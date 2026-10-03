import time
from pathlib import Path

import pytest
from analyzer import analyze_file, analyze_project, create_dependency_graph
from codestruct.analysis.diagnostics import DiagnosticCode
from codestruct.analysis.models import (
    CallKind,
    DefinitionKind,
    FileParseResult,
    ImportKind,
    ParameterKind,
    ResolutionStatus,
    SourceFile,
)
from codestruct.analysis.policy import AnalysisPolicy
from codestruct.analysis.python_parser import (
    FileParseCache,
    PythonAstParser,
    parse_project,
)
from codestruct.analysis.scanner import scan_project

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARSER_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "parser_project"
SAMPLE_PROJECT = PROJECT_ROOT / "sample_project"


@pytest.fixture(scope="module")
def parsed_project():
    return parse_project(
        PARSER_FIXTURE,
        AnalysisPolicy(exclude_patterns=("generated/**",)),
    )


def _file(result, relative_path):
    return next(
        item for item in result.files if item.source_file.relative_path == relative_path
    )


def test_project_retains_valid_files_when_other_files_fail(parsed_project):
    codes_by_path = {
        (diagnostic.relative_path, diagnostic.code)
        for diagnostic in parsed_project.diagnostics
    }

    assert parsed_project.partial
    assert _file(parsed_project, "empty.py").parsed
    assert _file(parsed_project, "pkg/module.py").parsed
    assert ("syntax_error.py", DiagnosticCode.FILE_SYNTAX_ERROR) in codes_by_path
    assert (
        "invalid_encoding.py",
        DiagnosticCode.FILE_ENCODING_FAILURE,
    ) in codes_by_path
    syntax = next(
        diagnostic
        for diagnostic in parsed_project.diagnostics
        if diagnostic.code is DiagnosticCode.FILE_SYNTAX_ERROR
    )
    assert syntax.span.start_line == 1
    assert syntax.relative_path == "syntax_error.py"


def test_project_parse_is_deterministic_for_unchanged_input(parsed_project):
    repeated = parse_project(
        PARSER_FIXTURE,
        AnalysisPolicy(exclude_patterns=("generated/**",)),
    )

    assert repeated == parsed_project


def test_scope_aware_definitions_ids_spans_and_docstrings(parsed_project):
    result = _file(parsed_project, "pkg/module.py")
    classes = {item.qualified_name: item for item in result.classes}
    functions = {item.qualified_name: item for item in result.functions}

    assert result.source_file.id == "src_6ae6ba2c0b8bca91ff994d17"
    assert result.module.id == "mod_431bdb697f66e95d791f9282"
    assert result.module.has_docstring
    assert classes["pkg.module.Service"].id == "cls_6a8219d64118f84046043c43"
    assert classes["pkg.module.Service"].span.start_line == 10
    assert (
        classes["pkg.module.Service.Nested"].enclosing_scope_id
        == classes["pkg.module.Service"].id
    )
    assert functions["pkg.module.Service.method"].kind is DefinitionKind.METHOD
    assert functions["pkg.module.Service.method.local"].kind is DefinitionKind.FUNCTION
    assert (
        functions["pkg.module.Service.async_method"].kind is DefinitionKind.ASYNC_METHOD
    )
    assert functions["pkg.module.async_function"].kind is DefinitionKind.ASYNC_FUNCTION
    assert (
        functions["pkg.module.outer.inner"].enclosing_scope_id
        == functions["pkg.module.outer"].id
    )
    assert functions["pkg.module.Service.method"].has_docstring
    assert [item.expression for item in classes["pkg.module.Service"].decorators] == [
        "register('service')"
    ]


def test_import_metadata_preserves_aliases_levels_and_multiple_names(parsed_project):
    imports = _file(parsed_project, "pkg/module.py").imports

    assert [item.kind for item in imports] == [
        ImportKind.IMPORT,
        ImportKind.FROM_IMPORT,
        ImportKind.FROM_IMPORT,
        ImportKind.FROM_IMPORT,
    ]
    assert [(item.name, item.alias) for item in imports[0].names] == [
        ("os", None),
        ("sys", "system"),
    ]
    assert (imports[1].module, imports[1].relative_level) == ("other", 2)
    assert [(item.name, item.alias) for item in imports[1].names] == [
        ("duplicate", "other_duplicate")
    ]
    assert (imports[2].module, imports[2].relative_level) == (None, 1)
    assert [(item.name, item.alias) for item in imports[3].names] == [
        ("helper", "aliased_helper"),
        ("second", None),
    ]


def test_parameters_decorators_and_annotations_are_syntactic(parsed_project):
    functions = {
        item.qualified_name: item
        for item in _file(parsed_project, "pkg/module.py").functions
    }
    outer = functions["pkg.module.outer"]

    assert [(item.name, item.kind, item.has_default) for item in outer.parameters] == [
        ("positional_only", ParameterKind.POSITIONAL_ONLY, False),
        ("regular", ParameterKind.POSITIONAL_OR_KEYWORD, True),
        ("items", ParameterKind.VAR_POSITIONAL, False),
        ("named", ParameterKind.KEYWORD_ONLY, False),
        ("optional", ParameterKind.KEYWORD_ONLY, True),
        ("extras", ParameterKind.VAR_KEYWORD, False),
    ]
    method = functions["pkg.module.Service.method"]
    assert method.return_annotation == "str"
    assert method.parameters[1].annotation == "int"
    assert [item.expression for item in method.decorators] == ["classmethod"]


def test_calls_record_expression_span_and_enclosing_caller(parsed_project):
    calls = _file(parsed_project, "pkg/module.py").calls
    by_expression = {}
    for call in calls:
        by_expression.setdefault(call.expression, []).append(call)

    assert by_expression["direct"][0].kind is CallKind.DIRECT
    assert by_expression["client.send"][0].kind is CallKind.ATTRIBUTE
    assert by_expression["package.client.send"][0].kind is CallKind.CHAINED_ATTRIBUTE
    assert by_expression["factory().service.run"][0].kind is CallKind.CHAINED_ATTRIBUTE
    assert by_expression["direct"][0].enclosing_qualified_name == (
        "pkg.module.Service.method"
    )
    assert by_expression["nested_call"][0].enclosing_qualified_name == (
        "pkg.module.Service.method.local"
    )
    assert by_expression["direct"][0].span.start_line == 20
    assert all(call.status is ResolutionStatus.SYNTACTIC_UNRESOLVED for call in calls)


def test_inheritance_expressions_remain_unresolved(parsed_project):
    references = _file(parsed_project, "pkg/module.py").inheritance

    assert [(item.expression, item.expression_kind) for item in references] == [
        ("Base", "Name"),
        ("mixins.Named['service']", "Subscript"),
    ]
    assert all(
        item.status is ResolutionStatus.SYNTACTIC_UNRESOLVED for item in references
    )


@pytest.mark.parametrize(
    ("relative_path", "imported_name"),
    [
        ("circular_a.py", "circular_b"),
        ("circular_b.py", "circular_a"),
        ("missing_import.py", "dependency_that_is_not_present"),
    ],
)
def test_circular_and_missing_imports_remain_syntax_observations(
    parsed_project, relative_path, imported_name
):
    result = _file(parsed_project, relative_path)

    assert [(alias.name, alias.alias) for alias in result.imports[0].names] == [
        (imported_name, None)
    ]


def test_multibyte_columns_are_normalized_to_unicode_columns(parsed_project):
    result = _file(parsed_project, "unicode_source.py")

    assert result.calls[0].span.start_column == 5
    assert result.calls[0].span.end_column == 11


def test_parser_detects_file_removed_after_scan(tmp_path):
    source = tmp_path / "removed.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    scan = scan_project(tmp_path, AnalysisPolicy())
    source.unlink()

    result = PythonAstParser().parse(tmp_path, scan.source_files[0], AnalysisPolicy())

    assert not result.parsed
    assert result.diagnostics[0].code is DiagnosticCode.FILE_CHANGED_OR_MISSING


def test_parser_honors_cancellation_before_read():
    scan = scan_project(PARSER_FIXTURE / "pkg", AnalysisPolicy(max_depth=0))
    source_file = next(
        item for item in scan.source_files if item.relative_path == "module.py"
    )

    result = PythonAstParser().parse(
        PARSER_FIXTURE / "pkg",
        source_file,
        AnalysisPolicy(max_depth=0),
        cancellation_check=lambda: True,
    )

    assert not result.parsed
    assert result.diagnostics[0].code is DiagnosticCode.CANCELLATION_REQUESTED


def test_parser_maps_permission_failure_to_safe_diagnostic(tmp_path, monkeypatch):
    source = tmp_path / "denied.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    scan = scan_project(tmp_path, AnalysisPolicy())
    original_open = Path.open

    def denied(path, *args, **kwargs):
        if path == source:
            raise PermissionError("sensitive operating-system detail")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    result = PythonAstParser().parse(tmp_path, scan.source_files[0], AnalysisPolicy())

    assert result.diagnostics[0].code is DiagnosticCode.FILE_READ_FAILURE
    assert "sensitive" not in result.diagnostics[0].message
    assert str(tmp_path) not in result.diagnostics[0].message


def test_analyzed_fixture_is_never_executed(parsed_project):
    marker = PARSER_FIXTURE / "CODESTRUCT_FIXTURE_EXECUTED"

    assert _file(parsed_project, "side_effect.py").parsed
    assert not marker.exists()


def test_legacy_adapter_remains_compatible():
    assert {item["file"] for item in analyze_project(SAMPLE_PROJECT)} == {
        "database.py",
        "main.py",
        "user.py",
    }
    assert analyze_file(SAMPLE_PROJECT / "main.py")["calls"] == [
        {"type": "method", "object": "user", "function": "UserService"},
        {"type": "method", "object": "service", "function": "get_user"},
    ]
    assert create_dependency_graph(SAMPLE_PROJECT) == [
        {"source": "main.py", "target": "user.py", "type": "import"},
        {"source": "user.py", "target": "database.py", "type": "import"},
    ]


def test_module_and_class_variable_extraction(tmp_path):
    source = tmp_path / "vars.py"
    source.write_text(
        """
GLOBAL_CONST = 42
timeout: int = 10
untyped_var = "hello"

class Config:
    CLASS_CONST: str = "fixed"
    count = 0

    def compute(self, x):
        local_var = x + 1
        return local_var
""",
        encoding="utf-8",
    )
    scan = scan_project(tmp_path, AnalysisPolicy())
    result = PythonAstParser().parse(tmp_path, scan.source_files[0], AnalysisPolicy())

    assert result.parsed
    vars_by_name = {v.name: v for v in result.variables}
    assert "GLOBAL_CONST" in vars_by_name
    assert vars_by_name["GLOBAL_CONST"].is_constant
    assert vars_by_name["GLOBAL_CONST"].value_expression == "42"

    assert "timeout" in vars_by_name
    assert vars_by_name["timeout"].type_annotation == "int"
    assert vars_by_name["timeout"].value_expression == "10"

    assert "untyped_var" in vars_by_name
    assert not vars_by_name["untyped_var"].is_constant

    assert "CLASS_CONST" in vars_by_name
    assert vars_by_name["CLASS_CONST"].is_constant
    assert vars_by_name["CLASS_CONST"].type_annotation == "str"
    assert vars_by_name["CLASS_CONST"].qualified_name == "vars.Config.CLASS_CONST"

    assert "count" in vars_by_name
    assert vars_by_name["count"].qualified_name == "vars.Config.count"

    # Local variable inside function must NOT be captured
    assert "local_var" not in vars_by_name


def test_file_parse_cache_direct():
    cache = FileParseCache()
    assert len(cache) == 0
    assert cache.get("a.py", 10, 100) is None

    result = FileParseResult(
        source_file=SourceFile("id", "a.py", "a", False, 10, 100),
        module=None,
        parsed=True,
    )
    cache.put("a.py", 10, 100, result)
    assert len(cache) == 1
    assert cache.get("a.py", 10, 100) is result
    assert cache.get("a.py", 11, 100) is None  # size mismatch
    assert cache.get("a.py", 10, 101) is None  # mtime mismatch
    assert cache.get("b.py", 10, 100) is None  # path mismatch

    cache.clear()
    assert len(cache) == 0
    assert cache.get("a.py", 10, 100) is None


def test_parse_project_with_incremental_cache(tmp_path):
    f1 = tmp_path / "mod1.py"
    f1.write_text("X = 1\n", encoding="utf-8")
    f2 = tmp_path / "mod2.py"
    f2.write_text("Y = 2\n", encoding="utf-8")

    policy = AnalysisPolicy()
    cache = FileParseCache()

    # First parse: populate cache
    r1 = parse_project(tmp_path, policy, cache=cache)
    assert len(cache) == 2
    assert len(r1.files) == 2

    # Second parse: unchanged files hit cache (object identity preserved)
    r2 = parse_project(tmp_path, policy, cache=cache)
    assert len(r2.files) == 2
    assert r2.files[0] is r1.files[0]
    assert r2.files[1] is r1.files[1]

    # Modify mod1
    time.sleep(0.02)
    f1.write_text("X = 100\n", encoding="utf-8")
    r3 = parse_project(tmp_path, policy, cache=cache)
    assert len(r3.files) == 2
    f1_res = next(f for f in r3.files if f.source_file.relative_path == "mod1.py")
    f2_res = next(f for f in r3.files if f.source_file.relative_path == "mod2.py")
    assert f1_res is not r1.files[0]
    assert f1_res.variables[0].value_expression == "100"
    assert f2_res is r1.files[1]
