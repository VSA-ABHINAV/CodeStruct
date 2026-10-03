"""Transitional compatibility adapter for the characterized prototype API.

New code should consume ``codestruct.analysis`` models. These functions retain
the legacy dictionaries required by ``backend/main.py`` and existing consumers.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SOURCE_PACKAGE = Path(__file__).resolve().parent / "src"
if str(_SOURCE_PACKAGE) not in sys.path:
    sys.path.insert(0, str(_SOURCE_PACKAGE))

from codestruct.analysis.diagnostics import DiagnosticCode  # noqa: E402
from codestruct.analysis.models import (  # noqa: E402
    CallKind,
    DefinitionKind,
    FileParseResult,
    ImportKind,
)
from codestruct.analysis.policy import AnalysisPolicy  # noqa: E402
from codestruct.analysis.python_parser import (  # noqa: E402
    PythonAstParser,
    parse_project,
)
from codestruct.analysis.scanner import scan_project  # noqa: E402


def _unique(values):
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _raise_legacy_parse_failure(result: FileParseResult, file_path: Path) -> None:
    diagnostic = result.diagnostics[0] if result.diagnostics else None
    if diagnostic and diagnostic.code is DiagnosticCode.FILE_SYNTAX_ERROR:
        span = diagnostic.span
        location = (
            str(file_path),
            span.start_line if span else 1,
            span.start_column if span else 1,
            None,
        )
        raise SyntaxError(diagnostic.message, location)
    if diagnostic and diagnostic.code is DiagnosticCode.FILE_ENCODING_FAILURE:
        raise UnicodeError(diagnostic.message)
    if diagnostic and diagnostic.code is DiagnosticCode.FILE_TOO_LARGE:
        raise ValueError(diagnostic.message)
    raise OSError(
        diagnostic.message if diagnostic else "The Python file could not be parsed."
    )


def _legacy_projection(result: FileParseResult) -> dict:
    imports: list[str] = []
    for statement in result.imports:
        if statement.kind is ImportKind.IMPORT:
            imports.extend(alias.name for alias in statement.names)
        elif statement.module:
            imports.append(statement.module)

    inheritance = []
    classes_by_id = {definition.id: definition for definition in result.classes}
    for reference in result.inheritance:
        child = classes_by_id[reference.class_id].name
        if reference.expression_kind == "Name":
            parent = reference.expression
        elif reference.expression_kind == "Attribute":
            parent = reference.expression.rsplit(".", 1)[-1]
        else:
            continue
        inheritance.append({"child": child, "parent": parent})

    calls = []
    for observation in result.calls:
        if observation.kind is CallKind.DIRECT:
            calls.append({"type": "function", "name": observation.expression})
        elif observation.kind is CallKind.ATTRIBUTE:
            owner, function = observation.expression.rsplit(".", 1)
            calls.append({"type": "method", "object": owner, "function": function})

    functions = [
        definition.name
        for definition in result.functions
        if definition.kind in {DefinitionKind.FUNCTION, DefinitionKind.METHOD}
    ]
    return {
        "file": Path(result.source_file.relative_path).name,
        "imports": _unique(imports),
        "classes": _unique([definition.name for definition in result.classes]),
        "functions": _unique(functions),
        "inheritance": _unique(inheritance),
        "calls": _unique(calls),
    }


def analyze_file(file_path):
    path = Path(file_path).resolve(strict=True)
    policy = AnalysisPolicy(max_depth=0)
    scan = scan_project(path.parent, policy)
    source_file = next(
        (item for item in scan.source_files if item.relative_path == path.name), None
    )
    if source_file is None:
        raise OSError("The Python file could not be discovered safely.")
    result = PythonAstParser().parse(path.parent, source_file, policy)
    if not result.parsed:
        _raise_legacy_parse_failure(result, path)
    return _legacy_projection(result)


def analyze_project(project_path):
    root = Path(project_path).resolve(strict=True)
    policy = AnalysisPolicy(max_depth=0)
    result = parse_project(root, policy)
    projected = []
    for file_result in result.files:
        if not file_result.parsed:
            _raise_legacy_parse_failure(
                file_result, root / file_result.source_file.relative_path
            )
        projected.append(_legacy_projection(file_result))
    return projected


def create_dependency_graph(project_path):
    root = Path(project_path).resolve(strict=True)
    project_data = analyze_project(root)
    graph = []
    for file_data in project_data:
        current_file = file_data["file"]
        for imported_module in file_data["imports"]:
            dependency = imported_module.split(".")[0] + ".py"
            if (root / dependency).exists():
                relation = {
                    "source": current_file,
                    "target": dependency,
                    "type": "import",
                }
                if relation not in graph:
                    graph.append(relation)
    return graph
