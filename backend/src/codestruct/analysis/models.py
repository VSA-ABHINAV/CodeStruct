"""Immutable parser-boundary models; these are not graph models."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum

from .diagnostics import DiagnosticCode, DiagnosticSeverity


def stable_id(prefix: str, *parts: object) -> str:
    """Return a process-independent ID for an ordered semantic key."""

    encoded = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:24]}"


class DefinitionKind(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    METHOD = "method"
    ASYNC_METHOD = "async_method"


class ParameterKind(str, Enum):
    POSITIONAL_ONLY = "positional_only"
    POSITIONAL_OR_KEYWORD = "positional_or_keyword"
    VAR_POSITIONAL = "var_positional"
    KEYWORD_ONLY = "keyword_only"
    VAR_KEYWORD = "var_keyword"


class ImportKind(str, Enum):
    IMPORT = "import"
    FROM_IMPORT = "from_import"


class CallKind(str, Enum):
    DIRECT = "direct"
    ATTRIBUTE = "attribute"
    CHAINED_ATTRIBUTE = "chained_attribute"
    EXPRESSION = "expression"


class ResolutionStatus(str, Enum):
    SYNTACTIC_UNRESOLVED = "syntactic_unresolved"


@dataclass(frozen=True, slots=True, order=True)
class SourceSpan:
    start_line: int
    start_column: int
    end_line: int | None = None
    end_column: int | None = None


@dataclass(frozen=True, slots=True)
class SourceFile:
    id: str
    relative_path: str
    module_name: str
    is_package: bool
    size_bytes: int
    modified_ns: int
    device: int | None = field(default=None, repr=False)
    inode: int | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class ModuleMetadata:
    id: str
    name: str
    qualified_name: str
    source_file_id: str
    relative_path: str
    is_package: bool
    has_docstring: bool
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class DecoratorMetadata:
    id: str
    expression: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ParameterMetadata:
    id: str
    name: str
    kind: ParameterKind
    annotation: str | None
    has_default: bool
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ClassDefinition:
    id: str
    name: str
    qualified_name: str
    enclosing_scope_id: str
    span: SourceSpan
    decorators: tuple[DecoratorMetadata, ...] = ()
    has_docstring: bool = False


@dataclass(frozen=True, slots=True)
class FunctionDefinition:
    id: str
    name: str
    qualified_name: str
    kind: DefinitionKind
    enclosing_scope_id: str
    span: SourceSpan
    parameters: tuple[ParameterMetadata, ...] = ()
    decorators: tuple[DecoratorMetadata, ...] = ()
    return_annotation: str | None = None
    has_docstring: bool = False


@dataclass(frozen=True, slots=True)
class VariableDefinition:
    id: str
    name: str
    qualified_name: str
    enclosing_scope_id: str
    span: SourceSpan
    type_annotation: str | None = None
    value_expression: str | None = None
    is_constant: bool = False


@dataclass(frozen=True, slots=True)
class ImportAlias:
    name: str
    alias: str | None


@dataclass(frozen=True, slots=True)
class ImportStatement:
    id: str
    kind: ImportKind
    module: str | None
    relative_level: int
    names: tuple[ImportAlias, ...]
    enclosing_scope_id: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class InheritanceReference:
    id: str
    class_id: str
    expression: str
    expression_kind: str
    status: ResolutionStatus
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class CallSiteObservation:
    id: str
    expression: str
    kind: CallKind
    enclosing_scope_id: str
    enclosing_qualified_name: str
    status: ResolutionStatus
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ParserDiagnostic:
    id: str
    code: DiagnosticCode
    severity: DiagnosticSeverity
    message: str
    relative_path: str | None = None
    span: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class FileParseResult:
    source_file: SourceFile
    module: ModuleMetadata | None
    classes: tuple[ClassDefinition, ...] = ()
    functions: tuple[FunctionDefinition, ...] = ()
    variables: tuple[VariableDefinition, ...] = ()
    imports: tuple[ImportStatement, ...] = ()
    inheritance: tuple[InheritanceReference, ...] = ()
    calls: tuple[CallSiteObservation, ...] = ()
    diagnostics: tuple[ParserDiagnostic, ...] = ()
    encoding: str | None = None
    parsed: bool = False


@dataclass(frozen=True, slots=True)
class ProjectScanResult:
    root_name: str | None
    source_files: tuple[SourceFile, ...] = ()
    diagnostics: tuple[ParserDiagnostic, ...] = ()
    cancelled: bool = False
    limit_reached: bool = False


@dataclass(frozen=True, slots=True)
class ProjectParseResult:
    scan: ProjectScanResult
    files: tuple[FileParseResult, ...] = ()
    diagnostics: tuple[ParserDiagnostic, ...] = ()
    cancelled: bool = False

    @property
    def partial(self) -> bool:
        return bool(self.files) and (
            self.cancelled
            or self.scan.limit_reached
            or any(not result.parsed for result in self.files)
            or any(
                diagnostic.severity is DiagnosticSeverity.ERROR
                for diagnostic in self.diagnostics
            )
        )
