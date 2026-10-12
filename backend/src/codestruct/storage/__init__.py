"""Persistent job and analysis-result repositories."""

from .file_cache import (
    DEFAULT_MAX_CACHE_BYTES,
    DEFAULT_MAX_CACHE_ENTRIES,
    PARSER_VERSION,
    PersistentFileParseCache,
    compute_file_cache_key,
    compute_parse_policy_fingerprint,
    dict_to_file_parse_result,
    file_parse_result_to_dict,
)
from .sqlite_repository import SQLiteRepository

__all__ = [
    "DEFAULT_MAX_CACHE_BYTES",
    "DEFAULT_MAX_CACHE_ENTRIES",
    "PARSER_VERSION",
    "PersistentFileParseCache",
    "SQLiteRepository",
    "compute_file_cache_key",
    "compute_parse_policy_fingerprint",
    "dict_to_file_parse_result",
    "file_parse_result_to_dict",
]
