from dataclasses import replace
from pathlib import Path

import pytest
from analyzer import analyze_project, create_dependency_graph
from codestruct.analysis import AnalysisPolicy, parse_project
from codestruct.graph import (
    build_graph,
    graph_from_json,
    graph_to_dict,
    graph_to_json,
    validate_graph,
)
from codestruct.graph.enums import (
    EvidenceOrigin,
    NodeKind,
    RelationshipKind,
    ResolutionStatus,
)
from codestruct.graph.identifiers import edge_id, node_id

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "parser_project"
SAMPLE_PROJECT = PROJECT_ROOT / "sample_project"


@pytest.fixture(scope="module")
def parsed_project():
    return parse_project(
        GRAPH_FIXTURE,
        AnalysisPolicy(exclude_patterns=("generated/**",)),
    )


@pytest.fixture(scope="module")
def graph(parsed_project):
    return build_graph(parsed_project)


def _nodes(graph, qualified_name, kind=None):
    return tuple(
        item
        for item in graph.nodes
        if item.qualified_name == qualified_name and (kind is None or item.kind is kind)
    )


def _edges(graph, *, kind=None, source=None, target=None, reference=None):
    names = {item.id: item.qualified_name for item in graph.nodes}
    return tuple(
        item
        for item in graph.edges
        if (kind is None or item.kind is kind)
        and (source is None or names.get(item.source_id) == source)
        and (target is None or names.get(item.target_id) == target)
        and (reference is None or item.target_reference == reference)
    )


def test_stable_identifiers_ordering_and_serialization(parsed_project, graph):
    repeated = build_graph(parsed_project)

    assert repeated == graph
    assert graph_to_json(repeated) == graph_to_json(graph)
    assert [item.id for item in graph.nodes] == [
        item.id
        for item in sorted(
            graph.nodes,
            key=lambda value: (value.kind.value, value.qualified_name, value.id),
        )
    ]
    caller = _nodes(graph, "pkg.resolution.caller", NodeKind.FUNCTION)[0]
    repeated_call = _edges(
        graph,
        kind=RelationshipKind.CALLS,
        source="pkg.resolution.caller",
        target="pkg.resolution.local_function",
    )[0]
    assert caller.id == "n_dvsp47h5oialcux24yakvfhmpg"
    assert repeated_call.id == "e_5m2kmmuxfxvncmyfpaxx66bpun"
    assert node_id(NodeKind.MODULE, "pkg/module.py", "pkg.module").startswith("n_")
    assert edge_id(
        RelationshipKind.CALLS,
        "source",
        "target",
        ResolutionStatus.RESOLVED,
        "rule",
    ) == edge_id(
        RelationshipKind.CALLS,
        "source",
        "target",
        ResolutionStatus.RESOLVED,
        "rule",
    )


def test_duplicate_files_packages_and_nested_containment(graph):
    duplicates = _nodes(graph, "pkg.duplicate", NodeKind.MODULE) + _nodes(
        graph, "other.duplicate", NodeKind.MODULE
    )
    assert len(duplicates) == 2
    assert len({item.id for item in duplicates}) == 2

    package = _nodes(graph, "pkg", NodeKind.PACKAGE)[0]
    module = _nodes(graph, "pkg.resolution", NodeKind.MODULE)[0]
    assert module.parent_id == package.id
    assert _edges(
        graph,
        kind=RelationshipKind.CONTAINS,
        source="pkg",
        target="pkg.resolution",
    )
    nested_package = _nodes(graph, "pkg.subpkg", NodeKind.PACKAGE)[0]
    nested_module = _nodes(graph, "pkg.subpkg.module", NodeKind.MODULE)[0]
    assert nested_package.parent_id == package.id
    assert nested_module.parent_id == nested_package.id
    assert _edges(
        graph,
        kind=RelationshipKind.INHERITS,
        source="pkg.subpkg.module.NestedChild",
        target="pkg.base.ImportedBase",
    )


def test_import_resolution_preserves_kind_alias_and_missing_state(graph):
    relative_symbol = _edges(
        graph,
        kind=RelationshipKind.IMPORTS,
        source="pkg.resolution",
        target="pkg.base.imported_function",
    )[0]
    assert relative_symbol.resolution.status is ResolutionStatus.RESOLVED
    evidence_by_id = {item.id: item for item in graph.evidence}
    source_evidence = next(
        evidence_by_id[item]
        for item in relative_symbol.evidence_ids
        if evidence_by_id[item].origin is EvidenceOrigin.SOURCE_AST
    )
    assert source_evidence.location.path == "pkg/resolution.py"
    assert source_evidence.location.span.start_line == 1
    assert dict(relative_symbol.attributes) == {
        "alias": "imported",
        "import_kind": "symbol",
        "relative_level": "1",
    }

    module_alias = _edges(
        graph,
        kind=RelationshipKind.IMPORTS,
        source="pkg.resolution",
        target="pkg.base",
    )[0]
    assert dict(module_alias.attributes)["alias"] == "base_alias"
    assert dict(module_alias.attributes)["import_kind"] == "module"

    external = _edges(
        graph,
        kind=RelationshipKind.IMPORTS,
        source="pkg.module",
        target="os",
    )[0]
    assert external.resolution.status is ResolutionStatus.RESOLVED
    assert _nodes(graph, "os", NodeKind.EXTERNAL_MODULE)

    missing = _edges(
        graph,
        kind=RelationshipKind.IMPORTS,
        source="missing_import",
        reference="dependency_that_is_not_present",
    )[0]
    assert missing.resolution.status is ResolutionStatus.UNRESOLVED
    assert (
        dict(
            next(
                item for item in graph.nodes if item.id == missing.target_id
            ).attributes
        )["classification"]
        == "external_or_missing_module"
    )


def test_inheritance_resolution_and_cycles_are_conservative(graph):
    imported = _edges(
        graph,
        kind=RelationshipKind.INHERITS,
        source="pkg.resolution.Child",
        target="pkg.base.ImportedBase",
    )[0]
    assert imported.resolution.status is ResolutionStatus.RESOLVED

    assert _edges(
        graph,
        kind=RelationshipKind.INHERITS,
        source="pkg.resolution.CycleA",
        target="pkg.resolution.CycleB",
    )
    assert _edges(
        graph,
        kind=RelationshipKind.INHERITS,
        source="pkg.resolution.CycleB",
        target="pkg.resolution.CycleA",
    )
    assert sum(item.code == "INHERITANCE_CYCLE" for item in graph.diagnostics) == 2

    dynamic = _edges(
        graph,
        kind=RelationshipKind.INHERITS,
        source="pkg.module.Service",
        reference="mixins.Named['service']",
    )[0]
    assert dynamic.target_id is None
    assert dynamic.resolution.status is ResolutionStatus.SYNTACTIC_ONLY


@pytest.mark.parametrize(
    ("source", "target", "kind"),
    [
        (
            "pkg.resolution.caller",
            "pkg.resolution.local_function",
            RelationshipKind.CALLS,
        ),
        (
            "pkg.resolution.caller",
            "pkg.base.imported_function",
            RelationshipKind.CALLS,
        ),
        (
            "pkg.resolution.LocalClass.invoke",
            "pkg.resolution.LocalClass.method",
            RelationshipKind.CALLS,
        ),
        (
            "pkg.resolution.LocalClass.invoke_class",
            "pkg.resolution.LocalClass.method",
            RelationshipKind.CALLS,
        ),
        (
            "pkg.resolution.LocalClass.invoke",
            "pkg.resolution.LocalClass",
            RelationshipKind.CONSTRUCTS,
        ),
        (
            "pkg.resolution.outer_scope",
            "pkg.resolution.outer_scope.inner_scope",
            RelationshipKind.CALLS,
        ),
    ],
)
def test_supported_calls(source, target, kind, graph):
    relationships = _edges(graph, kind=kind, source=source, target=target)
    assert relationships
    assert all(
        item.resolution.status is ResolutionStatus.RESOLVED for item in relationships
    )


def test_ambiguous_chained_mutual_and_aggregated_calls(graph):
    ambiguous = _edges(
        graph,
        kind=RelationshipKind.CALLS,
        source="pkg.resolution.ambiguous_caller",
        reference="ambiguous",
    )[0]
    assert ambiguous.resolution.status is ResolutionStatus.AMBIGUOUS
    assert len(ambiguous.resolution.candidate_ids) == 2
    assert ambiguous.diagnostic_ids

    chained = _edges(
        graph,
        kind=RelationshipKind.CALLS,
        source="pkg.resolution.caller",
        reference="dynamic.factory().run",
    )[0]
    assert chained.resolution.status is ResolutionStatus.SYNTACTIC_ONLY
    assert chained.target_id is None

    assert _edges(
        graph,
        kind=RelationshipKind.CALLS,
        source="pkg.resolution.mutual_a",
        target="pkg.resolution.mutual_b",
    )
    assert _edges(
        graph,
        kind=RelationshipKind.CALLS,
        source="pkg.resolution.mutual_b",
        target="pkg.resolution.mutual_a",
    )

    repeated = _edges(
        graph,
        kind=RelationshipKind.CALLS,
        source="pkg.resolution.caller",
        target="pkg.resolution.local_function",
    )[0]
    assert repeated.occurrence_count == 2
    assert len(repeated.evidence_ids) == 4


def test_partial_graph_evidence_spans_counts_and_round_trip(graph):
    assert graph.metadata.partial
    assert "file_parse_failure" in graph.metadata.partial_reasons
    assert _nodes(graph, "syntax_error.py", NodeKind.FILE)
    assert {"FILE_SYNTAX_ERROR", "FILE_ENCODING_FAILURE"} <= {
        item.code for item in graph.diagnostics
    }
    assert all(item.evidence_ids for item in graph.edges)
    assert all(
        item.location.path.startswith(("pkg/", "other/", "deep/"))
        or "/" not in item.location.path
        for item in graph.evidence
        if item.location
    )
    assert EvidenceOrigin.RUNTIME_TRACE not in {item.origin for item in graph.evidence}
    assert EvidenceOrigin.TYPE_INFERENCE not in {item.origin for item in graph.evidence}
    assert EvidenceOrigin.LLM_INFERENCE not in {item.origin for item in graph.evidence}
    assert graph.summary.nodes_total == len(graph.nodes)
    assert graph.summary.edges_total == len(graph.edges)
    assert graph.summary.evidence_total == len(graph.evidence)
    assert graph.summary.diagnostics_total == len(graph.diagnostics)
    assert graph_from_json(graph_to_json(graph)) == graph


def test_validation_reports_corrupt_endpoint_and_containment_cycle(graph):
    first = graph.edges[0]
    missing = replace(first, target_id="n_missing")
    report = validate_graph(replace(graph, edges=(missing, *graph.edges[1:])))
    assert not report.valid
    assert "MISSING_EDGE_TARGET" in {item.code for item in report.diagnostics}

    project = _nodes(graph, "project", NodeKind.PROJECT)[0]
    package = _nodes(graph, "pkg", NodeKind.PACKAGE)[0]
    cycle_edge = replace(
        first,
        id="e_test_containment_cycle",
        kind=RelationshipKind.CONTAINS,
        source_id=package.id,
        target_id=project.id,
        target_reference=None,
        resolution=replace(
            first.resolution,
            status=ResolutionStatus.NOT_APPLICABLE,
        ),
    )
    report = validate_graph(replace(graph, edges=(*graph.edges, cycle_edge)))
    assert "CONTAINMENT_CYCLE" in {item.code for item in report.diagnostics}


def test_serialization_does_not_leak_absolute_paths(graph):
    serialized = graph_to_json(graph)
    payload = graph_to_dict(graph)

    assert str(PROJECT_ROOT) not in serialized
    assert "D:\\" not in serialized
    assert payload["schema_version"] == "1.0.0"
    assert all("position" not in node for node in payload["nodes"])


def test_analysis_pipeline_never_executes_fixture_source():
    marker = GRAPH_FIXTURE / "CODESTRUCT_FIXTURE_EXECUTED"
    parsed = parse_project(
        GRAPH_FIXTURE,
        AnalysisPolicy(exclude_patterns=("generated/**",)),
    )
    graph = build_graph(parsed)
    graph_to_json(graph)

    assert graph.nodes
    assert not marker.exists()


def test_legacy_analyzer_contract_remains_unchanged():
    assert {item["file"] for item in analyze_project(SAMPLE_PROJECT)} == {
        "database.py",
        "main.py",
        "user.py",
    }
    assert create_dependency_graph(SAMPLE_PROJECT) == [
        {"source": "main.py", "target": "user.py", "type": "import"},
        {"source": "user.py", "target": "database.py", "type": "import"},
    ]
