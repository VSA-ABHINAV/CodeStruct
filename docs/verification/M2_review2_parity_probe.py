"""Independent M2 review probe for community-adapter parity."""

from itertools import combinations

from codestruct.graph.enums import (
    Confidence,
    NodeKind,
    RelationshipKind,
    ResolutionStatus,
)
from codestruct.graph.metrics import DefaultAlgorithmAdapter, NetworkXAlgorithmAdapter
from codestruct.graph.model import GraphEdge, GraphNode, ResolutionRecord


def _node(node_id: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        kind=NodeKind.FUNCTION,
        name=node_id,
        qualified_name=node_id,
        parent_id="project",
        attributes=(),
    )


def _edge(edge_id: str, source_id: str, target_id: str) -> GraphEdge:
    return GraphEdge(
        id=edge_id,
        kind=RelationshipKind.CALLS,
        source_id=source_id,
        target_id=target_id,
        target_reference=None,
        resolution=ResolutionRecord(
            status=ResolutionStatus.RESOLVED,
            confidence=Confidence.EXACT,
            reason_code="M2_REVIEW_2",
        ),
        evidence_ids=(),
        attributes=(),
    )


def _partition(metrics: dict) -> frozenset[frozenset[str]]:
    groups: dict[int, set[str]] = {}
    for node_id, item in metrics.items():
        groups.setdefault(item.community_id, set()).add(node_id)
    return frozenset(frozenset(group) for group in groups.values())


for node_count in (4, 5):
    pairs = list(combinations(range(node_count), 2))
    nodes = tuple(_node(str(index)) for index in range(node_count))
    for mask in range(1 << len(pairs)):
        edges = tuple(
            _edge(f"e{index}", str(source), str(target))
            for index, (source, target) in enumerate(pairs)
            if mask & (1 << index)
        )
        default_partition = _partition(
            DefaultAlgorithmAdapter().compute_metrics(nodes, edges)
        )
        networkx_partition = _partition(
            NetworkXAlgorithmAdapter().compute_metrics(nodes, edges)
        )
        printed_edges = [
            (str(source), str(target))
            for index, (source, target) in enumerate(pairs)
            if mask & (1 << index)
        ]
        assert default_partition == networkx_partition, (
            f"Community mismatch for {node_count} nodes, mask {mask}, "
            f"edges {printed_edges}: default={sorted(map(sorted, default_partition))}, "
            f"networkx={sorted(map(sorted, networkx_partition))}"
        )
    print(f"Checked all {1 << len(pairs)} labeled graphs on {node_count} nodes")
