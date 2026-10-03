"""Application-facing persistence ports."""

from __future__ import annotations

from typing import Protocol

from codestruct.jobs.models import JobRecord, JobState


class JobRepository(Protocol):
    def add(self, record: JobRecord) -> None: ...
    def get(self, analysis_id: str) -> JobRecord | None: ...
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
    ) -> JobRecord: ...
    def cleanup_expired(self) -> int: ...
    def is_expired(self, analysis_id: str) -> bool: ...


class CacheRepository(Protocol):
    def find_cache(self, key: str): ...
    def store_cache(
        self, key: str, graph: dict[str, object], policy_hash: str, project_hash: str
    ) -> None: ...
