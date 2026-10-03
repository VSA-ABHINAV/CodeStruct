"""Unit tests for graph metrics computation and algorithm port adapter."""

from __future__ import annotations

import pytest
from codestruct.graph.enums import (
    Confidence,
    NodeKind,
    RelationshipKind,
    ResolutionStatus,
)
from codestruct.graph.metrics import (
    DefaultAlgorithmAdapter,
    NodeMetrics,
    enrich_nodes_with_metrics,
)
from codestruct.graph.model import GraphEdge, GraphNode, ResolutionRecord


def _dummy_node(node_id: str, name: str | None = None) -> GraphNode:
    return GraphNode(
        id=node_id,
        kind=NodeKind.CLASS,
        name=name or node_id,
        qualified_name=f"pkg.{name or node_id}",
    )


def _dummy_edge(
    edge_id: str,
    source_id: str,
    target_id: str,
    kind: RelationshipKind = RelationshipKind.CALLS,
) -> GraphEdge:
    return GraphEdge(
        id=edge_id,
        kind=kind,
        source_id=source_id,
        target_id=target_id,
        target_reference=None,
        resolution=ResolutionRecord(
            status=ResolutionStatus.RESOLVED,
            confidence=Confidence.HIGH,
            reason_code="test",
        ),
        evidence_ids=(),
    )


@pytest.mark.unit
def test_node_metrics_to_attributes():
    m = NodeMetrics(
        node_id="n1",
        fan_in=2,
        fan_out=3,
        instability=0.6,
        degree_centrality=0.5,
        in_cycle=False,
    )
    attrs = dict(m.to_attributes())
    assert attrs["fan_in"] == "2"
    assert attrs["fan_out"] == "3"
    assert attrs["instability"] == "0.60"
    assert attrs["centrality"] == "0.500"
    assert attrs["in_cycle"] == "false"


@pytest.mark.unit
def test_linear_dependency_chain_metrics():
    # A -> B -> C
    nodes = (_dummy_node("A"), _dummy_node("B"), _dummy_node("C"))
    edges = (
        _dummy_edge("e1", "A", "B", RelationshipKind.CALLS),
        _dummy_edge("e2", "B", "C", RelationshipKind.CALLS),
    )

    adapter = DefaultAlgorithmAdapter()
    results = adapter.compute_metrics(nodes, edges)

    # Node A: fan_in=0, fan_out=1, instability=1.0
    assert results["A"].fan_in == 0
    assert results["A"].fan_out == 1
    assert results["A"].instability == 1.0
    assert not results["A"].in_cycle

    # Node B: fan_in=1, fan_out=1, instability=0.5
    assert results["B"].fan_in == 1
    assert results["B"].fan_out == 1
    assert results["B"].instability == 0.5
    assert not results["B"].in_cycle

    # Node C: fan_in=1, fan_out=0, instability=0.0
    assert results["C"].fan_in == 1
    assert results["C"].fan_out == 0
    assert results["C"].instability == 0.0
    assert not results["C"].in_cycle


@pytest.mark.unit
def test_cycle_detection():
    # Cycle: X -> Y -> Z -> X, plus isolated W
    nodes = (_dummy_node("X"), _dummy_node("Y"), _dummy_node("Z"), _dummy_node("W"))
    edges = (
        _dummy_edge("e1", "X", "Y", RelationshipKind.IMPORTS),
        _dummy_edge("e2", "Y", "Z", RelationshipKind.CALLS),
        _dummy_edge("e3", "Z", "X", RelationshipKind.INHERITS),
    )

    adapter = DefaultAlgorithmAdapter()
    results = adapter.compute_metrics(nodes, edges)

    assert results["X"].in_cycle is True
    assert results["Y"].in_cycle is True
    assert results["Z"].in_cycle is True
    assert results["W"].in_cycle is False


@pytest.mark.unit
def test_enrich_nodes_attaches_attributes():
    nodes = (_dummy_node("A"), _dummy_node("B"))
    edges = (_dummy_edge("e1", "A", "B"),)

    enriched = enrich_nodes_with_metrics(nodes, edges)
    node_map = {n.id: dict(n.attributes) for n in enriched}

    assert "fan_in" in node_map["A"]
    assert node_map["A"]["fan_in"] == "0"
    assert node_map["A"]["fan_out"] == "1"
    assert node_map["B"]["fan_in"] == "1"
    assert node_map["B"]["fan_out"] == "0"
    assert "community" in node_map["A"]
    assert node_map["A"]["community"] == node_map["B"]["community"]


@pytest.mark.unit
def test_community_clusters_connected_components():
    # Two disjoint subgraphs: (A <-> B) and (C <-> D), plus isolate E
    nodes = (
        _dummy_node("A"),
        _dummy_node("B"),
        _dummy_node("C"),
        _dummy_node("D"),
        _dummy_node("E"),
    )
    edges = (
        _dummy_edge("e1", "A", "B", RelationshipKind.CALLS),
        _dummy_edge("e2", "C", "D", RelationshipKind.IMPORTS),
    )

    adapter = DefaultAlgorithmAdapter()
    results = adapter.compute_metrics(nodes, edges)

    # A and B are in one community
    assert results["A"].community_id == results["B"].community_id
    # C and D are in another community
    assert results["C"].community_id == results["D"].community_id
    # E is in its own community
    assert results["E"].community_id not in (
        results["A"].community_id,
        results["C"].community_id,
    )
    assert len({results[k].community_id for k in ("A", "C", "E")}) == 3
