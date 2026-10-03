"""Immutable analysis policy for safe project discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".hypothesis",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        "site-packages",
        "vendor",
        "build",
        "dist",
        ".codestruct",
        "analysis-output",
    }
)

DEFAULT_EXCLUDED_FILE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.development",
        ".env.production",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
    }
)


@dataclass(frozen=True, slots=True)
class AnalysisPolicy:
    authorized_roots: tuple[Path, ...] = ()
    include_patterns: tuple[str, ...] = (
        "*.py",
        "**/*.py",
        "*.pyw",
        "**/*.pyw",
        "*.pyi",
        "**/*.pyi",
    )
    exclude_patterns: tuple[str, ...] = ()
    excluded_directories: frozenset[str] = field(
        default_factory=lambda: DEFAULT_EXCLUDED_DIRECTORIES
    )
    excluded_file_names: frozenset[str] = field(
        default_factory=lambda: DEFAULT_EXCLUDED_FILE_NAMES
    )
    max_depth: int = 40
    max_files: int = 10_000
    max_file_size: int = 2 * 1024 * 1024
    source_grammar: tuple[int, int] | None = None
    single_file_name: str | None = None
    compute_metrics: bool = False

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        if self.max_files < 0:
            raise ValueError("max_files must be non-negative")
        if self.max_file_size < 0:
            raise ValueError("max_file_size must be non-negative")
        if not self.include_patterns:
            raise ValueError("at least one include pattern is required")
        if self.source_grammar is not None:
            major, minor = self.source_grammar
            if major != 3 or not 10 <= minor <= 14:
                raise ValueError(
                    "source_grammar must be a supported Python 3.10-3.14 version"
                )
