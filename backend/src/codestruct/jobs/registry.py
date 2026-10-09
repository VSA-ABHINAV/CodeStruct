"""In-memory job and result repository with monotonic transitions."""

from __future__ import annotations

import time
from copy import deepcopy
from threading import RLock
from typing import Any

from .models import TERMINAL_STATES, JobRecord, JobState, utc_now


class InvalidTransitionError(RuntimeError):
    pass


_ALLOWED = {
    JobState.SUBMITTED: {JobState.VALIDATING, JobState.CANCELLATION_REQUESTED},
    JobState.VALIDATING: {
        JobState.QUEUED,
        JobState.CACHE_HIT,
        JobState.FAILED,
        JobState.CANCELLATION_REQUESTED,
    },
    JobState.QUEUED: {
        JobState.SCANNING,
        JobState.FAILED,
        JobState.CANCELLATION_REQUESTED,
    },
    JobState.SCANNING: {
        JobState.PARSING,
        JobState.FAILED,
        JobState.CANCELLATION_REQUESTED,
    },
    JobState.PARSING: {
        JobState.RESOLVING,
        JobState.FAILED,
        JobState.CANCELLATION_REQUESTED,
    },
    JobState.RESOLVING: {
        JobState.BUILDING_GRAPH,
        JobState.FAILED,
        JobState.CANCELLATION_REQUESTED,
    },
    JobState.BUILDING_GRAPH: {
        JobState.COMPLETED,
        JobState.PARTIALLY_COMPLETED,
        JobState.FAILED,
        JobState.CANCELLATION_REQUESTED,
    },
    JobState.COMPUTING_METRICS: {
        JobState.COMPLETED,
        JobState.PARTIALLY_COMPLETED,
        JobState.FAILED,
        JobState.CANCELLATION_REQUESTED,
    },
    JobState.CACHE_HIT: {JobState.COMPLETED},
    JobState.CANCELLATION_REQUESTED: {
        JobState.CANCELLED,
        JobState.COMPLETED,
        JobState.PARTIALLY_COMPLETED,
        JobState.FAILED,
    },
}


class JobRegistry:
    def __init__(self, retention_seconds: int) -> None:
        self._records: dict[str, JobRecord] = {}
        self._runtime_sessions: dict[str, list[Any]] = {}
        self._expired: set[str] = set()
        self._lock = RLock()
        self._retention = retention_seconds

    def add(self, record: JobRecord) -> None:
        with self._lock:
            self._records[record.analysis_id] = record

    def get(self, analysis_id: str) -> JobRecord | None:
        with self._lock:
            value = self._records.get(analysis_id)
            return deepcopy(value) if value else None

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
        with self._lock:
            record = self._records[analysis_id]
            if state != record.state:
                if state not in _ALLOWED.get(record.state, set()):
                    raise InvalidTransitionError(
                        f"invalid transition {record.state} -> {state}"
                    )
                if record.state in TERMINAL_STATES:
                    raise InvalidTransitionError("terminal jobs are immutable")
                record.state = state
            if percent is not None:
                if record.percent is not None and percent < record.percent:
                    raise InvalidTransitionError("progress cannot decrease")
                record.percent = min(100, max(0, percent))
            now = utc_now()
            if record.started_at is None and state not in {
                JobState.SUBMITTED,
                JobState.VALIDATING,
                JobState.QUEUED,
            }:
                record.started_at = now
            record.updated_at = now
            record.revision += 1
            if message_code is not None:
                record.message_code = message_code
            if graph is not None:
                record.graph = graph
            if diagnostics is not None:
                record.diagnostics = diagnostics
            record.error_code = error_code
            record.error_message = error_message
            if state in TERMINAL_STATES:
                record.completed_at = now
                record.expires_at_epoch = time.time() + self._retention
                record.percent = (
                    100
                    if state in {JobState.COMPLETED, JobState.PARTIALLY_COMPLETED}
                    else record.percent
                )
            record.partial = state is JobState.PARTIALLY_COMPLETED
            return deepcopy(record)

    def cleanup_expired(self) -> int:
        now = time.time()
        with self._lock:
            expired = [
                key
                for key, value in self._records.items()
                if value.expires_at_epoch and value.expires_at_epoch <= now
            ]
            for key in expired:
                del self._records[key]
                if key in self._runtime_sessions:
                    del self._runtime_sessions[key]
                self._expired.add(key)
            return len(expired)

    def is_expired(self, analysis_id: str) -> bool:
        with self._lock:
            return analysis_id in self._expired

    def save_runtime_session(self, session: Any) -> None:
        with self._lock:
            if session.analysis_id not in self._runtime_sessions:
                self._runtime_sessions[session.analysis_id] = []
            self._runtime_sessions[session.analysis_id].append(deepcopy(session))

    def get_runtime_sessions(self, analysis_id: str) -> list[Any]:
        with self._lock:
            return deepcopy(self._runtime_sessions.get(analysis_id, []))

    def update_analysis_graph(self, analysis_id: str, graph: dict[str, object]) -> None:
        with self._lock:
            record = self._records.get(analysis_id)
            if record is not None:
                record.graph = deepcopy(graph)
                record.updated_at = utc_now()
                record.revision += 1
