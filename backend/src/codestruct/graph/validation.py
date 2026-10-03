"""Graph invariant validation independent of graph construction."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

from .enums import (
    DiagnosticPhase,
    DiagnosticSeverity,
    RelationshipKind,
    ResolutionStatus,
)
from .identifiers import diagnostic_id
from .model import GraphDiagnostic, GraphResult

SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0.0"})


class GraphInvariantError(ValueError):
    """Raised only when a graph is unusable or violates programmer invariants."""

    def __init__(self, diagnostics: tuple[GraphDiagnostic, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__(
            "graph invariant validation failed: "
            + ", ".join(item.code for item in diagnostics)
        )


@dataclass(frozen=True, slots=True)
class GraphValidationReport:
    valid: bool
    diagnostics: tuple[GraphDiagnostic, ...]


def _problem(
    code: str, message: str, entity_id: str | None = None, edge_id: str | None = None
) -> GraphDiagnostic:
    return GraphDiagnostic(
        id=diagnostic_id(
            code,
            DiagnosticPhase.VALIDATING.value,
            discriminator=f"{entity_id or ''}:{edge_id or ''}",
        ),
        code=code,
        severity=DiagnosticSeverity.ERROR,
        phase=DiagnosticPhase.VALIDATING,
        message=message,
        entity_id=entity_id,
        edge_id=edge_id,
        recoverable=False,
        consequence="graph_rejected",
    )


def _valid_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and "\\" not in value
        and not path.is_absolute()
        and ".." not in path.parts
    )


def _valid_span(location) -> bool:
    if location is None:
        return True
    span = location.span
    if span.start_line < 1 or span.start_column < 1:
        return False
    if (span.end_line is None) != (span.end_column is None):
        return False
    if span.end_line is None:
        return True
    return (span.end_line, span.end_column) >= (
        span.start_line,
        span.start_column,
    ) and span.end_column >= 1


def validate_graph(graph: GraphResult) -> GraphValidationReport:
    problems: list[GraphDiagnostic] = []
    if (
        graph.schema_version not in SUPPORTED_SCHEMA_VERSIONS
        or graph.metadata.schema_version != graph.schema_version
    ):
        problems.append(
            _problem(
                "UNSUPPORTED_SCHEMA_VERSION",
                "The graph schema version is missing, unsupported, or inconsistent.",
            )
        )

    node_ids = [item.id for item in graph.nodes]
    edge_ids = [item.id for item in graph.edges]
    evidence_ids = [item.id for item in graph.evidence]
    diagnostic_ids = [item.id for item in graph.diagnostics]
    for code, values in (
        ("DUPLICATE_NODE_ID", node_ids),
        ("DUPLICATE_EDGE_ID", edge_ids),
        ("DUPLICATE_EVIDENCE_ID", evidence_ids),
        ("DUPLICATE_DIAGNOSTIC_ID", diagnostic_ids),
    ):
        if len(values) != len(set(values)):
            problems.append(_problem(code, "A canonical identifier is duplicated."))

    nodes = set(node_ids)
    evidence = set(evidence_ids)
    diagnostics = set(diagnostic_ids)
    parent_edges: set[tuple[str, str]] = set()
    adjacency: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.source_id not in nodes:
            problems.append(
                _problem(
                    "MISSING_EDGE_SOURCE",
                    "An edge source does not exist.",
                    edge_id=edge.id,
                )
            )
        if edge.target_id is not None and edge.target_id not in nodes:
            problems.append(
                _problem(
                    "MISSING_EDGE_TARGET",
                    "An edge target does not exist.",
                    edge_id=edge.id,
                )
            )
        if (
            edge.resolution.status is ResolutionStatus.RESOLVED
            and edge.target_id is None
        ):
            problems.append(
                _problem(
                    "RESOLVED_EDGE_WITHOUT_TARGET",
                    "A resolved edge must identify one target.",
                    edge_id=edge.id,
                )
            )
        if (
            edge.resolution.status
            in {
                ResolutionStatus.AMBIGUOUS,
                ResolutionStatus.UNRESOLVED,
                ResolutionStatus.SYNTACTIC_ONLY,
            }
            and not edge.target_reference
        ):
            problems.append(
                _problem(
                    "UNRESOLVED_EDGE_WITHOUT_REFERENCE",
                    "A non-resolved edge must retain its safe reference.",
                    edge_id=edge.id,
                )
            )
        if edge.occurrence_count < 1:
            problems.append(
                _problem(
                    "INVALID_OCCURRENCE_COUNT",
                    "An edge occurrence count must be positive.",
                    edge_id=edge.id,
                )
            )
        if not edge.evidence_ids:
            problems.append(
                _problem(
                    "EDGE_WITHOUT_EVIDENCE",
                    "Every graph edge must retain evidence.",
                    edge_id=edge.id,
                )
            )
        if any(item not in evidence for item in edge.evidence_ids):
            problems.append(
                _problem(
                    "MISSING_EDGE_EVIDENCE",
                    "An edge refers to absent evidence.",
                    edge_id=edge.id,
                )
            )
        if any(item not in diagnostics for item in edge.diagnostic_ids):
            problems.append(
                _problem(
                    "MISSING_EDGE_DIAGNOSTIC",
                    "An edge refers to an absent diagnostic.",
                    edge_id=edge.id,
                )
            )
        if (
            edge.kind in {RelationshipKind.CONTAINS, RelationshipKind.DEFINES}
            and edge.target_id
        ):
            parent_edges.add((edge.source_id, edge.target_id))
            adjacency.setdefault(edge.source_id, []).append(edge.target_id)

    for node in graph.nodes:
        if node.location:
            if not _valid_path(node.location.path):
                problems.append(
                    _problem(
                        "UNSAFE_SOURCE_PATH",
                        "A node contains a non-relative source path.",
                        entity_id=node.id,
                    )
                )
            if not _valid_span(node.location):
                problems.append(
                    _problem(
                        "INVALID_SOURCE_SPAN",
                        "A node has an invalid source span.",
                        entity_id=node.id,
                    )
                )
        if node.parent_id:
            if node.parent_id not in nodes:
                problems.append(
                    _problem(
                        "MISSING_PARENT",
                        "A node parent does not exist.",
                        entity_id=node.id,
                    )
                )
            if (node.parent_id, node.id) not in parent_edges:
                problems.append(
                    _problem(
                        "INCONSISTENT_OWNERSHIP",
                        "A node parent and containment edge disagree.",
                        entity_id=node.id,
                    )
                )

    for record in graph.evidence:
        if record.location:
            if not _valid_path(record.location.path):
                problems.append(
                    _problem(
                        "UNSAFE_EVIDENCE_PATH",
                        "Evidence contains a non-relative source path.",
                    )
                )
            if not _valid_span(record.location):
                problems.append(
                    _problem(
                        "INVALID_EVIDENCE_SPAN", "Evidence has an invalid source span."
                    )
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def has_cycle(identifier: str) -> bool:
        if identifier in visiting:
            return True
        if identifier in visited:
            return False
        visiting.add(identifier)
        for child in adjacency.get(identifier, ()):
            if has_cycle(child):
                return True
        visiting.remove(identifier)
        visited.add(identifier)
        return False

    if any(
        has_cycle(identifier)
        for identifier in sorted(nodes)
        if identifier not in visited
    ):
        problems.append(
            _problem("CONTAINMENT_CYCLE", "Canonical containment must be acyclic.")
        )

    expected = {
        "nodes_total": len(graph.nodes),
        "edges_total": len(graph.edges),
        "evidence_total": len(graph.evidence),
        "diagnostics_total": len(graph.diagnostics),
        "nodes_by_kind": tuple(
            sorted(Counter(item.kind.value for item in graph.nodes).items())
        ),
        "edges_by_kind": tuple(
            sorted(Counter(item.kind.value for item in graph.edges).items())
        ),
        "edges_by_resolution": tuple(
            sorted(
                Counter(item.resolution.status.value for item in graph.edges).items()
            )
        ),
    }
    for field, value in expected.items():
        if getattr(graph.summary, field) != value:
            problems.append(
                _problem(
                    "SUMMARY_COUNT_MISMATCH",
                    f"Summary field {field} does not match the graph.",
                )
            )

    unique = {item.id: item for item in problems}
    ordered = tuple(sorted(unique.values(), key=lambda item: (item.code, item.id)))
    return GraphValidationReport(not ordered, ordered)


def assert_valid_graph(graph: GraphResult) -> None:
    report = validate_graph(graph)
    if not report.valid:
        raise GraphInvariantError(report.diagnostics)
