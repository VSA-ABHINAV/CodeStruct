"""Stable graph-contract enumerations."""

from __future__ import annotations

from enum import Enum


class NodeKind(str, Enum):
    PROJECT = "project"
    DIRECTORY = "directory"
    FILE = "file"
    PACKAGE = "package"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    METHOD = "method"
    ASYNC_METHOD = "async_method"
    EXTERNAL_MODULE = "external_module"
    UNRESOLVED_SYMBOL = "unresolved_symbol"


class RelationshipKind(str, Enum):
    CONTAINS = "contains"
    DEFINES = "defines"
    IMPORTS = "imports"
    INHERITS = "inherits"
    CALLS = "calls"
    CONSTRUCTS = "constructs"
    REFERENCES = "references"


class ResolutionStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    SYNTACTIC_ONLY = "syntactic_only"


class EvidenceOrigin(str, Enum):
    SOURCE_AST = "source_ast"
    STATIC_RESOLUTION = "static_resolution"
    RUNTIME_TRACE = "runtime_trace"
    TYPE_INFERENCE = "type_inference"
    LLM_INFERENCE = "llm_inference"


class Confidence(str, Enum):
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticPhase(str, Enum):
    SCANNING = "scanning"
    PARSING = "parsing"
    RESOLVING = "resolving"
    BUILDING_GRAPH = "building_graph"
    VALIDATING = "validating"
