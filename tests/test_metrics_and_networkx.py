"""Focused tests for metrics calculation, iterative cycle detection, community clustering, module metrics, and NetworkX parity (CS-009, CS-010)."""

from codestruct.graph.enums import (
    Confidence,
    NodeKind,
    RelationshipKind,
    ResolutionStatus,
)
from codestruct.graph.metrics import (
    DefaultAlgorithmAdapter,
    NetworkXAlgorithmAdapter,
    enrich_nodes_with_metrics,
    get_algorithm_port,
)
from codestruct.graph.model import GraphEdge, GraphNode, ResolutionRecord


def _make_node(
    nid: str,
    name: str,
    kind: NodeKind = NodeKind.FUNCTION,
    module_id: str | None = None,
) -> GraphNode:
    return GraphNode(
        id=nid,
        kind=kind,
        name=name,
        qualified_name=name,
        parent_id="proj",
        module_id=module_id,
        attributes=(),
    )


def _make_edge(
    eid: str,
    src: str,
    tgt: str,
    kind: RelationshipKind = RelationshipKind.CALLS,
    status: ResolutionStatus = ResolutionStatus.RESOLVED,
) -> GraphEdge:
    return GraphEdge(
        id=eid,
        kind=kind,
        source_id=src,
        target_id=tgt,
        target_reference=None,
        resolution=ResolutionRecord(
            status=status,
            confidence=Confidence.EXACT
            if status is ResolutionStatus.RESOLVED
            else Confidence.UNKNOWN,
            reason_code="TEST_CALL",
        ),
        evidence_ids=(),
        attributes=(),
    )


def test_networkx_and_default_adapter_parity():
    """CS-009/CS-010: Verify DefaultAlgorithmAdapter and NetworkXAlgorithmAdapter compute identical metrics."""
    nodes = tuple(_make_node(f"node_{i}", f"func_{i}") for i in range(6))
    edges = (
        # Cycle between 0 and 1
        _make_edge("e01", "node_0", "node_1", RelationshipKind.CALLS),
        _make_edge("e10", "node_1", "node_0", RelationshipKind.CALLS),
        # 1 calls 2
        _make_edge("e12", "node_1", "node_2", RelationshipKind.CALLS),
        # 3 calls 2 and 4
        _make_edge("e32", "node_3", "node_2", RelationshipKind.CALLS),
        _make_edge("e34", "node_3", "node_4", RelationshipKind.CALLS),
        # Containment edge (DEFINES) - should NOT affect fan-in / fan-out
        _make_edge(
            "e_def",
            "node_0",
            "node_5",
            RelationshipKind.DEFINES,
            ResolutionStatus.NOT_APPLICABLE,
        ),
        # Self-loop on node_5 (CALLS)
        _make_edge("e_self", "node_5", "node_5", RelationshipKind.CALLS),
    )

    default_adapter = DefaultAlgorithmAdapter()
    nx_adapter = NetworkXAlgorithmAdapter()

    metrics_default = default_adapter.compute_metrics(nodes, edges)
    metrics_nx = nx_adapter.compute_metrics(nodes, edges)

    assert set(metrics_default.keys()) == set(metrics_nx.keys())
    for nid in metrics_default:
        d = metrics_default[nid]
        x = metrics_nx[nid]
        assert d.node_id == x.node_id
        assert d.fan_in == x.fan_in, (
            f"fan_in mismatch for {nid}: default={d.fan_in} nx={x.fan_in}"
        )
        assert d.fan_out == x.fan_out, (
            f"fan_out mismatch for {nid}: default={d.fan_out} nx={x.fan_out}"
        )
        assert d.instability == x.instability, (
            f"instability mismatch for {nid}: default={d.instability} nx={x.instability}"
        )
        assert d.degree_centrality == x.degree_centrality, (
            f"centrality mismatch for {nid}: default={d.degree_centrality} nx={x.degree_centrality}"
        )
        assert d.in_cycle == x.in_cycle, (
            f"in_cycle mismatch for {nid}: default={d.in_cycle} nx={x.in_cycle}"
        )
        assert d.component_id == x.component_id, (
            f"component_id mismatch for {nid}: default={d.component_id} nx={x.component_id}"
        )
        assert d.community_id == x.community_id, (
            f"community_id mismatch for {nid}: default={d.community_id} nx={x.community_id}"
        )

    # Specific semantic checks:
    # node_0 and node_1 participate in cycle
    assert metrics_default["node_0"].in_cycle is True
    assert metrics_default["node_1"].in_cycle is True
    # node_5 has a self-loop -> in_cycle is True
    assert metrics_default["node_5"].in_cycle is True
    # node_2, node_3, node_4 not in cycle
    assert metrics_default["node_2"].in_cycle is False
    assert metrics_default["node_3"].in_cycle is False
    assert metrics_default["node_4"].in_cycle is False

    # node_5 has DEFINES from node_0, but fan_in should be 0 because DEFINES is non-dependency
    assert metrics_default["node_5"].fan_in == 0
    assert metrics_default["node_5"].fan_out == 0  # self-loop excluded from fan_out


def test_resolved_edge_filtering_and_unresolved_exclusion():
    """CS-010: Verify unresolved, ambiguous, syntactic-only, and containment edges do not count towards coupling."""
    nodes = (
        _make_node("a", "func_a"),
        _make_node("b", "func_b"),
        _make_node("c", "func_c"),
    )
    edges = (
        # a calls b (RESOLVED) -> fan_out(a)=1, fan_in(b)=1
        _make_edge(
            "e_resolved", "a", "b", RelationshipKind.CALLS, ResolutionStatus.RESOLVED
        ),
        # a calls c (UNRESOLVED) -> should NOT count
        _make_edge(
            "e_unresolved",
            "a",
            "c",
            RelationshipKind.CALLS,
            ResolutionStatus.UNRESOLVED,
        ),
        # b calls c (AMBIGUOUS) -> should NOT count
        _make_edge(
            "e_ambiguous", "b", "c", RelationshipKind.CALLS, ResolutionStatus.AMBIGUOUS
        ),
        # c imports a (SYNTACTIC_ONLY) -> should NOT count
        _make_edge(
            "e_syntactic",
            "c",
            "a",
            RelationshipKind.IMPORTS,
            ResolutionStatus.SYNTACTIC_ONLY,
        ),
        # c contains b (CONTAINS, NOT_APPLICABLE) -> should NOT count
        _make_edge(
            "e_contains",
            "c",
            "b",
            RelationshipKind.CONTAINS,
            ResolutionStatus.NOT_APPLICABLE,
        ),
    )

    for adapter in (DefaultAlgorithmAdapter(), NetworkXAlgorithmAdapter()):
        metrics = adapter.compute_metrics(nodes, edges)
        assert metrics["a"].fan_out == 1, (
            f"a fan_out should only count resolved call to b, got {metrics['a'].fan_out}"
        )
        assert metrics["a"].fan_in == 0, (
            f"a fan_in should be 0, got {metrics['a'].fan_in}"
        )
        assert metrics["b"].fan_in == 1, (
            f"b fan_in should be 1 from resolved call, got {metrics['b'].fan_in}"
        )
        assert metrics["b"].fan_out == 0, (
            f"b fan_out should be 0 (ambiguous ignored), got {metrics['b'].fan_out}"
        )
        assert metrics["c"].fan_in == 0, (
            f"c fan_in should be 0, got {metrics['c'].fan_in}"
        )
        assert metrics["c"].fan_out == 0, (
            f"c fan_out should be 0, got {metrics['c'].fan_out}"
        )


def test_weak_bridge_community_vs_component_separation():
    """CS-009/CS-010: A connected graph with a weak bridge must prove community detection is not merely component detection."""
    # Graph: Two triangles (0-1-2) and (3-4-5) joined by a single bridge edge (2-3)
    nodes = tuple(_make_node(f"node_{i}", f"func_{i}") for i in range(6))
    edges = (
        # Triangle 1: 0, 1, 2
        _make_edge("e01", "node_0", "node_1", RelationshipKind.CALLS),
        _make_edge("e12", "node_1", "node_2", RelationshipKind.CALLS),
        _make_edge("e20", "node_2", "node_0", RelationshipKind.CALLS),
        # Triangle 2: 3, 4, 5
        _make_edge("e34", "node_3", "node_4", RelationshipKind.CALLS),
        _make_edge("e45", "node_4", "node_5", RelationshipKind.CALLS),
        _make_edge("e53", "node_5", "node_3", RelationshipKind.CALLS),
        # Weak Bridge: 2 -> 3
        _make_edge("e23_bridge", "node_2", "node_3", RelationshipKind.CALLS),
    )

    default_adapter = DefaultAlgorithmAdapter()
    nx_adapter = NetworkXAlgorithmAdapter()

    m_default = default_adapter.compute_metrics(nodes, edges)
    m_nx = nx_adapter.compute_metrics(nodes, edges)

    # 1. Connected component check: All 6 nodes must belong to the SAME connected component
    assert len({m_default[f"node_{i}"].component_id for i in range(6)}) == 1
    assert len({m_nx[f"node_{i}"].component_id for i in range(6)}) == 1

    # 2. Community detection check: The graph must be split into TWO communities across the weak bridge
    comm_default_t1 = {m_default[f"node_{i}"].community_id for i in (0, 1, 2)}
    comm_default_t2 = {m_default[f"node_{i}"].community_id for i in (3, 4, 5)}
    assert len(comm_default_t1) == 1, (
        f"Triangle 1 must be in 1 community, got {comm_default_t1}"
    )
    assert len(comm_default_t2) == 1, (
        f"Triangle 2 must be in 1 community, got {comm_default_t2}"
    )
    assert comm_default_t1 != comm_default_t2, (
        "Triangle 1 and Triangle 2 must belong to distinct communities across the weak bridge!"
    )

    # NetworkX adapter must also split them into distinct communities
    comm_nx_t1 = {m_nx[f"node_{i}"].community_id for i in (0, 1, 2)}
    comm_nx_t2 = {m_nx[f"node_{i}"].community_id for i in (3, 4, 5)}
    assert len(comm_nx_t1) == 1
    assert len(comm_nx_t2) == 1
    assert comm_nx_t1 != comm_nx_t2

    # Parity check between Default and NetworkX
    for i in range(6):
        nid = f"node_{i}"
        assert m_default[nid].component_id == m_nx[nid].component_id
        assert m_default[nid].community_id == m_nx[nid].community_id


def test_module_architecture_metrics():
    """CS-009/CS-010: Verify module-level coupling (Ca, Ce), instability, cohesion, and relational density."""
    mod_a = _make_node("mod_a", "pkg.mod_a", NodeKind.MODULE)
    mod_b = _make_node("mod_b", "pkg.mod_b", NodeKind.MODULE)
    mod_c = _make_node("mod_c", "pkg.mod_c", NodeKind.MODULE)  # Empty module
    func_a1 = _make_node("fa1", "fa1", NodeKind.FUNCTION, module_id="mod_a")
    func_a2 = _make_node("fa2", "fa2", NodeKind.FUNCTION, module_id="mod_a")
    func_b1 = _make_node("fb1", "fb1", NodeKind.FUNCTION, module_id="mod_b")

    nodes = (mod_a, mod_b, mod_c, func_a1, func_a2, func_b1)
    edges = (
        # Internal edge within mod_a: fa1 -> fa2
        _make_edge("e_internal", "fa1", "fa2", RelationshipKind.CALLS),
        # External edge: fa2 -> fb1 (mod_a -> mod_b)
        _make_edge("e_external", "fa2", "fb1", RelationshipKind.CALLS),
    )

    adapter = DefaultAlgorithmAdapter()
    metrics = adapter.compute_metrics(nodes, edges)

    # Check mod_a metrics:
    # Contained entities: {fa1, fa2} -> 2 entities
    # Internal edges: 1 (fa1 -> fa2)
    # External incoming: 0 (Ca = 0)
    # External outgoing: 1 (Ce = 1, targeting fb1)
    # Instability = 1 / (0 + 1) = 1.0
    # Cohesion = 1 / (2 * 1) = 0.50 (50% internal density)
    # Relational density = (1 + 0 + 1) / 2 = 1.00
    m_a = metrics["mod_a"]
    assert m_a.afferent_coupling == 0
    assert m_a.efferent_coupling == 1
    assert m_a.module_instability == 1.0
    assert m_a.cohesion == 0.50
    assert m_a.relational_density == 1.00

    # Check mod_b metrics:
    # Contained entities: {fb1} -> 1 entity
    # Internal edges: 0
    # External incoming: 1 (Ca = 1, from fa2)
    # External outgoing: 0 (Ce = 0)
    # Instability = 0 / 1 = 0.0
    # Cohesion = 1.0 (single entity represents unified module cohesion)
    # Relational density = (0 + 1 + 0) / 1 = 1.00
    m_b = metrics["mod_b"]
    assert m_b.afferent_coupling == 1
    assert m_b.efferent_coupling == 0
    assert m_b.module_instability == 0.0
    assert m_b.cohesion == 1.0
    assert m_b.relational_density == 1.00

    # Check mod_c (empty module container) metrics:
    # Contained entities: {} -> 0 entities
    # Cohesion = 0.0, Relational density = 0.0
    m_c = metrics["mod_c"]
    assert m_c.afferent_coupling == 0
    assert m_c.efferent_coupling == 0
    assert m_c.module_instability == 0.0
    assert m_c.cohesion == 0.0
    assert m_c.relational_density == 0.0


def test_small_graph_community_parity_corpus():
    """CS-009/CS-010: Exhaustive small-graph parity corpus testing Default vs NetworkX community partitions."""
    from itertools import combinations

    def _partition(res: dict) -> frozenset[frozenset[str]]:
        groups: dict[int, set[str]] = {}
        for nid, item in res.items():
            groups.setdefault(item.community_id, set()).add(nid)
        return frozenset(frozenset(group) for group in groups.values())

    default_adapter = DefaultAlgorithmAdapter()
    nx_adapter = NetworkXAlgorithmAdapter()

    # 1. Exhaustively verify all 64 4-node graphs and all 1024 5-node graphs
    for node_count in (4, 5):
        pairs = list(combinations(range(node_count), 2))
        nodes = tuple(
            _make_node(str(index), f"n_{index}") for index in range(node_count)
        )
        for mask in range(1 << len(pairs)):
            edges = tuple(
                _make_edge(
                    f"e{index}", str(source), str(target), RelationshipKind.CALLS
                )
                for index, (source, target) in enumerate(pairs)
                if mask & (1 << index)
            )
            part_def = _partition(default_adapter.compute_metrics(nodes, edges))
            part_nx = _partition(nx_adapter.compute_metrics(nodes, edges))
            assert part_def == part_nx, (
                f"Parity mismatch for {node_count} nodes, mask {mask}: def={part_def} nx={part_nx}"
            )

    # 2. Named multi-cluster and barbell topologies on 6 nodes
    test_cases = [
        (
            "barbell_6",
            6,
            [
                ("0", "1"),
                ("1", "2"),
                ("2", "0"),
                ("2", "3"),
                ("3", "4"),
                ("4", "5"),
                ("5", "3"),
            ],
        ),
        (
            "disconnected_6",
            6,
            [("0", "1"), ("1", "2"), ("2", "0"), ("3", "4"), ("4", "5")],
        ),
    ]

    for name, n_nodes, edge_pairs in test_cases:
        nodes = tuple(_make_node(str(i), f"n_{i}") for i in range(n_nodes))
        edges = tuple(
            _make_edge(f"e_{u}_{v}", str(u), str(v), RelationshipKind.CALLS)
            for u, v in edge_pairs
        )
        part_def = _partition(default_adapter.compute_metrics(nodes, edges))
        part_nx = _partition(nx_adapter.compute_metrics(nodes, edges))
        assert part_def == part_nx, (
            f"Parity mismatch for '{name}': def={part_def} nx={part_nx}"
        )


def test_iterative_tarjan_deep_recursion_resilience():
    """CS-010: Ensure iterative Tarjan's SCC handles deep call chains (1000 nodes) without recursion limit errors."""
    n = 1000
    nodes = tuple(_make_node(f"node_{i}", f"func_{i}") for i in range(n))
    # Long chain 0 -> 1 -> 2 -> ... -> 999 -> 0 (huge cycle)
    edges = tuple(
        _make_edge(
            f"e_{i}",
            f"node_{i}",
            f"node_{(i + 1) % n}",
            RelationshipKind.CALLS,
        )
        for i in range(n)
    )

    adapter = DefaultAlgorithmAdapter()
    metrics = adapter.compute_metrics(nodes, edges)

    assert len(metrics) == n
    for i in range(n):
        m = metrics[f"node_{i}"]
        assert m.in_cycle is True
        assert m.fan_in == 1
        assert m.fan_out == 1
        assert m.instability == 0.5


def test_enrich_nodes_with_metrics_port_fallback():
    """Test get_algorithm_port and enrich_nodes_with_metrics."""
    port_default = get_algorithm_port("default")
    assert isinstance(port_default, DefaultAlgorithmAdapter)
    port_nx = get_algorithm_port("networkx")
    assert isinstance(port_nx, NetworkXAlgorithmAdapter)
    port_auto = get_algorithm_port()
    assert isinstance(port_auto, (NetworkXAlgorithmAdapter, DefaultAlgorithmAdapter))

    nodes = (_make_node("a", "func_a"), _make_node("b", "func_b"))
    edges = (_make_edge("e1", "a", "b", RelationshipKind.CALLS),)
    enriched = enrich_nodes_with_metrics(nodes, edges, port=port_auto)

    assert len(enriched) == 2
    attrs_a = dict(enriched[0].attributes)
    assert attrs_a["fan_out"] == "1"
    assert attrs_a["fan_in"] == "0"
    assert attrs_a["in_cycle"] == "false"
    assert attrs_a["component"] == "1"
    assert attrs_a["community"] == "1"


def test_algorithm_port_fallback_when_networkx_missing(monkeypatch):
    """CS-009: Test deterministic fallback to DefaultAlgorithmAdapter when NetworkX extra is absent."""
    import builtins

    import pytest

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "networkx" or name.startswith("networkx."):
            raise ModuleNotFoundError("No module named 'networkx'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    # 1. Auto selection falls back cleanly to DefaultAlgorithmAdapter
    port_auto = get_algorithm_port()
    assert isinstance(port_auto, DefaultAlgorithmAdapter)

    # 2. Explicit 'default' returns DefaultAlgorithmAdapter
    port_def = get_algorithm_port("default")
    assert isinstance(port_def, DefaultAlgorithmAdapter)

    # 3. Explicit 'networkx' raises RuntimeError explaining missing extra
    with pytest.raises(RuntimeError, match="NetworkX extra is not installed"):
        get_algorithm_port("networkx")

    # 4. Enriched metrics run cleanly through fallback adapter
    nodes = (_make_node("a", "func_a"), _make_node("b", "func_b"))
    edges = (_make_edge("e1", "a", "b", RelationshipKind.CALLS),)
    enriched = enrich_nodes_with_metrics(nodes, edges)
    assert len(enriched) == 2
    attrs_a = dict(enriched[0].attributes)
    assert attrs_a["fan_out"] == "1"
    assert attrs_a["community"] == "1"
