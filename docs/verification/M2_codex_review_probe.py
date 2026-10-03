"""Independent probes for canonical M2 contracts and metric filtering."""

from pathlib import Path
from tempfile import TemporaryDirectory

from codestruct.analysis import AnalysisPolicy, parse_project
from codestruct.analysis.llm_summary import extract_node_context
from codestruct.graph import build_graph, graph_to_dict
from codestruct.graph.enums import (
    Confidence,
    NodeKind,
    RelationshipKind,
    ResolutionStatus,
)
from codestruct.graph.metrics import DefaultAlgorithmAdapter
from codestruct.graph.model import GraphEdge, GraphNode, ResolutionRecord

with TemporaryDirectory(prefix="codestruct-m2-review-") as directory:
    root = Path(directory)
    (root / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
    graph = graph_to_dict(
        build_graph(parse_project(root, AnalysisPolicy(authorized_roots=(root,))))
    )
    target = next(node for node in graph["nodes"] if node["name"] == "target")
    context = extract_node_context(graph, target["id"])
    print("Canonical location:", target["location"])
    print(
        "Extracted path/line/end_line:",
        context.file_path,
        context.line,
        context.end_line,
    )
    assert context.file_path == "app.py", f"Expected app.py, got {context.file_path}"
    assert context.line == 1, f"Expected start line 1, got {context.line}"
    assert context.end_line == 2, f"Expected end line 2, got {context.end_line}"
    assert isinstance(context.evidence, list), "Context evidence must be a list"

nodes = (
    GraphNode(id="a", kind=NodeKind.FUNCTION, name="a", qualified_name="a"),
    GraphNode(id="b", kind=NodeKind.FUNCTION, name="b", qualified_name="b"),
)
unresolved = GraphEdge(
    id="unresolved",
    kind=RelationshipKind.CALLS,
    source_id="a",
    target_id="b",
    target_reference="b",
    resolution=ResolutionRecord(
        status=ResolutionStatus.UNRESOLVED,
        confidence=Confidence.UNKNOWN,
        reason_code="REVIEW_PROBE",
    ),
    evidence_ids=(),
)
metrics = DefaultAlgorithmAdapter().compute_metrics(nodes, (unresolved,))
print(
    "Unresolved target counted fan_out/fan_in:",
    metrics["a"].fan_out,
    metrics["b"].fan_in,
)
assert metrics["a"].fan_out == 0, (
    f"Unresolved edge must not contribute to fan_out: {metrics['a'].fan_out}"
)
assert metrics["b"].fan_in == 0, (
    f"Unresolved edge must not contribute to fan_in: {metrics['b'].fan_in}"
)
print("M2 Review Probe: All assertions passed successfully.")
