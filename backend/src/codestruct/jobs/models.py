"""Thread-safe job-domain records, independent of FastAPI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class JobState(str, Enum):
    SUBMITTED = "submitted"
    VALIDATING = "validating"
    QUEUED = "queued"
    SCANNING = "scanning"
    PARSING = "parsing"
    RESOLVING = "resolving"
    BUILDING_GRAPH = "building_graph"
    COMPUTING_METRICS = "computing_metrics"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"
    CACHE_HIT = "cache_hit"


TERMINAL_STATES = {
    JobState.COMPLETED,
    JobState.PARTIALLY_COMPLETED,
    JobState.FAILED,
    JobState.CANCELLED,
}
CANCELLABLE_STATES = {
    JobState.SUBMITTED,
    JobState.VALIDATING,
    JobState.QUEUED,
    JobState.SCANNING,
    JobState.PARSING,
    JobState.RESOLVING,
    JobState.BUILDING_GRAPH,
    JobState.COMPUTING_METRICS,
    JobState.CANCELLATION_REQUESTED,
}


@dataclass(slots=True)
class JobRecord:
    analysis_id: str
    root_id: str
    project_root: str
    state: JobState = JobState.SUBMITTED
    percent: int | None = 0
    message_code: str = "ANALYSIS_SUBMITTED"
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    updated_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    revision: int = 0
    partial: bool = False
    graph: dict[str, object] | None = None
    diagnostics: list[dict[str, object]] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    expires_at_epoch: float | None = None
    cache_hit: bool = False
    cache_key: str | None = None
