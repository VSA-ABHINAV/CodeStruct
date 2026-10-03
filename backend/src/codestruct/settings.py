"""Validated, environment-backed application settings for the local MVP."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .analysis import AnalysisPolicy


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    value = default if raw is None else int(raw)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _paths(raw: str | None, fallback: Path) -> dict[str, Path]:
    if not raw:
        return {"sample": fallback.resolve(strict=True)} if fallback.is_dir() else {}
    roots: dict[str, Path] = {}
    canonical: set[str] = set()
    for index, item in enumerate(
        part.strip() for part in raw.split(os.pathsep) if part.strip()
    ):
        if "=" in item:
            root_id, value = (part.strip() for part in item.split("=", 1))
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", root_id):
                raise ValueError(
                    "authorized root aliases must use letters, numbers, '_' or '-'"
                )
        else:
            root_id, value = f"root-{index + 1}", item
        if root_id in roots:
            raise ValueError("authorized root aliases must be unique")
        try:
            resolved = Path(value).resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError(
                "every authorized root must be an existing directory"
            ) from None
        identity = os.path.normcase(str(resolved))
        if identity in canonical:
            raise ValueError("authorized root locations must be unique")
        canonical.add(identity)
        roots[root_id] = resolved
    if not roots:
        raise ValueError("CODESTRUCT_AUTHORIZED_ROOTS must contain a directory")
    if any(not value.is_dir() for value in roots.values()):
        raise ValueError("every authorized root must be an existing directory")
    return roots


@dataclass(frozen=True, slots=True)
class Settings:
    authorized_roots: dict[str, Path]
    database_path: Path | None = None
    max_concurrent_jobs: int = 2
    max_queued_jobs: int = 8
    analysis_timeout_seconds: int = 120
    cancellation_grace_seconds: int = 3
    result_retention_seconds: int = 900
    polling_interval_ms: int = 750
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    environment: str = "development"
    max_depth: int = 40
    max_files: int = 10_000
    max_file_size: int = 2 * 1024 * 1024
    max_cache_results: int = 100
    max_cache_bytes: int = 256 * 1024 * 1024
    max_full_graph_bytes: int = 4 * 1024 * 1024
    max_graph_page_size: int = 1000

    def policy(self) -> AnalysisPolicy:
        return AnalysisPolicy(
            authorized_roots=tuple(self.authorized_roots.values()),
            max_depth=self.max_depth,
            max_files=self.max_files,
            max_file_size=self.max_file_size,
        )


def load_settings() -> Settings:
    repository = Path(__file__).resolve().parents[3]
    sample = repository / "sample_project"
    if os.name == "nt":
        data_home = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        data_home = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    default_database = data_home / "CodeStruct" / "codestruct.sqlite3"
    origins = tuple(
        value.strip()
        for value in os.getenv(
            "CODESTRUCT_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if value.strip()
    )
    if any(value == "*" for value in origins):
        raise ValueError("wildcard CORS origins are not permitted")
    return Settings(
        authorized_roots=_paths(os.getenv("CODESTRUCT_AUTHORIZED_ROOTS"), sample),
        database_path=Path(
            os.getenv(
                "CODESTRUCT_DATABASE_PATH",
                str(default_database),
            )
        ).resolve(),
        max_concurrent_jobs=_integer("CODESTRUCT_MAX_CONCURRENT_JOBS", 2, 1, 16),
        max_queued_jobs=_integer("CODESTRUCT_MAX_QUEUED_JOBS", 8, 0, 100),
        analysis_timeout_seconds=_integer(
            "CODESTRUCT_ANALYSIS_TIMEOUT_SECONDS", 120, 1, 3600
        ),
        cancellation_grace_seconds=_integer(
            "CODESTRUCT_CANCELLATION_GRACE_SECONDS", 3, 1, 30
        ),
        result_retention_seconds=_integer(
            "CODESTRUCT_RESULT_RETENTION_SECONDS", 900, 10, 86400
        ),
        polling_interval_ms=_integer("CODESTRUCT_POLLING_INTERVAL_MS", 750, 250, 10000),
        cors_origins=origins,
        environment=os.getenv("CODESTRUCT_ENV", "development"),
        max_depth=_integer("CODESTRUCT_MAX_DEPTH", 40, 0, 200),
        max_files=_integer("CODESTRUCT_MAX_FILES", 10_000, 1, 100_000),
        max_file_size=_integer(
            "CODESTRUCT_MAX_FILE_SIZE", 2 * 1024 * 1024, 1, 100 * 1024 * 1024
        ),
        max_cache_results=_integer("CODESTRUCT_MAX_CACHE_RESULTS", 100, 1, 10000),
        max_cache_bytes=_integer(
            "CODESTRUCT_MAX_CACHE_BYTES",
            256 * 1024 * 1024,
            1024 * 1024,
            10 * 1024 * 1024 * 1024,
        ),
        max_full_graph_bytes=_integer(
            "CODESTRUCT_MAX_FULL_GRAPH_BYTES", 4 * 1024 * 1024, 65536, 128 * 1024 * 1024
        ),
        max_graph_page_size=_integer("CODESTRUCT_MAX_GRAPH_PAGE_SIZE", 1000, 10, 10000),
    )
