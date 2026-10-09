"""Analysis use-case service: authorize, register, dispatch, inspect, cancel."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from codestruct.settings import Settings
from codestruct.storage import SQLiteRepository
from codestruct.storage.cache_keys import (
    cache_key,
    policy_fingerprint,
    project_fingerprint,
)
from codestruct.storage.errors import CorruptCacheEntryError
from codestruct.storage.interfaces import JobRepository
from codestruct.storage.models import RuntimeSessionRecord

from .executor import QueueFullError, SpawnJobExecutor
from .models import TERMINAL_STATES, JobRecord, JobState
from .registry import JobRegistry

logger = logging.getLogger(__name__)


class ProjectSelectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(slots=True)
class EditorNavigationCommand:
    command_id: str
    relative_path: str
    line: int
    column: int | None
    created_at: float
    expires_at: float
    status: str = "queued"
    failure_reason: str | None = None


@dataclass(slots=True)
class EditorCapability:
    capability_id: str
    file_path: Path
    canonical_path: Path
    file_identity: str
    filename: str
    file_digest: str
    expires_at: float
    canonical_root: Path | None = None
    revoked: bool = False
    pending_command: EditorNavigationCommand | None = None
    last_command: EditorNavigationCommand | None = None


class AnalysisService:
    def __init__(
        self, settings: Settings, repository: JobRepository | None = None
    ) -> None:
        self.settings = settings
        self._editor_capabilities: dict[str, EditorCapability] = {}
        self._editor_lock = threading.RLock()
        if repository is not None:
            self.registry: JobRepository = repository
        elif settings.database_path:
            self.registry = SQLiteRepository(
                settings.database_path,
                settings.result_retention_seconds,
                max_payload_bytes=settings.max_full_graph_bytes * 8,
                max_results=settings.max_cache_results,
                max_bytes=settings.max_cache_bytes,
            )
        else:
            self.registry = JobRegistry(settings.result_retention_seconds)
        self.executor = SpawnJobExecutor(
            self.registry,
            max_workers=settings.max_concurrent_jobs,
            max_queued=settings.max_queued_jobs,
            timeout_seconds=settings.analysis_timeout_seconds,
            cancellation_grace_seconds=settings.cancellation_grace_seconds,
        )

    def register_editor_file(
        self, file_path: str | Path, ttl_seconds: float = 120.0
    ) -> EditorCapability:
        if not file_path or not str(file_path).strip():
            raise ProjectSelectionError("INVALID_PATH", "File path must not be empty.")
        raw_path = Path(str(file_path).strip())
        if "\x00" in str(file_path):
            raise ProjectSelectionError(
                "INVALID_PATH", "File path contains an invalid character."
            )
        if ".." in raw_path.parts:
            raise ProjectSelectionError(
                "PROJECT_UNAUTHORIZED", "Path traversal is not permitted."
            )

        from codestruct.analysis.scanner import (
            _has_link_component,
            _is_link_or_reparse,
            _is_within,
        )

        # R1: Check for ancestor junction/reparse/symlink escape before resolution
        if _has_link_component(raw_path):
            raise ProjectSelectionError(
                "PROJECT_UNAUTHORIZED",
                "Symlinks, junctions, and reparse points are not permitted.",
            )

        try:
            resolved = raw_path.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ProjectSelectionError(
                "PROJECT_NOT_FOUND",
                "The specified file does not exist or is inaccessible.",
            ) from None

        if not resolved.is_file():
            raise ProjectSelectionError(
                "PROJECT_NOT_FOUND", "The specified path is not a regular file."
            )

        if _is_link_or_reparse(resolved):
            raise ProjectSelectionError(
                "PROJECT_UNAUTHORIZED",
                "Symlinks and reparse points are not permitted.",
            )

        suffix = resolved.suffix.lower()
        if suffix not in (".py", ".pyw"):
            raise ProjectSelectionError(
                "UNSUPPORTED_EXTENSION",
                "CodeStruct only analyzes Python (.py, .pyw) files.",
            )

        try:
            with resolved.open("rb") as f:
                f.read(1)
        except OSError as err:
            raise ProjectSelectionError(
                "PERMISSION_DENIED", f"Cannot read the specified file: {err}"
            ) from err

        file_identity = os.path.normcase(str(resolved))
        file_digest = hashlib.sha256(file_identity.encode("utf-8")).hexdigest()
        now = time.time()
        expires_at = now + max(0.001, ttl_seconds)

        canonical_root: Path | None = None
        for root_path in self.settings.authorized_roots.values():
            if _is_within(resolved, root_path):
                canonical_root = root_path
                break

        with self._editor_lock:
            # Prune expired capabilities
            expired = [
                k
                for k, cap in self._editor_capabilities.items()
                if cap.expires_at <= now or cap.revoked
            ]
            for k in expired:
                del self._editor_capabilities[k]

            # Bounded session storage: prune oldest if capacity reached
            max_capabilities = 100
            if len(self._editor_capabilities) >= max_capabilities:
                oldest_key = min(
                    self._editor_capabilities.keys(),
                    key=lambda k: self._editor_capabilities[k].expires_at,
                )
                del self._editor_capabilities[oldest_key]

            # R2: Independent registrations of the same file must not share credentials
            capability_id = "cap_" + secrets.token_urlsafe(24)
            capability = EditorCapability(
                capability_id=capability_id,
                file_path=raw_path,
                canonical_path=resolved,
                file_identity=file_identity,
                filename=resolved.name,
                file_digest=file_digest,
                expires_at=expires_at,
                canonical_root=canonical_root,
            )
            self._editor_capabilities[capability_id] = capability
            return capability

    def get_editor_capability(self, capability_id: str) -> EditorCapability | None:
        now = time.time()
        with self._editor_lock:
            cap = self._editor_capabilities.get(capability_id)
            if cap is None:
                return None
            if cap.revoked or cap.expires_at <= now:
                del self._editor_capabilities[capability_id]
                return None
            return cap

    def revoke_editor_capability(self, capability_id: str) -> bool:
        with self._editor_lock:
            cap = self._editor_capabilities.get(capability_id)
            if cap is None:
                return False
            cap.revoked = True
            cap.pending_command = None
            del self._editor_capabilities[capability_id]
            return True

    def queue_editor_navigation(
        self,
        capability_id: str,
        relative_path: str,
        line: int,
        column: int | None = None,
        command_ttl_seconds: float = 120.0,
    ) -> EditorNavigationCommand:
        if capability_id in self.settings.authorized_roots:
            raise ProjectSelectionError(
                "SESSION_UNAUTHORIZED",
                "A public project alias is not a valid editor session credential.",
            )

        with self._editor_lock:
            cap = self.get_editor_capability(capability_id)
            if cap is None:
                raise ProjectSelectionError(
                    "SESSION_UNAUTHORIZED",
                    "The editor session is invalid, expired, or revoked.",
                )

            if not relative_path or not relative_path.strip():
                raise ProjectSelectionError("INVALID_PATH", "Path must not be empty.")
            if "\x00" in relative_path:
                raise ProjectSelectionError(
                    "INVALID_PATH", "Path contains an invalid character."
                )

            clean_path = relative_path.strip()
            if (
                clean_path.startswith(("/", "\\"))
                or bool(re.match(r"^[A-Za-z]:", clean_path))
                or clean_path.startswith(("//", "\\\\"))
                or Path(clean_path).is_absolute()
            ):
                raise ProjectSelectionError(
                    "PROJECT_UNAUTHORIZED", "Absolute paths are not permitted."
                )

            clean_slash = clean_path.replace("\\", "/")
            raw_parts = [p for p in clean_slash.split("/") if p]
            if ".." in raw_parts:
                raise ProjectSelectionError(
                    "PROJECT_UNAUTHORIZED", "Path traversal is not permitted."
                )

            norm_rel = clean_slash
            while norm_rel.startswith("./"):
                norm_rel = norm_rel[2:]
            norm_rel = norm_rel.strip()

            if norm_rel != cap.filename:
                raise ProjectSelectionError(
                    "SCOPE_UNAUTHORIZED",
                    f"Path '{relative_path}' is outside the authorized editor session scope.",
                )

            from codestruct.analysis.scanner import (
                _has_link_component,
                _is_link_or_reparse,
                _is_within,
            )

            # R1: Verify original registered path has no ancestor junction/reparse/symlink escape
            if _has_link_component(cap.file_path):
                raise ProjectSelectionError(
                    "PROJECT_UNAUTHORIZED",
                    "Symlinks, junctions, and reparse points are not permitted.",
                )

            try:
                verified = cap.file_path.resolve(strict=True)
            except (OSError, RuntimeError):
                raise ProjectSelectionError(
                    "PROJECT_NOT_FOUND", "The target file does not exist."
                ) from None

            if not verified.is_file():
                raise ProjectSelectionError(
                    "PROJECT_NOT_FOUND", "The target file is not a regular file."
                )

            if _is_link_or_reparse(verified):
                raise ProjectSelectionError(
                    "PROJECT_UNAUTHORIZED",
                    "Symlinks and reparse points are not permitted.",
                )

            # R1: Compare resolved scope with registered identity
            if os.path.normcase(str(verified)) != cap.file_identity:
                raise ProjectSelectionError(
                    "PROJECT_UNAUTHORIZED",
                    "Path identity changed or ancestor replaced.",
                )

            if cap.canonical_root is not None and not _is_within(
                verified, cap.canonical_root
            ):
                raise ProjectSelectionError(
                    "PERMISSION_DENIED",
                    "Resolved path escapes project root.",
                )

            if line < 1:
                raise ProjectSelectionError("INVALID_PATH", "Line number must be >= 1.")
            if column is not None and column < 1:
                raise ProjectSelectionError(
                    "INVALID_PATH", "Column number must be >= 1."
                )

            command_id = "nav_" + secrets.token_urlsafe(9)
            now = time.time()
            cmd = EditorNavigationCommand(
                command_id=command_id,
                relative_path=cap.filename,
                line=line,
                column=column,
                created_at=now,
                expires_at=now + command_ttl_seconds,
            )
            cap.pending_command = cmd
            cap.last_command = cmd
            return cmd

    def get_pending_navigation(
        self, capability_id: str
    ) -> EditorNavigationCommand | None:
        with self._editor_lock:
            cap = self.get_editor_capability(capability_id)
            if cap is None:
                raise ProjectSelectionError(
                    "SESSION_UNAUTHORIZED",
                    "The editor session is invalid, expired, or revoked.",
                )

            if cap.pending_command is None:
                return None

            now = time.time()
            if cap.pending_command.expires_at <= now:
                cap.pending_command = None
                return None

            from codestruct.analysis.scanner import (
                _has_link_component,
                _is_link_or_reparse,
                _is_within,
            )

            if _has_link_component(cap.file_path):
                cap.pending_command = None
                return None

            try:
                verified = cap.file_path.resolve(strict=True)
                if not verified.is_file():
                    cap.pending_command = None
                    return None

                if _is_link_or_reparse(verified):
                    cap.pending_command = None
                    return None

                if os.path.normcase(str(verified)) != cap.file_identity:
                    cap.pending_command = None
                    return None

                if cap.canonical_root is not None and not _is_within(
                    verified, cap.canonical_root
                ):
                    cap.pending_command = None
                    return None
            except (OSError, RuntimeError):
                cap.pending_command = None
                return None

            return cap.pending_command

    def acknowledge_navigation(
        self,
        capability_id: str,
        command_id: str,
        status: str = "delivered",
        reason: str | None = None,
    ) -> tuple[bool, str]:
        with self._editor_lock:
            cap = self.get_editor_capability(capability_id)
            if cap is None:
                raise ProjectSelectionError(
                    "SESSION_UNAUTHORIZED",
                    "The editor session is invalid, expired, or revoked.",
                )

            now = time.time()

            if cap.pending_command and cap.pending_command.command_id == command_id:
                if cap.pending_command.expires_at <= now:
                    cap.pending_command = None
                    return False, "command_expired"
                outcome = "delivered" if status == "delivered" else "failed"
                cap.pending_command.status = outcome
                cap.pending_command.failure_reason = reason
                if cap.last_command and cap.last_command.command_id == command_id:
                    cap.last_command.status = outcome
                    cap.last_command.failure_reason = reason
                cap.pending_command = None
                return True, outcome

            if cap.last_command and cap.last_command.command_id == command_id:
                if cap.last_command.expires_at <= now:
                    return False, "command_expired"
                return False, "already_consumed"

            return False, "unknown_command"

    def resolve_project(self, root_id: str, relative_path: str) -> Path:
        if root_id.startswith("cap_"):
            capability = self.get_editor_capability(root_id)
            if capability is None:
                raise ProjectSelectionError(
                    "PROJECT_UNAUTHORIZED",
                    "The selected editor capability has expired or is invalid.",
                )
            rel = relative_path.replace("\\", "/").strip()
            if rel not in (capability.filename, ".", ""):
                raise ProjectSelectionError(
                    "SCOPE_UNAUTHORIZED",
                    f"Selected path '{relative_path}' is outside the authorized single-file scope.",
                )

            from codestruct.analysis.scanner import _has_link_component

            if _has_link_component(capability.file_path):
                raise ProjectSelectionError(
                    "PROJECT_UNAUTHORIZED",
                    "Symlinks, junctions, and reparse points are not permitted.",
                )

            try:
                curr = capability.file_path.resolve(strict=True)
            except (OSError, RuntimeError):
                raise ProjectSelectionError(
                    "PROJECT_NOT_FOUND", "The target file does not exist."
                ) from None

            if os.path.normcase(str(curr)) != capability.file_identity:
                raise ProjectSelectionError(
                    "PROJECT_UNAUTHORIZED",
                    "Path identity changed or ancestor replaced.",
                )
            return curr.parent

        root = self.settings.authorized_roots.get(root_id)
        if root is None:
            raise ProjectSelectionError(
                "PROJECT_UNAUTHORIZED",
                "The selected project is outside authorized locations.",
            )
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ProjectSelectionError(
                "PROJECT_UNAUTHORIZED",
                "The selected project is outside authorized locations.",
            )
        try:
            candidate = (root / relative).resolve(strict=True)
        except (OSError, RuntimeError):
            raise ProjectSelectionError(
                "PROJECT_NOT_FOUND", "The selected project directory does not exist."
            ) from None
        try:
            inside = os.path.commonpath(
                (os.path.normcase(str(candidate)), os.path.normcase(str(root)))
            ) == os.path.normcase(str(root))
        except ValueError:
            inside = False
        if not inside:
            raise ProjectSelectionError(
                "PROJECT_UNAUTHORIZED",
                "The selected project is outside authorized locations.",
            )
        if not candidate.is_dir():
            raise ProjectSelectionError(
                "PROJECT_NOT_FOUND", "The selected project directory does not exist."
            )
        return candidate

    def create(
        self,
        root_id: str,
        relative_path: str,
        *,
        refresh: bool = False,
        compute_metrics: bool = False,
    ) -> JobRecord:
        self.registry.cleanup_expired()
        project = self.resolve_project(root_id, relative_path)
        capability = (
            self.get_editor_capability(root_id) if root_id.startswith("cap_") else None
        )
        if capability is not None:
            base_policy = self.settings.policy()
            policy = replace(
                base_policy,
                authorized_roots=(project.resolve(),),
                include_patterns=(capability.filename,),
                single_file_name=capability.filename,
                compute_metrics=compute_metrics,
            )
            policy_hash = policy_fingerprint(policy)
            project_hash = project_fingerprint(project, policy)
            cache_root_id = f"editor_{capability.file_digest}"
            key = cache_key(
                cache_root_id,
                capability.filename,
                project_hash,
                policy_hash,
            )
        else:
            base_policy = self.settings.policy()
            policy = replace(
                base_policy,
                compute_metrics=compute_metrics,
            )
            policy_hash = policy_fingerprint(policy)
            project_hash = project_fingerprint(project, policy)
            cache_root_id = root_id
            key = cache_key(root_id, relative_path, project_hash, policy_hash)

        analysis_id = "ana_" + secrets.token_urlsafe(18)
        record = JobRecord(
            analysis_id=analysis_id,
            root_id=cache_root_id,
            project_root=str(project),
            cache_key=key,
        )
        self.registry.add(record)
        self.registry.transition(
            analysis_id,
            JobState.VALIDATING,
            percent=2,
            message_code="VALIDATING_PROJECT",
        )
        if not refresh and hasattr(self.registry, "find_cache"):
            try:
                cached = self.registry.find_cache(key)
            except CorruptCacheEntryError:
                cached = None
            if cached is not None:
                logger.info("codestruct.cache.hit analysis_id=%s", analysis_id)
                logger.info(
                    "event=analysis_cache_hit analysis_id=%s stage=validating",
                    analysis_id,
                )
                self.registry.transition(
                    analysis_id,
                    JobState.CACHE_HIT,
                    percent=95,
                    message_code="CACHE_HIT",
                )
                hit = self.registry.transition(
                    analysis_id,
                    JobState.COMPLETED,
                    percent=100,
                    message_code="ANALYSIS_COMPLETED",
                    graph=cached.graph,
                    diagnostics=list(cached.graph.get("diagnostics", [])),
                )
                hit.cache_hit = True
                if hasattr(self.registry, "mark_cache_hit"):
                    self.registry.mark_cache_hit(analysis_id)
                return hit
        logger.info(
            "codestruct.cache.miss analysis_id=%s refresh=%s", analysis_id, refresh
        )
        logger.info(
            "event=analysis_cache_miss analysis_id=%s stage=validating", analysis_id
        )
        queued = self.registry.transition(
            analysis_id, JobState.QUEUED, percent=5, message_code="ANALYSIS_QUEUED"
        )
        try:
            self.executor.submit(analysis_id, str(project), policy)
        except QueueFullError:
            self.registry.transition(
                analysis_id,
                JobState.FAILED,
                error_code="QUEUE_FULL",
                error_message="The analysis queue is currently full.",
                message_code="QUEUE_FULL",
            )
            raise
        return queued

    def get(self, analysis_id: str) -> JobRecord | None:
        self.registry.cleanup_expired()
        return self.registry.get(analysis_id)

    def is_expired(self, analysis_id: str) -> bool:
        return self.registry.is_expired(analysis_id)

    def cancel(self, analysis_id: str) -> JobRecord | None:
        record = self.get(analysis_id)
        if record is None or record.state in TERMINAL_STATES:
            return record
        if record.state is not JobState.CANCELLATION_REQUESTED:
            record = self.registry.transition(
                analysis_id,
                JobState.CANCELLATION_REQUESTED,
                message_code="CANCELLATION_REQUESTED",
            )
        self.executor.cancel(analysis_id)
        return record

    def execute_runtime_session(
        self,
        analysis_id: str,
        target_file: str,
        *,
        entry_function: str | None = None,
        args: Sequence[str] = (),
        timeout_seconds: float = 10.0,
        max_events: int = 50000,
    ) -> tuple[RuntimeSessionRecord, dict[str, object]]:
        record = self.get(analysis_id)
        if record is None:
            raise ProjectSelectionError(
                "JOB_NOT_FOUND", "The requested analysis does not exist or has expired."
            )
        if record.graph is None or record.state not in (
            JobState.COMPLETED,
            JobState.PARTIALLY_COMPLETED,
        ):
            raise ProjectSelectionError(
                "RESULT_UNAVAILABLE",
                "Runtime execution requires a completed static analysis result.",
            )

        from codestruct.analysis.dynamic_tracer import (
            merge_runtime_trace_into_graph,
            trace_project_target,
        )
        from codestruct.graph.enums import NodeKind
        from codestruct.graph.serialization import graph_from_dict, graph_to_dict

        project_root = Path(record.project_root).resolve()
        target_path = (
            project_root / target_file
            if not Path(target_file).is_absolute()
            else Path(target_file)
        ).resolve()
        if not target_path.is_relative_to(project_root):
            raise ProjectSelectionError(
                "RUNTIME_PATH_OUTSIDE_PROJECT",
                f"Target file '{target_file}' is outside authorized project root.",
            )
        if not target_path.is_file():
            raise ProjectSelectionError(
                "TARGET_NOT_FOUND",
                f"Target file does not exist: '{target_file}'",
            )

        success, trace, error_msg = trace_project_target(
            project_root,
            target_path,
            entry_function=entry_function,
            args=args,
            timeout_seconds=timeout_seconds,
            max_events=max_events,
        )

        graph_res = graph_from_dict(record.graph)
        merged_res = merge_runtime_trace_into_graph(graph_res, trace)
        merged_dict = graph_to_dict(merged_res)

        # Update in-memory / persistent record
        if hasattr(self.registry, "update_analysis_graph"):
            self.registry.update_analysis_graph(analysis_id, merged_dict)

        # Calculate coverage stats
        target_kinds = (
            NodeKind.FUNCTION,
            NodeKind.METHOD,
            NodeKind.ASYNC_FUNCTION,
            NodeKind.ASYNC_METHOD,
        )
        total_nodes = len([n for n in merged_res.nodes if n.kind in target_kinds])
        covered_nodes = len(
            [
                n
                for n in merged_res.nodes
                if n.kind in target_kinds
                and (
                    dict(n.attributes).get("runtime_invocations")
                    or dict(n.attributes).get("runtime_calls_out")
                )
            ]
        )
        coverage_percent = (
            round(100.0 * covered_nodes / max(1, total_nodes), 2)
            if total_nodes > 0
            else 0.0
        )

        session_id = "rts_" + secrets.token_urlsafe(12)
        session = RuntimeSessionRecord(
            session_id=session_id,
            analysis_id=analysis_id,
            target_file=target_file,
            entry_function=entry_function,
            status="completed" if success else "failed",
            total_calls=trace.total_calls,
            execution_time_seconds=trace.execution_time_seconds,
            overhead_seconds=trace.overhead_seconds,
            covered_nodes=covered_nodes,
            total_nodes=total_nodes,
            coverage_percent=coverage_percent,
            trace_events_count=len(trace.events),
            created_at=datetime.now(timezone.utc).isoformat(),
            error_message=error_msg,
        )

        if hasattr(self.registry, "save_runtime_session"):
            self.registry.save_runtime_session(session)

        return session, merged_dict

    def get_runtime_sessions(self, analysis_id: str) -> list[RuntimeSessionRecord]:
        if hasattr(self.registry, "get_runtime_sessions"):
            return self.registry.get_runtime_sessions(analysis_id)
        return []

    def shutdown(self) -> None:
        self.executor.shutdown()
