"""Graph metric computation and algorithm adapters conforming to ADR-002.

Architecture Policy:
- Primary Adapter: NetworkXAlgorithmAdapter (used when networkx is installed).
- Fallback Adapter: DefaultAlgorithmAdapter (deterministic pure-Python implementation).
- Port Isolation: GraphAlgorithmPort returns immutable NodeMetrics; no NetworkX objects leak
  into graph models, storage, cache, or API boundaries.
- Edge Policy: Only resolved static dependencies (RelationshipKind in DEPENDENCY_KINDS,
  ResolutionStatus.RESOLVED, src != tgt) are counted in fan-in/fan-out coupling, centrality,
  cycles, communities, components, and module metrics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

from .enums import NodeKind, RelationshipKind, ResolutionStatus
from .model import Attribute, GraphEdge, GraphNode


@dataclass(frozen=True, slots=True)
class NodeMetrics:
    """Computed structural metrics for a graph node."""

    node_id: str
    fan_in: int
    fan_out: int
    instability: float
    degree_centrality: float
    in_cycle: bool
    component_id: int = 1
    community_id: int = 1
    afferent_coupling: int | None = None
    efferent_coupling: int | None = None
    module_instability: float | None = None
    cohesion: float | None = None
    relational_density: float | None = None

    def to_attributes(self) -> tuple[Attribute, ...]:
        attrs: list[Attribute] = [
            ("centrality", f"{self.degree_centrality:.3f}"),
            ("community", str(self.community_id)),
            ("component", str(self.component_id)),
            ("fan_in", str(self.fan_in)),
            ("fan_out", str(self.fan_out)),
            ("in_cycle", "true" if self.in_cycle else "false"),
            ("instability", f"{self.instability:.2f}"),
        ]
        if self.afferent_coupling is not None:
            attrs.append(("ca", str(self.afferent_coupling)))
        if self.efferent_coupling is not None:
            attrs.append(("ce", str(self.efferent_coupling)))
        if self.module_instability is not None:
            attrs.append(("module_instability", f"{self.module_instability:.2f}"))
        if self.cohesion is not None:
            attrs.append(("cohesion", f"{self.cohesion:.2f}"))
        if self.relational_density is not None:
            attrs.append(("relational_density", f"{self.relational_density:.2f}"))
        return tuple(sorted(attrs))


class GraphAlgorithmPort(Protocol):
    """Port for computing approved graph metrics without leaking engine objects."""

    def compute_metrics(
        self,
        nodes: tuple[GraphNode, ...],
        edges: tuple[GraphEdge, ...],
    ) -> dict[str, NodeMetrics]: ...


DEPENDENCY_KINDS = frozenset(
    {
        RelationshipKind.IMPORTS,
        RelationshipKind.CALLS,
        RelationshipKind.INHERITS,
        RelationshipKind.CONSTRUCTS,
        RelationshipKind.REFERENCES,
    }
)


def _compute_module_metrics(
    nodes: tuple[GraphNode, ...],
    node_ids: set[str],
    dep_out_adjacency: dict[str, set[str]],
    dep_in_adjacency: dict[str, set[str]],
) -> dict[str, dict[str, Any]]:
    """Compute afferent/efferent coupling, instability, cohesion, and relational density for modules."""
    module_of: dict[str, str] = {}
    module_nodes: set[str] = set()

    for node in nodes:
        if node.kind in (NodeKind.MODULE, NodeKind.PACKAGE):
            module_nodes.add(node.id)
            module_of[node.id] = node.id
        elif node.module_id and node.module_id in node_ids:
            module_of[node.id] = node.module_id
        elif node.parent_id and node.parent_id in node_ids:
            module_of[node.id] = node.parent_id

    module_members: dict[str, set[str]] = defaultdict(set)
    for nid, mod_id in module_of.items():
        module_members[mod_id].add(nid)

    results: dict[str, dict[str, Any]] = {}
    for mod_id in module_nodes:
        # Contained program entities (functions, classes, methods) excluding the container itself
        all_module_entities = module_members.get(mod_id, {mod_id})
        contained_entities = {n for n in all_module_entities if n != mod_id}
        n_contained = len(contained_entities)

        # External incoming: external nodes targeting any entity in the module or container
        ext_in: set[str] = set()
        for member in all_module_entities:
            for caller in dep_in_adjacency.get(member, ()):
                if caller not in all_module_entities:
                    ext_in.add(caller)

        # External outgoing: any entity in the module or container targeting external nodes
        ext_out: set[str] = set()
        for member in all_module_entities:
            for callee in dep_out_adjacency.get(member, ()):
                if callee not in all_module_entities:
                    ext_out.add(callee)

        ca = len(ext_in)
        ce = len(ext_out)
        instability = ce / (ca + ce) if (ca + ce) > 0 else 0.0

        # Internal edges: dependency edges strictly between contained program entities
        internal_edges_count = 0
        for member in contained_entities:
            for callee in dep_out_adjacency.get(member, ()):
                if callee in contained_entities:
                    internal_edges_count += 1

        # Cohesion denominator uses contained program entities
        if n_contained > 1:
            cohesion = internal_edges_count / (n_contained * (n_contained - 1))
        elif n_contained == 1:
            cohesion = 1.0
        else:
            cohesion = 0.0

        relational_density = (internal_edges_count + ca + ce) / max(1, n_contained)

        results[mod_id] = {
            "ca": ca,
            "ce": ce,
            "module_instability": round(instability, 2),
            "cohesion": round(cohesion, 2),
            "relational_density": round(relational_density, 2),
        }

    return results


class DefaultAlgorithmAdapter:
    """Pure-Python, deterministic graph metric computer."""

    def compute_metrics(
        self,
        nodes: tuple[GraphNode, ...],
        edges: tuple[GraphEdge, ...],
    ) -> dict[str, NodeMetrics]:
        node_ids = {node.id for node in nodes}
        total_nodes = len(node_ids)
        denominator = max(1, total_nodes - 1)

        dep_out_adjacency: dict[str, set[str]] = defaultdict(set)
        dep_in_adjacency: dict[str, set[str]] = defaultdict(set)
        undirected_dep: dict[str, set[str]] = defaultdict(set)
        self_loops: set[str] = set()

        for edge in edges:
            src = edge.source_id
            tgt = edge.target_id
            if (
                src in node_ids
                and tgt is not None
                and tgt in node_ids
                and edge.kind in DEPENDENCY_KINDS
                and edge.resolution.status is ResolutionStatus.RESOLVED
            ):
                if src == tgt:
                    self_loops.add(src)
                else:
                    dep_out_adjacency[src].add(tgt)
                    dep_in_adjacency[tgt].add(src)
                    undirected_dep[src].add(tgt)
                    undirected_dep[tgt].add(src)

        # Detect nodes involved in directed dependency cycles via iterative Tarjan's SCC
        cycle_nodes = _find_cycle_nodes(dep_out_adjacency, node_ids, self_loops)

        # Detect connected components
        components = _detect_components(undirected_dep, node_ids)

        # Detect actual community clusters (deterministic greedy modularity)
        communities = _detect_communities(undirected_dep, node_ids, components)

        # Compute module-level architecture metrics
        mod_metrics = _compute_module_metrics(
            nodes, node_ids, dep_out_adjacency, dep_in_adjacency
        )

        metrics: dict[str, NodeMetrics] = {}
        for node in nodes:
            nid = node.id
            fin = len(dep_in_adjacency.get(nid, ()))
            fout = len(dep_out_adjacency.get(nid, ()))
            deg_sum = fin + fout

            instability = fout / deg_sum if deg_sum > 0 else 0.0
            centrality = deg_sum / denominator if total_nodes > 1 else 0.0

            mm = mod_metrics.get(nid)

            metrics[nid] = NodeMetrics(
                node_id=nid,
                fan_in=fin,
                fan_out=fout,
                instability=round(instability, 2),
                degree_centrality=round(centrality, 3),
                in_cycle=nid in cycle_nodes,
                component_id=components.get(nid, 1),
                community_id=communities.get(nid, 1),
                afferent_coupling=mm["ca"] if mm else None,
                efferent_coupling=mm["ce"] if mm else None,
                module_instability=mm["module_instability"] if mm else None,
                cohesion=mm["cohesion"] if mm else None,
                relational_density=mm["relational_density"] if mm else None,
            )

        return metrics


def _detect_components(
    undirected_adj: dict[str, set[str]],
    all_nodes: set[str],
) -> dict[str, int]:
    """Group connected nodes into deterministic connected components."""
    visited: set[str] = set()
    components: dict[str, int] = {}
    comp_id = 1

    for start in sorted(all_nodes):
        if start not in visited:
            queue = [start]
            visited.add(start)
            comp_nodes: list[str] = []
            while queue:
                current = queue.pop(0)
                comp_nodes.append(current)
                for neighbor in sorted(undirected_adj.get(current, ())):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            for nid in comp_nodes:
                components[nid] = comp_id
            comp_id += 1
    return components


def _detect_communities(
    undirected_adj: dict[str, set[str]],
    all_nodes: set[str],
    components: dict[str, int],
) -> dict[str, int]:
    """Detect deterministic community clusters within connected components using greedy modularity."""
    comp_to_nodes: dict[int, list[str]] = defaultdict(list)
    for nid, cid in components.items():
        comp_to_nodes[cid].append(nid)

    community_assignments: dict[str, int] = {}
    comm_counter = 1

    for cid in sorted(comp_to_nodes):
        comp_nodes = sorted(comp_to_nodes[cid])
        subgraph_nodes = set(comp_nodes)
        total_edges = (
            sum(len(undirected_adj.get(n, set()) & subgraph_nodes) for n in comp_nodes)
            // 2
        )

        if len(comp_nodes) <= 3 or total_edges == 0:
            for nid in comp_nodes:
                community_assignments[nid] = comm_counter
            comm_counter += 1
            continue

        # Pure Python Greedy Modularity Optimization (Clauset-Newman-Moore)
        m = float(total_edges)
        comms: dict[int, set[str]] = {i: {n} for i, n in enumerate(comp_nodes)}
        node_to_c = {n: i for i, n in enumerate(comp_nodes)}
        degrees = {
            i: len(undirected_adj.get(n, set()) & subgraph_nodes)
            for i, n in enumerate(comp_nodes)
        }
        comm_edges: dict[tuple[int, int], int] = {}
        for u in comp_nodes:
            cu = node_to_c[u]
            for v in sorted(undirected_adj.get(u, set()) & subgraph_nodes):
                cv = node_to_c[v]
                if cu < cv:
                    comm_edges[(cu, cv)] = comm_edges.get((cu, cv), 0) + 1

        while len(comms) > 1:
            best_dq = -float("inf")
            best_pair = None
            for (cu, cv), e_uv in sorted(comm_edges.items()):
                if e_uv <= 0:
                    continue
                dq = (e_uv / m) - (degrees[cu] * degrees[cv]) / (2.0 * m * m)
                if dq > best_dq + 1e-12:
                    best_dq = dq
                    best_pair = (cu, cv)
                elif abs(dq - best_dq) <= 1e-12:
                    if best_pair is None or (cu, cv) < best_pair:
                        best_dq = dq
                        best_pair = (cu, cv)

            if best_pair is None or best_dq < -1e-12:
                break

            c1, c2 = best_pair
            comms[c1].update(comms[c2])
            del comms[c2]
            degrees[c1] += degrees[c2]
            del degrees[c2]

            new_comm_edges: dict[tuple[int, int], int] = {}
            for (cu_i, cv_i), w in comm_edges.items():
                new_u = c1 if cu_i == c2 else cu_i
                new_v = c1 if cv_i == c2 else cv_i
                if new_u == new_v:
                    continue
                pair = (min(new_u, new_v), max(new_u, new_v))
                new_comm_edges[pair] = new_comm_edges.get(pair, 0) + w
            comm_edges = new_comm_edges

        final_comms = [
            sorted(list(comms[c]))
            for c in sorted(comms, key=lambda k: (-len(comms[k]), min(comms[k])))
        ]
        for comm in final_comms:
            for nid in comm:
                community_assignments[nid] = comm_counter
            comm_counter += 1

    return community_assignments


def _find_cycle_nodes(
    adjacency: dict[str, set[str]],
    all_nodes: set[str],
    self_loop_nodes: set[str],
) -> set[str]:
    """Find all node IDs in cycles using an iterative Tarjan's SCC algorithm."""
    cycle_nodes: set[str] = set(self_loop_nodes)
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    scc_stack: list[str] = []

    for root in sorted(all_nodes):
        if root in indices:
            continue
        call_stack: list[tuple[str, list[str], int]] = [
            (root, sorted(adjacency.get(root, ())), 0)
        ]
        indices[root] = index
        lowlinks[root] = index
        index += 1
        scc_stack.append(root)
        on_stack.add(root)

        while call_stack:
            u, neighbors, i = call_stack[-1]
            if i < len(neighbors):
                v = neighbors[i]
                call_stack[-1] = (u, neighbors, i + 1)
                if v not in indices:
                    indices[v] = index
                    lowlinks[v] = index
                    index += 1
                    scc_stack.append(v)
                    on_stack.add(v)
                    call_stack.append((v, sorted(adjacency.get(v, ())), 0))
                elif v in on_stack:
                    lowlinks[u] = min(lowlinks[u], indices[v])
            else:
                call_stack.pop()
                if lowlinks[u] == indices[u]:
                    scc: list[str] = []
                    while True:
                        w = scc_stack.pop()
                        on_stack.remove(w)
                        scc.append(w)
                        if w == u:
                            break
                    if len(scc) > 1:
                        cycle_nodes.update(scc)
                if call_stack:
                    parent = call_stack[-1][0]
                    lowlinks[parent] = min(lowlinks[parent], lowlinks[u])

    return cycle_nodes


class NetworkXAlgorithmAdapter:
    """Transient NetworkX-backed graph metric computer conforming to GraphAlgorithmPort."""

    def compute_metrics(
        self,
        nodes: tuple[GraphNode, ...],
        edges: tuple[GraphEdge, ...],
    ) -> dict[str, NodeMetrics]:
        import networkx as nx

        node_ids = {node.id for node in nodes}
        total_nodes = len(node_ids)
        denominator = max(1, total_nodes - 1)

        graph = nx.DiGraph()
        graph.add_nodes_from(sorted(node_ids))

        dep_out_adjacency: dict[str, set[str]] = defaultdict(set)
        dep_in_adjacency: dict[str, set[str]] = defaultdict(set)
        undirected_dep: dict[str, set[str]] = defaultdict(set)
        self_loops: set[str] = set()

        for edge in edges:
            src = edge.source_id
            tgt = edge.target_id
            if (
                src in node_ids
                and tgt is not None
                and tgt in node_ids
                and edge.kind in DEPENDENCY_KINDS
                and edge.resolution.status is ResolutionStatus.RESOLVED
            ):
                if src == tgt:
                    self_loops.add(src)
                else:
                    graph.add_edge(src, tgt)
                    dep_out_adjacency[src].add(tgt)
                    dep_in_adjacency[tgt].add(src)
                    undirected_dep[src].add(tgt)
                    undirected_dep[tgt].add(src)

        cycle_nodes: set[str] = set(self_loops)
        for scc in nx.strongly_connected_components(graph):
            if len(scc) > 1:
                cycle_nodes.update(scc)

        undirected_g = graph.to_undirected()
        # Connected components
        components_list = list(nx.connected_components(undirected_g))
        components_list.sort(key=lambda c: min(c))
        component_assignments: dict[str, int] = {}

        for comp_id, comp in enumerate(components_list, start=1):
            for nid in comp:
                component_assignments[nid] = comp_id

        # Detect actual community clusters using the canonical greedy modularity partition routine
        community_assignments = _detect_communities(
            undirected_dep, node_ids, component_assignments
        )

        # Compute module-level architecture metrics
        mod_metrics = _compute_module_metrics(
            nodes, node_ids, dep_out_adjacency, dep_in_adjacency
        )

        metrics: dict[str, NodeMetrics] = {}
        for node in nodes:
            nid = node.id
            fin = int(graph.in_degree(nid))
            fout = int(graph.out_degree(nid))
            deg_sum = fin + fout

            instability = fout / deg_sum if deg_sum > 0 else 0.0
            centrality = deg_sum / denominator if total_nodes > 1 else 0.0

            mm = mod_metrics.get(nid)

            metrics[nid] = NodeMetrics(
                node_id=nid,
                fan_in=fin,
                fan_out=fout,
                instability=round(instability, 2),
                degree_centrality=round(centrality, 3),
                in_cycle=nid in cycle_nodes,
                component_id=component_assignments.get(nid, 1),
                community_id=community_assignments.get(nid, 1),
                afferent_coupling=mm["ca"] if mm else None,
                efferent_coupling=mm["ce"] if mm else None,
                module_instability=mm["module_instability"] if mm else None,
                cohesion=mm["cohesion"] if mm else None,
                relational_density=mm["relational_density"] if mm else None,
            )

        return metrics


def get_algorithm_port(force_adapter: str | None = None) -> GraphAlgorithmPort:
    """Return an algorithm port adapter; uses NetworkX by default if installed, with pure Python fallback."""
    if force_adapter == "default":
        return DefaultAlgorithmAdapter()
    if force_adapter == "networkx":
        try:
            import networkx  # type: ignore[import-untyped,unused-ignore]  # noqa: F401

            return NetworkXAlgorithmAdapter()
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "NetworkX extra is not installed. Install via `pip install codestruct[metrics]` or use the default adapter."
            ) from exc

    try:
        import networkx  # type: ignore[import-untyped,unused-ignore]  # noqa: F401

        return NetworkXAlgorithmAdapter()
    except (ImportError, ModuleNotFoundError):
        return DefaultAlgorithmAdapter()


METRIC_ATTRIBUTE_KEYS = frozenset(
    {
        "centrality",
        "community",
        "component",
        "fan_in",
        "fan_out",
        "in_cycle",
        "instability",
        "ca",
        "ce",
        "module_instability",
        "cohesion",
        "relational_density",
    }
)


def enrich_nodes_with_metrics(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    port: GraphAlgorithmPort | None = None,
) -> tuple[GraphNode, ...]:
    """Compute structural metrics and attach them to node attributes, refreshing existing metric values."""
    if not nodes:
        return nodes

    adapter = port or get_algorithm_port()
    metrics = adapter.compute_metrics(nodes, edges)

    enriched: list[GraphNode] = []
    for node in nodes:
        m = metrics.get(node.id)
        if m is None:
            enriched.append(node)
            continue

        non_metric_attrs = [
            (k, v) for k, v in node.attributes if k not in METRIC_ATTRIBUTE_KEYS
        ]
        new_attrs = non_metric_attrs + list(m.to_attributes())

        enriched.append(
            GraphNode(
                id=node.id,
                kind=node.kind,
                name=node.name,
                qualified_name=node.qualified_name,
                parent_id=node.parent_id,
                module_id=node.module_id,
                file_id=node.file_id,
                location=node.location,
                modifiers=node.modifiers,
                attributes=tuple(sorted(new_attrs)),
            )
        )

    return tuple(enriched)
