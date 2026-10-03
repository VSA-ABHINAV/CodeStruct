"""Stable diagnostics for scanner and parser failures."""

from __future__ import annotations

from enum import Enum


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCode(str, Enum):
    INVALID_PROJECT_ROOT = "INVALID_PROJECT_ROOT"
    UNAUTHORIZED_ROOT = "UNAUTHORIZED_ROOT"
    PATH_TRAVERSAL_REJECTED = "PATH_TRAVERSAL_REJECTED"
    PATH_LINK_SKIPPED = "PATH_LINK_SKIPPED"
    PATH_EXCLUDED = "PATH_EXCLUDED"
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_COUNT_LIMIT_REACHED = "FILE_COUNT_LIMIT_REACHED"
    DEPTH_LIMIT_REACHED = "DEPTH_LIMIT_REACHED"
    FILE_READ_FAILURE = "FILE_READ_FAILURE"
    FILE_ENCODING_FAILURE = "FILE_ENCODING_FAILURE"
    FILE_SYNTAX_ERROR = "FILE_SYNTAX_ERROR"
    FILE_CHANGED_OR_MISSING = "FILE_CHANGED_OR_MISSING"
    UNSUPPORTED_GRAMMAR = "UNSUPPORTED_GRAMMAR"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"


SAFE_MESSAGES: dict[DiagnosticCode, str] = {
    DiagnosticCode.INVALID_PROJECT_ROOT: (
        "The project root is missing or is not a directory."
    ),
    DiagnosticCode.UNAUTHORIZED_ROOT: (
        "The project root is outside authorized locations."
    ),
    DiagnosticCode.PATH_TRAVERSAL_REJECTED: (
        "A path resolved outside the project root and was skipped."
    ),
    DiagnosticCode.PATH_LINK_SKIPPED: (
        "A symbolic link or reparse point was skipped by policy."
    ),
    DiagnosticCode.PATH_EXCLUDED: "A path was excluded by analysis policy.",
    DiagnosticCode.UNSUPPORTED_FILE: "A matched file type is not supported.",
    DiagnosticCode.FILE_TOO_LARGE: "A Python file exceeded the configured size limit.",
    DiagnosticCode.FILE_COUNT_LIMIT_REACHED: (
        "The configured Python file-count limit was reached."
    ),
    DiagnosticCode.DEPTH_LIMIT_REACHED: (
        "The configured traversal-depth limit was reached."
    ),
    DiagnosticCode.FILE_READ_FAILURE: "A Python file could not be read.",
    DiagnosticCode.FILE_ENCODING_FAILURE: (
        "A Python file has an unsupported or invalid source encoding."
    ),
    DiagnosticCode.FILE_SYNTAX_ERROR: (
        "A Python file contains invalid or incomplete syntax."
    ),
    DiagnosticCode.FILE_CHANGED_OR_MISSING: (
        "A Python file changed or disappeared during analysis."
    ),
    DiagnosticCode.UNSUPPORTED_GRAMMAR: (
        "The requested Python grammar is not supported by this runtime."
    ),
    DiagnosticCode.CANCELLATION_REQUESTED: (
        "Analysis was cancelled at a safe checkpoint."
    ),
}
