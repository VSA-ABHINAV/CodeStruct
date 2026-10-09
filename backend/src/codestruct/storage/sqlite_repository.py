"""SQLite/WAL repository with per-operation connections and checked JSON."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import RLock

from codestruct import __version__
from codestruct.graph import graph_from_dict
from codestruct.graph.builder import SCHEMA_VERSION
from codestruct.jobs.models import TERMINAL_STATES, JobRecord, JobState, utc_now
from codestruct.jobs.registry import _ALLOWED, InvalidTransitionError

from .errors import CorruptCacheEntryError, StorageError
from .migrations import migrate
from .models import CacheEntry, RuntimeSessionRecord


class SQLiteRepository:
    def __init__(
        self,
        path: Path,
        retention_seconds: int,
        *,
        busy_timeout_ms: int = 3000,
        max_payload_bytes: int = 32 * 1024 * 1024,
        max_results: int = 100,
        max_bytes: int = 256 * 1024 * 1024,
    ) -> None:
        self.path = path
        self.retention_seconds = retention_seconds
        self.busy_timeout_ms = busy_timeout_ms
        self.max_payload_bytes = max_payload_bytes
        self.max_results = max_results
        self.max_bytes = max_bytes
        self._lock = RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            migrate(connection)
        self.recover_interrupted()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout_ms / 1000)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _loads(value: str | None, fallback):
        return fallback if value is None else json.loads(value)

    def _record(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            analysis_id=row["analysis_id"],
            root_id=row["root_id"],
            project_root=row["project_identity"],
            state=JobState(row["state"]),
            percent=row["percent"],
            message_code=row["message_code"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            revision=row["revision"],
            partial=bool(row["partial"]),
            graph=self._loads(row["graph_json"], None),
            diagnostics=self._loads(row["diagnostics_json"], []),
            error_code=row["error_code"],
            error_message=row["error_message"],
            expires_at_epoch=row["expires_at_epoch"],
            cache_hit=bool(row["cache_hit"]),
            cache_key=row["cache_key"],
        )

    def add(self, record: JobRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record.analysis_id,
                    record.root_id,
                    record.project_root,
                    record.state.value,
                    record.percent,
                    record.message_code,
                    record.created_at,
                    record.started_at,
                    record.updated_at,
                    record.completed_at,
                    record.revision,
                    int(record.partial),
                    None,
                    "[]",
                    record.error_code,
                    record.error_message,
                    record.expires_at_epoch,
                    int(record.cache_hit),
                    record.cache_key,
                ),
            )

    def get(self, analysis_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE analysis_id=?", (analysis_id,)
            ).fetchone()
        return self._record(row) if row else None

    def transition(
        self,
        analysis_id: str,
        state: JobState,
        *,
        percent: int | None = None,
        message_code: str | None = None,
        graph: dict[str, object] | None = None,
        diagnostics: list[dict[str, object]] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE analysis_id=?", (analysis_id,)
            ).fetchone()
            if row is None:
                raise KeyError(analysis_id)
            record = self._record(row)
            if state != record.state and (
                record.state in TERMINAL_STATES
                or state not in _ALLOWED.get(record.state, set())
            ):
                raise InvalidTransitionError(
                    f"invalid transition {record.state} -> {state}"
                )
            if (
                percent is not None
                and record.percent is not None
                and percent < record.percent
            ):
                raise InvalidTransitionError("progress cannot decrease")
            record.state = state
            record.percent = (
                min(100, max(0, percent)) if percent is not None else record.percent
            )
            record.message_code = message_code or record.message_code
            record.updated_at = utc_now()
            record.revision += 1
            if record.started_at is None and state not in {
                JobState.SUBMITTED,
                JobState.VALIDATING,
                JobState.QUEUED,
            }:
                record.started_at = record.updated_at
            if graph is not None:
                record.graph = graph
            if diagnostics is not None:
                record.diagnostics = diagnostics
            record.error_code = error_code
            record.error_message = error_message
            record.partial = state is JobState.PARTIALLY_COMPLETED
            if state in TERMINAL_STATES:
                record.completed_at = record.updated_at
                record.expires_at_epoch = time.time() + self.retention_seconds
            graph_json = (
                json.dumps(record.graph, sort_keys=True, separators=(",", ":"))
                if record.graph is not None
                else None
            )
            if graph_json and len(graph_json.encode()) > self.max_payload_bytes:
                raise StorageError("result exceeds configured storage limit")
            connection.execute(
                "UPDATE jobs SET state=?,percent=?,message_code=?,started_at=?,updated_at=?,completed_at=?,revision=?,partial=?,graph_json=?,diagnostics_json=?,error_code=?,error_message=?,expires_at_epoch=?,cache_hit=?,cache_key=? WHERE analysis_id=?",
                (
                    record.state.value,
                    record.percent,
                    record.message_code,
                    record.started_at,
                    record.updated_at,
                    record.completed_at,
                    record.revision,
                    int(record.partial),
                    graph_json,
                    json.dumps(
                        record.diagnostics, sort_keys=True, separators=(",", ":")
                    ),
                    record.error_code,
                    record.error_message,
                    record.expires_at_epoch,
                    int(record.cache_hit),
                    record.cache_key,
                    analysis_id,
                ),
            )
            connection.commit()
            return deepcopy(record)

    def cleanup_expired(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM cache_results WHERE expires_at_epoch<=?", (time.time(),)
            )
            connection.execute(
                "INSERT OR REPLACE INTO expired_jobs SELECT analysis_id,? FROM jobs WHERE expires_at_epoch IS NOT NULL AND expires_at_epoch<=?",
                (time.time() + self.retention_seconds, time.time()),
            )
            connection.execute(
                "DELETE FROM jobs WHERE expires_at_epoch IS NOT NULL AND expires_at_epoch<=?",
                (time.time(),),
            )
            connection.execute(
                "DELETE FROM expired_jobs WHERE forget_after_epoch<=?", (time.time(),)
            )
            return cursor.rowcount

    def is_expired(self, analysis_id: str) -> bool:
        with self._connect() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM expired_jobs WHERE analysis_id=?", (analysis_id,)
                ).fetchone()
                is not None
            )

    def recover_interrupted(self) -> int:
        active = tuple(
            state.value for state in JobState if state not in TERMINAL_STATES
        )
        placeholders = ",".join("?" for _ in active)
        now = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE jobs SET state='failed',message_code='PROCESS_RESTARTED',error_code='PROCESS_RESTARTED',error_message='The analysis was interrupted by an application restart.',completed_at=?,updated_at=?,revision=revision+1,expires_at_epoch=? WHERE state IN ({placeholders})",  # noqa: S608 -- placeholders are generated solely from a fixed enum set.
                (now, now, time.time() + self.retention_seconds, *active),
            )
            return cursor.rowcount

    def find_cache(self, key: str) -> CacheEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cache_results WHERE cache_key=? AND invalid=0 AND expires_at_epoch>?",
                (key, time.time()),
            ).fetchone()
            if row is None:
                return None
            if (
                row["schema_version"] != SCHEMA_VERSION
                or row["analyzer_version"] != __version__
            ):
                connection.execute(
                    "UPDATE cache_results SET invalid=1 WHERE cache_key=?", (key,)
                )
                return None
            raw = row["graph_json"]
            if (
                len(raw.encode()) > self.max_payload_bytes
                or hashlib.sha256(raw.encode()).hexdigest() != row["graph_sha256"]
            ):
                connection.execute(
                    "UPDATE cache_results SET invalid=1 WHERE cache_key=?", (key,)
                )
                raise CorruptCacheEntryError("cached graph integrity check failed")
            try:
                graph = json.loads(raw)
                graph_from_dict(graph)
            except (ValueError, TypeError, KeyError) as error:
                connection.execute(
                    "UPDATE cache_results SET invalid=1 WHERE cache_key=?", (key,)
                )
                raise CorruptCacheEntryError(
                    "cached graph validation failed"
                ) from error
            now = utc_now()
            connection.execute(
                "UPDATE cache_results SET last_accessed_at=? WHERE cache_key=?",
                (now, key),
            )
            return CacheEntry(
                key,
                graph,
                row["created_at"],
                now,
                row["expires_at_epoch"],
                row["stored_size"],
            )

    def store_cache(
        self, key: str, graph: dict[str, object], policy_hash: str, project_hash: str
    ) -> None:
        metadata = graph.get("metadata")
        if isinstance(metadata, dict) and metadata.get("partial"):
            return
        graph_from_dict(graph)
        raw = json.dumps(graph, sort_keys=True, separators=(",", ":"))
        size = len(raw.encode())
        if size > self.max_payload_bytes:
            raise StorageError("result exceeds configured storage limit")
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO cache_results VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
                (
                    key,
                    raw,
                    hashlib.sha256(raw.encode()).hexdigest(),
                    SCHEMA_VERSION,
                    __version__,
                    policy_hash,
                    project_hash,
                    now,
                    now,
                    time.time() + self.retention_seconds,
                    size,
                ),
            )
        self.evict(self.max_results, self.max_bytes)

    def mark_cache_hit(self, analysis_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET cache_hit=1 WHERE analysis_id=?", (analysis_id,)
            )

    def evict(self, max_results: int, max_bytes: int) -> int:
        removed = 0
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT cache_key,stored_size FROM cache_results ORDER BY last_accessed_at,cache_key"
            ).fetchall()
            total = sum(row["stored_size"] for row in rows)
            while len(rows) - removed > max_results or total > max_bytes:
                row = rows[removed]
                connection.execute(
                    "DELETE FROM cache_results WHERE cache_key=?", (row["cache_key"],)
                )
                total -= row["stored_size"]
                removed += 1
        return removed

    def save_runtime_session(self, session: RuntimeSessionRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runtime_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    session.session_id,
                    session.analysis_id,
                    session.target_file,
                    session.entry_function,
                    session.status,
                    session.total_calls,
                    session.execution_time_seconds,
                    session.overhead_seconds,
                    session.covered_nodes,
                    session.total_nodes,
                    session.coverage_percent,
                    session.trace_events_count,
                    session.created_at,
                    session.error_message,
                ),
            )

    def get_runtime_sessions(self, analysis_id: str) -> list[RuntimeSessionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runtime_sessions WHERE analysis_id=? ORDER BY created_at",
                (analysis_id,),
            ).fetchall()
            return [
                RuntimeSessionRecord(
                    session_id=row["session_id"],
                    analysis_id=row["analysis_id"],
                    target_file=row["target_file"],
                    entry_function=row["entry_function"],
                    status=row["status"],
                    total_calls=row["total_calls"],
                    execution_time_seconds=row["execution_time_seconds"],
                    overhead_seconds=row["overhead_seconds"],
                    covered_nodes=row["covered_nodes"],
                    total_nodes=row["total_nodes"],
                    coverage_percent=row["coverage_percent"],
                    trace_events_count=row["trace_events_count"],
                    created_at=row["created_at"],
                    error_message=row["error_message"],
                )
                for row in rows
            ]

    def update_analysis_graph(self, analysis_id: str, graph: dict[str, object]) -> None:
        raw = json.dumps(graph, sort_keys=True, separators=(",", ":"))
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET graph_json=?, updated_at=? WHERE analysis_id=?",
                (raw, now, analysis_id),
            )
