"""Scope-aware Python AST extraction without importing or executing source."""

from __future__ import annotations

import ast
import io
import os
import stat as stat_module
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .diagnostics import SAFE_MESSAGES, DiagnosticCode, DiagnosticSeverity
from .models import (
    CallKind,
    CallSiteObservation,
    ClassDefinition,
    DecoratorMetadata,
    DefinitionKind,
    FileParseResult,
    FunctionDefinition,
    ImportAlias,
    ImportKind,
    ImportStatement,
    InheritanceReference,
    ModuleMetadata,
    ParameterKind,
    ParameterMetadata,
    ParserDiagnostic,
    ProjectParseResult,
    ResolutionStatus,
    SourceFile,
    SourceSpan,
    VariableDefinition,
    stable_id,
)
from .policy import AnalysisPolicy
from .scanner import CancellationCheck, scan_project


@dataclass(frozen=True, slots=True)
class _Scope:
    id: str
    qualified_name: str
    kind: DefinitionKind | None


def _safe_message(
    code: DiagnosticCode,
    severity: DiagnosticSeverity,
    relative_path: str | None,
    span: SourceSpan | None = None,
) -> ParserDiagnostic:
    return ParserDiagnostic(
        id=stable_id(
            "diag",
            code.value,
            relative_path or "",
            span.start_line if span else "",
            span.start_column if span else "",
        ),
        code=code,
        severity=severity,
        message=SAFE_MESSAGES[code],
        relative_path=relative_path,
        span=span,
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        normalized_path = os.path.normcase(os.fspath(path))
        normalized_root = os.path.normcase(os.fspath(root))
        return os.path.commonpath((normalized_path, normalized_root)) == normalized_root
    except ValueError:
        return False


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(flag and getattr(path.lstat(), "st_file_attributes", 0) & flag)
    except OSError:
        return False


def _resolve_source(
    root: Path, source_file: SourceFile
) -> tuple[Path | None, DiagnosticCode | None]:
    relative = PurePosixPath(source_file.relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        return None, DiagnosticCode.PATH_TRAVERSAL_REJECTED
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if _is_link_or_reparse(current):
            return None, DiagnosticCode.PATH_LINK_SKIPPED
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None, DiagnosticCode.FILE_CHANGED_OR_MISSING
    if not _is_within(resolved, root):
        return None, DiagnosticCode.PATH_TRAVERSAL_REJECTED
    return resolved, None


class _Extractor(ast.NodeVisitor):
    def __init__(self, source_file: SourceFile, source: str) -> None:
        self.source_file = source_file
        self.lines = source.splitlines()
        module_id = stable_id("mod", source_file.relative_path, source_file.module_name)
        self.module_id = module_id
        self.scopes = [_Scope(module_id, source_file.module_name, None)]
        self.classes: list[ClassDefinition] = []
        self.functions: list[FunctionDefinition] = []
        self.variables: list[VariableDefinition] = []
        self.imports: list[ImportStatement] = []
        self.inheritance: list[InheritanceReference] = []
        self.calls: list[CallSiteObservation] = []

    @property
    def scope(self) -> _Scope:
        return self.scopes[-1]

    def _column(self, line_number: int, byte_offset: int) -> int:
        if line_number < 1 or line_number > len(self.lines):
            return max(1, byte_offset + 1)
        encoded = self.lines[line_number - 1].encode("utf-8")
        prefix = encoded[: max(0, byte_offset)]
        return len(prefix.decode("utf-8", errors="ignore")) + 1

    def span(self, node: ast.AST) -> SourceSpan:
        start_line = int(getattr(node, "lineno", 1))
        start_offset = int(getattr(node, "col_offset", 0))
        end_line = getattr(node, "end_lineno", None)
        end_offset = getattr(node, "end_col_offset", None)
        return SourceSpan(
            start_line=start_line,
            start_column=self._column(start_line, start_offset),
            end_line=int(end_line) if end_line is not None else None,
            end_column=(
                self._column(int(end_line), int(end_offset))
                if end_line is not None and end_offset is not None
                else None
            ),
        )

    @staticmethod
    def expression(node: ast.AST | None) -> str | None:
        if node is None:
            return None
        try:
            return " ".join(ast.unparse(node).split())
        except (ValueError, TypeError):
            return type(node).__name__

    def decorators(
        self, nodes: list[ast.expr], owner_key: str
    ) -> tuple[DecoratorMetadata, ...]:
        return tuple(
            DecoratorMetadata(
                id=stable_id(
                    "dec",
                    self.source_file.relative_path,
                    owner_key,
                    self.expression(node),
                    self.span(node).start_line,
                    self.span(node).start_column,
                ),
                expression=self.expression(node) or type(node).__name__,
                span=self.span(node),
            )
            for node in nodes
        )

    def parameters(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        owner_id: str,
    ) -> tuple[ParameterMetadata, ...]:
        result: list[ParameterMetadata] = []
        positional = [*node.args.posonlyargs, *node.args.args]
        first_default = len(positional) - len(node.args.defaults)

        def add(argument: ast.arg, kind: ParameterKind, has_default: bool) -> None:
            span = self.span(argument)
            result.append(
                ParameterMetadata(
                    id=stable_id(
                        "par",
                        owner_id,
                        argument.arg,
                        kind.value,
                        span.start_line,
                        span.start_column,
                    ),
                    name=argument.arg,
                    kind=kind,
                    annotation=self.expression(argument.annotation),
                    has_default=has_default,
                    span=span,
                )
            )

        for index, argument in enumerate(node.args.posonlyargs):
            add(argument, ParameterKind.POSITIONAL_ONLY, index >= first_default)
        offset = len(node.args.posonlyargs)
        for index, argument in enumerate(node.args.args, start=offset):
            add(argument, ParameterKind.POSITIONAL_OR_KEYWORD, index >= first_default)
        if node.args.vararg is not None:
            add(node.args.vararg, ParameterKind.VAR_POSITIONAL, False)
        for argument, default in zip(
            node.args.kwonlyargs, node.args.kw_defaults, strict=True
        ):
            add(argument, ParameterKind.KEYWORD_ONLY, default is not None)
        if node.args.kwarg is not None:
            add(node.args.kwarg, ParameterKind.VAR_KEYWORD, False)
        return tuple(result)

    def visit_Import(self, node: ast.Import) -> None:
        span = self.span(node)
        aliases = tuple(ImportAlias(item.name, item.asname) for item in node.names)
        self.imports.append(
            ImportStatement(
                id=stable_id(
                    "imp",
                    self.source_file.relative_path,
                    self.scope.id,
                    "import",
                    *(f"{item.name}:{item.asname or ''}" for item in node.names),
                    span.start_line,
                    span.start_column,
                ),
                kind=ImportKind.IMPORT,
                module=None,
                relative_level=0,
                names=aliases,
                enclosing_scope_id=self.scope.id,
                span=span,
            )
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        span = self.span(node)
        aliases = tuple(ImportAlias(item.name, item.asname) for item in node.names)
        self.imports.append(
            ImportStatement(
                id=stable_id(
                    "imp",
                    self.source_file.relative_path,
                    self.scope.id,
                    "from",
                    node.level,
                    node.module or "",
                    *(f"{item.name}:{item.asname or ''}" for item in node.names),
                    span.start_line,
                    span.start_column,
                ),
                kind=ImportKind.FROM_IMPORT,
                module=node.module,
                relative_level=node.level,
                names=aliases,
                enclosing_scope_id=self.scope.id,
                span=span,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        span = self.span(node)
        qualified_name = f"{self.scope.qualified_name}.{node.name}"
        class_id = stable_id(
            "cls",
            self.source_file.relative_path,
            qualified_name,
            span.start_line,
            span.start_column,
        )
        self.classes.append(
            ClassDefinition(
                id=class_id,
                name=node.name,
                qualified_name=qualified_name,
                enclosing_scope_id=self.scope.id,
                span=span,
                decorators=self.decorators(node.decorator_list, class_id),
                has_docstring=ast.get_docstring(node, clean=False) is not None,
            )
        )
        for base in node.bases:
            base_span = self.span(base)
            self.inheritance.append(
                InheritanceReference(
                    id=stable_id(
                        "base",
                        class_id,
                        self.expression(base),
                        base_span.start_line,
                        base_span.start_column,
                    ),
                    class_id=class_id,
                    expression=self.expression(base) or type(base).__name__,
                    expression_kind=type(base).__name__,
                    status=ResolutionStatus.SYNTACTIC_UNRESOLVED,
                    span=base_span,
                )
            )
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        for type_parameter in getattr(node, "type_params", ()):
            self.visit(type_parameter)
        self.scopes.append(_Scope(class_id, qualified_name, DefinitionKind.CLASS))
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_async: bool,
    ) -> None:
        span = self.span(node)
        parent_is_class = self.scope.kind is DefinitionKind.CLASS
        if parent_is_class:
            kind = DefinitionKind.ASYNC_METHOD if is_async else DefinitionKind.METHOD
        else:
            kind = (
                DefinitionKind.ASYNC_FUNCTION if is_async else DefinitionKind.FUNCTION
            )
        qualified_name = f"{self.scope.qualified_name}.{node.name}"
        function_id = stable_id(
            "fn",
            self.source_file.relative_path,
            kind.value,
            qualified_name,
            span.start_line,
            span.start_column,
        )
        self.functions.append(
            FunctionDefinition(
                id=function_id,
                name=node.name,
                qualified_name=qualified_name,
                kind=kind,
                enclosing_scope_id=self.scope.id,
                span=span,
                parameters=self.parameters(node, function_id),
                decorators=self.decorators(node.decorator_list, function_id),
                return_annotation=self.expression(node.returns),
                has_docstring=ast.get_docstring(node, clean=False) is not None,
            )
        )
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in node.args.defaults:
            self.visit(default)
        for keyword_default in node.args.kw_defaults:
            if keyword_default is not None:
                self.visit(keyword_default)
        for argument in [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]:
            if argument.annotation is not None:
                self.visit(argument.annotation)
        if node.args.vararg is not None and node.args.vararg.annotation is not None:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
            self.visit(node.args.kwarg.annotation)
        if node.returns is not None:
            self.visit(node.returns)
        for type_parameter in getattr(node, "type_params", ()):
            self.visit(type_parameter)
        self.scopes.append(_Scope(function_id, qualified_name, kind))
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, True)

    def visit_Call(self, node: ast.Call) -> None:
        span = self.span(node)
        expression = self.expression(node.func) or type(node.func).__name__
        if isinstance(node.func, ast.Name):
            kind = CallKind.DIRECT
        elif isinstance(node.func, ast.Attribute):
            kind = (
                CallKind.ATTRIBUTE
                if isinstance(node.func.value, ast.Name)
                else CallKind.CHAINED_ATTRIBUTE
            )
        else:
            kind = CallKind.EXPRESSION
        self.calls.append(
            CallSiteObservation(
                id=stable_id(
                    "call",
                    self.source_file.relative_path,
                    self.scope.id,
                    expression,
                    span.start_line,
                    span.start_column,
                ),
                expression=expression,
                kind=kind,
                enclosing_scope_id=self.scope.id,
                enclosing_qualified_name=self.scope.qualified_name,
                status=ResolutionStatus.SYNTACTIC_UNRESOLVED,
                span=span,
            )
        )
        self.generic_visit(node)

    def _extract_names(self, node: ast.AST) -> list[ast.Name]:
        if isinstance(node, ast.Name):
            return [node]
        if isinstance(node, (ast.Tuple, ast.List)):
            result: list[ast.Name] = []
            for elt in node.elts:
                result.extend(self._extract_names(elt))
            return result
        return []

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.scope.kind is None or self.scope.kind is DefinitionKind.CLASS:
            value_expr = self.expression(node.value)
            for target in node.targets:
                for name_node in self._extract_names(target):
                    name = name_node.id
                    qualified_name = f"{self.scope.qualified_name}.{name}"
                    var_span = self.span(name_node)
                    var_id = stable_id(
                        "var",
                        self.source_file.relative_path,
                        qualified_name,
                        var_span.start_line,
                        var_span.start_column,
                    )
                    self.variables.append(
                        VariableDefinition(
                            id=var_id,
                            name=name,
                            qualified_name=qualified_name,
                            enclosing_scope_id=self.scope.id,
                            span=var_span,
                            type_annotation=None,
                            value_expression=value_expr,
                            is_constant=name.isupper(),
                        )
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self.scope.kind is None or self.scope.kind is DefinitionKind.CLASS:
            for name_node in self._extract_names(node.target):
                name = name_node.id
                qualified_name = f"{self.scope.qualified_name}.{name}"
                var_span = self.span(name_node)
                annotation_expr = self.expression(node.annotation)
                value_expr = (
                    self.expression(node.value) if node.value is not None else None
                )
                is_const = name.isupper() or (
                    annotation_expr is not None and "Final" in annotation_expr
                )
                var_id = stable_id(
                    "var",
                    self.source_file.relative_path,
                    qualified_name,
                    var_span.start_line,
                    var_span.start_column,
                )
                self.variables.append(
                    VariableDefinition(
                        id=var_id,
                        name=name,
                        qualified_name=qualified_name,
                        enclosing_scope_id=self.scope.id,
                        span=var_span,
                        type_annotation=annotation_expr,
                        value_expression=value_expr,
                        is_constant=is_const,
                    )
                )
        self.generic_visit(node)


class PythonAstParser:
    """Parser adapter that emits syntax metadata and never resolves relationships."""

    def parse(
        self,
        project_root: str | os.PathLike[str],
        source_file: SourceFile,
        policy: AnalysisPolicy,
        cancellation_check: CancellationCheck | None = None,
    ) -> FileParseResult:
        if cancellation_check and cancellation_check():
            diagnostic = _safe_message(
                DiagnosticCode.CANCELLATION_REQUESTED,
                DiagnosticSeverity.WARNING,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))

        try:
            root = Path(project_root).resolve(strict=True)
        except (OSError, RuntimeError):
            diagnostic = _safe_message(
                DiagnosticCode.INVALID_PROJECT_ROOT,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))
        absolute_path, path_error = _resolve_source(root, source_file)
        if path_error is not None or absolute_path is None:
            diagnostic = _safe_message(
                path_error or DiagnosticCode.FILE_CHANGED_OR_MISSING,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))

        if policy.source_grammar is not None and policy.source_grammar > (
            sys.version_info.major,
            sys.version_info.minor,
        ):
            diagnostic = _safe_message(
                DiagnosticCode.UNSUPPORTED_GRAMMAR,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))

        try:
            with absolute_path.open("rb") as handle:
                before = os.fstat(handle.fileno())
                identity_changed = (
                    before.st_size != source_file.size_bytes
                    or before.st_mtime_ns != source_file.modified_ns
                    or (
                        source_file.device not in (None, 0)
                        and getattr(before, "st_dev", None) != source_file.device
                    )
                    or (
                        source_file.inode not in (None, 0)
                        and getattr(before, "st_ino", None) != source_file.inode
                    )
                )
                if identity_changed:
                    raise FileNotFoundError
                data = handle.read(policy.max_file_size + 1)
                after = os.fstat(handle.fileno())
            current = absolute_path.stat()
        except FileNotFoundError:
            diagnostic = _safe_message(
                DiagnosticCode.FILE_CHANGED_OR_MISSING,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))
        except (OSError, RuntimeError):
            diagnostic = _safe_message(
                DiagnosticCode.FILE_READ_FAILURE,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))

        if len(data) > policy.max_file_size:
            diagnostic = _safe_message(
                DiagnosticCode.FILE_TOO_LARGE,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or current.st_size != after.st_size
            or current.st_mtime_ns != after.st_mtime_ns
        ):
            diagnostic = _safe_message(
                DiagnosticCode.FILE_CHANGED_OR_MISSING,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))

        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
            source = data.decode(encoding)
        except (SyntaxError, UnicodeDecodeError, LookupError):
            diagnostic = _safe_message(
                DiagnosticCode.FILE_ENCODING_FAILURE,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))

        try:
            feature_version = policy.source_grammar
            tree = ast.parse(
                source,
                filename=source_file.relative_path,
                type_comments=True,
                feature_version=feature_version,
            )
        except SyntaxError as error:
            start_line = max(1, error.lineno or 1)
            start_column = max(1, error.offset or 1)
            span = SourceSpan(
                start_line,
                start_column,
                error.end_lineno,
                error.end_offset,
            )
            diagnostic = _safe_message(
                DiagnosticCode.FILE_SYNTAX_ERROR,
                DiagnosticSeverity.ERROR,
                source_file.relative_path,
                span,
            )
            return FileParseResult(source_file, None, diagnostics=(diagnostic,))

        extractor = _Extractor(source_file, source)
        extractor.visit(tree)
        source_lines = source.splitlines()
        line_count = max(1, len(source_lines))
        final_line = source_lines[-1] if source_lines else ""
        module = ModuleMetadata(
            id=extractor.module_id,
            name=source_file.module_name.rsplit(".", 1)[-1],
            qualified_name=source_file.module_name,
            source_file_id=source_file.id,
            relative_path=source_file.relative_path,
            is_package=source_file.is_package,
            has_docstring=ast.get_docstring(tree, clean=False) is not None,
            span=SourceSpan(1, 1, line_count, len(final_line) + 1),
        )

        def order(item):
            return (item.span.start_line, item.span.start_column, item.id)

        return FileParseResult(
            source_file=source_file,
            module=module,
            classes=tuple(sorted(extractor.classes, key=order)),
            functions=tuple(sorted(extractor.functions, key=order)),
            variables=tuple(sorted(extractor.variables, key=order)),
            imports=tuple(sorted(extractor.imports, key=order)),
            inheritance=tuple(sorted(extractor.inheritance, key=order)),
            calls=tuple(sorted(extractor.calls, key=order)),
            encoding=encoding,
            parsed=True,
        )


class FileParseCache:
    """In-memory mtime/size based cache for FileParseResult to bypass unchanged files."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[int, int, FileParseResult]] = {}

    def get(
        self, relative_path: str, size_bytes: int, modified_ns: int
    ) -> FileParseResult | None:
        entry = self._entries.get(relative_path)
        if entry is not None:
            cached_size, cached_mtime, result = entry
            if cached_size == size_bytes and cached_mtime == modified_ns:
                return result
        return None

    def put(
        self,
        relative_path: str,
        size_bytes: int,
        modified_ns: int,
        result: FileParseResult,
    ) -> None:
        self._entries[relative_path] = (size_bytes, modified_ns, result)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


def parse_project(
    project_root: str | os.PathLike[str],
    policy: AnalysisPolicy,
    cancellation_check: CancellationCheck | None = None,
    parser: PythonAstParser | None = None,
    cache: FileParseCache | None = None,
) -> ProjectParseResult:
    """Scan and parse a project while retaining valid per-file results."""

    scan = scan_project(project_root, policy, cancellation_check)
    if not scan.source_files:
        return ProjectParseResult(
            scan=scan,
            diagnostics=scan.diagnostics,
            cancelled=scan.cancelled,
        )
    canonical_root = Path(project_root).resolve(strict=True)
    adapter = parser or PythonAstParser()
    files: list[FileParseResult] = []
    diagnostics = list(scan.diagnostics)
    cancelled = scan.cancelled
    for source_file in scan.source_files:
        if cancellation_check and cancellation_check():
            diagnostics.append(
                _safe_message(
                    DiagnosticCode.CANCELLATION_REQUESTED,
                    DiagnosticSeverity.WARNING,
                    source_file.relative_path,
                )
            )
            cancelled = True
            break
        if cache is not None:
            cached = cache.get(
                source_file.relative_path,
                source_file.size_bytes,
                source_file.modified_ns,
            )
            if cached is not None:
                files.append(cached)
                diagnostics.extend(cached.diagnostics)
                continue
        result = adapter.parse(
            canonical_root,
            source_file,
            policy,
            cancellation_check,
        )
        if cache is not None and result.parsed:
            cache.put(
                source_file.relative_path,
                source_file.size_bytes,
                source_file.modified_ns,
                result,
            )
        files.append(result)
        diagnostics.extend(result.diagnostics)
        if any(
            diagnostic.code is DiagnosticCode.CANCELLATION_REQUESTED
            for diagnostic in result.diagnostics
        ):
            cancelled = True
            break
    return ProjectParseResult(
        scan=scan,
        files=tuple(files),
        diagnostics=tuple(diagnostics),
        cancelled=cancelled,
    )
