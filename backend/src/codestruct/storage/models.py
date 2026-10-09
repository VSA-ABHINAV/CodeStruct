from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CacheEntry:
    cache_key: str
    graph: dict[str, object]
    created_at: str
    last_accessed_at: str
    expires_at_epoch: float
    stored_size: int


@dataclass(frozen=True, slots=True)
class RuntimeSessionRecord:
    session_id: str
    analysis_id: str
    target_file: str
    entry_function: str | None
    status: str
    total_calls: int
    execution_time_seconds: float
    overhead_seconds: float
    covered_nodes: int
    total_nodes: int
    coverage_percent: float
    trace_events_count: int
    created_at: str
    error_message: str | None = None
