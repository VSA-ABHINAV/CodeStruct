# Development architecture

FastAPI validates DTOs and delegates to the analysis service; it never parses.
Settings own authorized capabilities and policy. The service canonicalizes the
alias/root, fingerprints inputs, consults storage, registers a job, and dispatches
a spawned worker. The worker scans, parses with `ast`, resolves conservatively,
builds/validates the dataclass graph, and returns deterministic JSON. The parent
persists terminal state in SQLite.

The frontend API client discovers projects, polls jobs, and retrieves bounded
pages. Normalization, selectors, and layout are React Flow independent; only the
renderer adapter creates renderer records. UI selection/filter/page state stays
outside the canonical graph.

Dependency direction is API → service/interfaces → scanner/parser/graph domain;
SQLite and React Flow are adapters. Project code is never imported. Canonical
roots stay server-side; public evidence uses relative paths.

## Graph metrics architecture (CS-009, CS-010)

Graph metrics are computed when `options.metrics` is `true` in `POST /api/v1/analyses`.
When computed, the graph serializer sets `metadata.metrics_computed = true` and attaches
string-normalized attributes to graph nodes.

### Edge qualification & filtering
- **Eligible dependency kinds:** `RelationshipKind.CALLS`, `IMPORTS`, `INHERITS`, `CONSTRUCTS`, `REFERENCES`.
- **Resolution status:** Strictly `ResolutionStatus.RESOLVED` only. Unresolved, ambiguous, syntactic-only, and containment (`DEFINES`, `CONTAINS`, `MEMBER_OF`) edges are excluded from dependency counts.
- **Self-loops & duplicates:** Parallel edges are deduplicated into adjacency sets. Self-loops on dependency edges mark `in_cycle = True` on the node but are excluded from fan-in/fan-out, coupling, and modularity calculations.

### Node-level metrics
- **Fan-in / Fan-out:** In-degree and out-degree over eligible resolved dependency edges.
- **Instability ($I$):** $I = \text{fan\_out} / (\text{fan\_in} + \text{fan\_out})$ ($0.0$ if sum is 0).
- **Degree Centrality:** Normalized by $(\text{fan\_in} + \text{fan\_out}) / \max(1, N - 1)$ where $N$ is total node count.
- **Cycle Membership (`in_cycle`):** Boolean indicating if node is in a strongly connected component of size > 1 or has a self-loop. Computed using iterative Tarjan's SCC (recursion-depth safe up to 10,000+ nodes).
- **Component ID (`component`):** Integer ID 1..k of the undirected connected component (reachability).
- **Community ID (`community`):** Integer ID 1..k of the community cluster within connected components, computed via Clauset-Newman-Moore greedy modularity optimization.

### Module-level architecture metrics
Computed for `NodeKind.MODULE` and `NodeKind.PACKAGE` nodes:
- **Module Members ($E(M)$):** Contained program entities (functions, classes, methods) belonging to module $M$, excluding the module container itself.
- **Afferent Coupling ($C_a$):** Number of external entities outside $E(M) \cup \{M\}$ that depend on any entity in $E(M) \cup \{M\}$.
- **Efferent Coupling ($C_e$):** Number of external entities outside $E(M) \cup \{M\}$ depended on by any entity in $E(M) \cup \{M\}$.
- **Module Instability ($I_M$):** $I_M = C_e / (C_a + C_e)$ ($0.0$ if $C_a + C_e = 0$).
- **Internal Cohesion:** Ratio of internal dependency edges between entities in $E(M)$ over theoretical maximum $|E(M)| \times (|E(M)| - 1)$. For $|E(M)| = 1$, cohesion is $1.0$ (unified single entity). For $|E(M)| = 0$ (empty module container), cohesion is $0.0$.
- **Relational Density:** $(\text{internal\_edges} + C_a + C_e) / \max(1, |E(M)|)$.

### Adapter policy & optional installation
- **Default Adapter (`DefaultAlgorithmAdapter`):** Pure-Python, zero-dependency implementation with iterative Tarjan SCC and Clauset-Newman-Moore modularity optimization.
- **NetworkX Adapter (`NetworkXAlgorithmAdapter`):** Optional adapter enabled via `pip install codestruct[metrics]` (declaring `networkx>=3.0,<4.0`). Provides 100% numerical and community partition parity with the default adapter.
- **Fallback selection:** `get_algorithm_port()` uses NetworkX if installed, cleanly falling back to `DefaultAlgorithmAdapter` when missing. Third-party graph objects never leak across API, storage, or serializer boundaries.

## Type stub (.pyi) and static resolution scope (CS-018, CS-019)

- **`.py` vs `.pyi` Precedence:** When both `.py` implementation and `.pyi` type stub exist for the same module/symbol, `.py` implementation is prioritized.
- **Stub-Only Support:** When only `.pyi` exists without `.py`, symbols from `.pyi` are indexed and resolved.
- **External Stub Boundary:** Stubs for external/stdlib packages are not scanned as project source files; external references resolve to `EXTERNAL_MODULE` or `UNRESOLVED_SYMBOL`.
- **Static Purity:** Target code is never imported or executed. Dynamic reflection (`getattr`, `importlib`) remains conservatively `UNRESOLVED` or `SYNTACTIC_ONLY`.

See [target architecture](../architecture/target-architecture.md),
[graph schema](../architecture/graph-schema.md), [API contract](../architecture/api-contract.md),
[security model](../architecture/security-model.md), [migration plan](../architecture/migration-plan.md),
and [ADRs](../decisions/README.md).
