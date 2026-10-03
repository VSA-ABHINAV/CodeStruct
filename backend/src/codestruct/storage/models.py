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
