"""Build immutable graph results from Phase 6 parser output without reparsing."""

from __future__ import annotations

import platform
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import replace
from typing import TypeVar

from codestruct import __version__
from codestruct.analysis.diagnostics import DiagnosticSeverity as ParserSeverity
from codestruct.analysis.models import (
    ClassDefinition,
    DefinitionKind,
    FunctionDefinition,
    ProjectParseResult,
)
from codestruct.analysis.models import (
    SourceSpan as ParserSourceSpan,
)

from .enums import (
    Confidence,
    DiagnosticPhase,
    DiagnosticSeverity,
    EvidenceOrigin,
    NodeKind,
    RelationshipKind,
    ResolutionStatus,
)
from .identifiers import (
    GraphIdentityCollisionError,
    content_digest,
    diagnostic_id,
    edge_id,
    evidence_id,
    node_id,
    normalized_text_hash,
    stable_digest,
)
from .metrics import enrich_nodes_with_metrics
from .model import (
    EvidenceRecord,
    GraphDiagnostic,
    GraphEdge,
    GraphMetadata,
    GraphNode,
    GraphResult,
    GraphSummaryCounts,
    ResolutionRecord,
    SourceReference,
    SourceSpan,
)
from .resolver import RelationshipObservation, RelationshipResolver
from .validation import assert_valid_graph

SCHEMA_VERSION = "1.0.0"
_Record = TypeVar("_Record")


def _span_key(span: ParserSourceSpan) -> tuple[int, int, int, int]:
    return (
        span.start_line,
        span.start_column,
        span.end_line or span.start_line,
        span.end_column or span.start_column,
    )


def _project_semantics(parsed: ProjectParseResult) -> tuple[object, ...]:
    files: list[object] = []
    for item in parsed.files:
        files.append(
            (
                item.source_file.relative_path,
                item.source_file.module_name,
                item.parsed,
                item.encoding,
                (
                    item.module.qualified_name,
                    item.module.has_docstring,
                    _span_key(item.module.span),
                )
                if item.module
                else None,
                tuple(
                    (value.id, value.qualified_name, _span_key(value.span))
                    for value in item.classes
                ),
                tuple(
                    (
                        value.id,
                        value.kind.value,
                        value.qualified_name,
                        _span_key(value.span),
                    )
                    for value in item.functions
                ),
                tuple(
                    (value.id, value.name, value.qualified_name, _span_key(value.span))
                    for value in item.variables
                ),
                tuple(
                    (
                        value.id,
                        value.kind.value,
                        value.module,
                        value.relative_level,
                        tuple((alias.name, alias.alias) for alias in value.names),
                        _span_key(value.span),
                    )
                    for value in item.imports
                ),
                tuple(
                    (value.id, value.expression, _span_key(value.span))
                    for value in item.inheritance
                ),
                tuple(
                    (
                        value.id,
                        value.expression,
                        value.enclosing_scope_id,
                        _span_key(value.span),
                    )
                    for value in item.calls
                ),
            )
        )
    diagnostics = tuple(
        (
            item.code.value,
            item.severity.value,
            item.relative_path,
            _span_key(item.span) if item.span else None,
        )
        for item in parsed.diagnostics
    )
    return tuple(files), diagnostics, parsed.cancelled, parsed.scan.limit_reached


class _Registry:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.evidence: dict[str, EvidenceRecord] = {}
        self.edges: dict[str, GraphEdge] = {}
        self.diagnostics: dict[str, GraphDiagnostic] = {}

    @staticmethod
    def _insert(store: dict[str, _Record], identifier: str, value: _Record) -> None:
        previous = store.get(identifier)
        if previous is not None and previous != value:
            raise GraphIdentityCollisionError(f"identity collision for {identifier}")
        store[identifier] = value

    def node(self, value: GraphNode) -> None:
        self._insert(self.nodes, value.id, value)

    def evidence_record(self, value: EvidenceRecord) -> None:
        self._insert(self.evidence, value.id, value)

    def diagnostic(self, value: GraphDiagnostic) -> None:
        self._insert(self.diagnostics, value.id, value)

    def edge(self, value: GraphEdge) -> None:
        previous = self.edges.get(value.id)
        if previous is None:
            self.edges[value.id] = value
            return
        if (
            previous.kind,
            previous.source_id,
            previous.target_id,
            previous.target_reference,
            previous.resolution,
            previous.attributes,
        ) != (
            value.kind,
            value.source_id,
            value.target_id,
            value.target_reference,
            value.resolution,
            value.attributes,
        ):
            raise GraphIdentityCollisionError(f"identity collision for {value.id}")
        self.edges[value.id] = replace(
            previous,
            evidence_ids=tuple(sorted(set(previous.evidence_ids + value.evidence_ids))),
            diagnostic_ids=tuple(
                sorted(set(previous.diagnostic_ids + value.diagnostic_ids))
            ),
            occurrence_count=previous.occurrence_count + value.occurrence_count,
        )


def _location(
    source_unit_id: str,
    path: str,
    span: ParserSourceSpan | SourceSpan,
) -> SourceReference:
    graph_span = SourceSpan(
        span.start_line,
        span.start_column,
        span.end_line,
        span.end_column,
    )
    return SourceReference(source_unit_id, path, graph_span)


def _node_kind(kind: DefinitionKind) -> NodeKind:
    return {
        DefinitionKind.CLASS: NodeKind.CLASS,
        DefinitionKind.FUNCTION: NodeKind.FUNCTION,
        DefinitionKind.ASYNC_FUNCTION: NodeKind.ASYNC_FUNCTION,
        DefinitionKind.METHOD: NodeKind.METHOD,
        DefinitionKind.ASYNC_METHOD: NodeKind.ASYNC_METHOD,
    }[kind]


def _evidence(
    registry: _Registry,
    origin: EvidenceOrigin,
    observation_kind: str,
    location: SourceReference,
    expression: str | None,
    explanation: str,
) -> str:
    observed_hash = normalized_text_hash(expression)
    identifier = evidence_id(
        origin, location.source_unit_id, location.span, observation_kind, observed_hash
    )
    registry.evidence_record(
        EvidenceRecord(
            id=identifier,
            origin=origin,
            observation_kind=observation_kind,
            location=location,
            observed_text_hash=observed_hash,
            excerpt=None,
            explanation=explanation,
            expression=" ".join(expression.split()) if expression else None,
        )
    )
    return identifier


def _add_containment(
    registry: _Registry,
    parent: GraphNode,
    child: GraphNode,
    relationship: RelationshipKind,
) -> None:
    if child.location is None:
        return
    evidence = _evidence(
        registry,
        EvidenceOrigin.SOURCE_AST,
        "definition" if relationship is RelationshipKind.DEFINES else "source_artifact",
        child.location,
        child.qualified_name,
        "The child entity is directly owned by the source parent.",
    )
    identifier = edge_id(
        relationship,
        parent.id,
        child.id,
        ResolutionStatus.NOT_APPLICABLE,
        "canonical_parent",
    )
    registry.edge(
        GraphEdge(
            id=identifier,
            kind=relationship,
            source_id=parent.id,
            target_id=child.id,
            target_reference=None,
            resolution=ResolutionRecord(
                ResolutionStatus.NOT_APPLICABLE,
                Confidence.EXACT,
                "DIRECT_OWNERSHIP",
            ),
            evidence_ids=(evidence,),
            attributes=(),
        )
    )


def _parser_diagnostics(
    parsed: ProjectParseResult,
    file_ids: dict[str, str],
) -> tuple[GraphDiagnostic, ...]:
    result: list[GraphDiagnostic] = []
    parsing_codes = {
        "FILE_READ_FAILURE",
        "FILE_ENCODING_FAILURE",
        "FILE_SYNTAX_ERROR",
        "FILE_CHANGED_OR_MISSING",
        "UNSUPPORTED_GRAMMAR",
    }
    for item in parsed.diagnostics:
        phase = (
            DiagnosticPhase.PARSING
            if item.code.value in parsing_codes
            else DiagnosticPhase.SCANNING
        )
        location = None
        source_unit_id = ""
        if item.relative_path and item.span and item.relative_path in file_ids:
            source_unit_id = file_ids[item.relative_path]
            location = _location(source_unit_id, item.relative_path, item.span)
        result.append(
            GraphDiagnostic(
                id=diagnostic_id(
                    item.code.value,
                    phase.value,
                    source_unit_id,
                    location.span if location else None,
                    item.relative_path or item.id,
                ),
                code=item.code.value,
                severity={
                    ParserSeverity.INFO: DiagnosticSeverity.INFO,
                    ParserSeverity.WARNING: DiagnosticSeverity.WARNING,
                    ParserSeverity.ERROR: DiagnosticSeverity.ERROR,
                }[item.severity],
                phase=phase,
                message=item.message,
                location=location,
                recoverable=item.severity is not ParserSeverity.ERROR,
                consequence="skipped_or_partial",
            )
        )
    return tuple(result)


def _resolution_diagnostic(
    observation: RelationshipObservation,
    edge_identifier: str,
    location: SourceReference,
) -> GraphDiagnostic | None:
    if (
        observation.status is ResolutionStatus.RESOLVED
        or observation.status is ResolutionStatus.NOT_APPLICABLE
    ):
        return None
    code = {
        ResolutionStatus.AMBIGUOUS: "AMBIGUOUS_STATIC_REFERENCE",
        ResolutionStatus.UNRESOLVED: "UNRESOLVED_STATIC_REFERENCE",
        ResolutionStatus.SYNTACTIC_ONLY: "SYNTACTIC_ONLY_REFERENCE",
    }[observation.status]
    severity = (
        DiagnosticSeverity.WARNING
        if observation.status is not ResolutionStatus.SYNTACTIC_ONLY
        else DiagnosticSeverity.INFO
    )
    identifier = diagnostic_id(
        code,
        DiagnosticPhase.RESOLVING.value,
        location.source_unit_id,
        location.span,
        observation.discriminator,
    )
    return GraphDiagnostic(
        id=identifier,
        code=code,
        severity=severity,
        phase=DiagnosticPhase.RESOLVING,
        message="The reference could not be assigned one exact supported static target.",
        location=location,
        edge_id=edge_identifier,
        recoverable=True,
        consequence="relationship_retained_without_exact_target",
        details=(("reason_code", observation.reason_code),),
    )


def _add_relationship(
    registry: _Registry,
    observation: RelationshipObservation,
    file_ids_by_parser_id: dict[str, str],
) -> None:
    source_unit_id = file_ids_by_parser_id[observation.source_unit_id]
    location = _location(source_unit_id, observation.relative_path, observation.span)
    source_evidence = _evidence(
        registry,
        EvidenceOrigin.SOURCE_AST,
        observation.observation_kind,
        location,
        observation.expression,
        "The Python AST parser directly observed this syntax.",
    )
    evidence_ids = [source_evidence]
    if observation.status is ResolutionStatus.RESOLVED:
        evidence_ids.append(
            _evidence(
                registry,
                EvidenceOrigin.STATIC_RESOLUTION,
                f"{observation.observation_kind}_resolution",
                location,
                observation.expression,
                f"The deterministic resolver applied {observation.reason_code}.",
            )
        )
    target_key = observation.target_id or observation.target_reference or ""
    semantic_discriminator = content_digest(
        (EvidenceOrigin.SOURCE_AST.value, observation.attributes)
    )
    identifier = edge_id(
        observation.kind,
        observation.source_id,
        target_key,
        observation.status,
        semantic_discriminator,
    )
    diagnostic = _resolution_diagnostic(observation, identifier, location)
    diagnostic_ids: tuple[str, ...] = ()
    if diagnostic:
        registry.diagnostic(diagnostic)
        diagnostic_ids = (diagnostic.id,)
    registry.edge(
        GraphEdge(
            id=identifier,
            kind=observation.kind,
            source_id=observation.source_id,
            target_id=observation.target_id,
            target_reference=observation.target_reference,
            resolution=ResolutionRecord(
                observation.status,
                observation.confidence,
                observation.reason_code,
                observation.candidate_ids,
            ),
            evidence_ids=tuple(sorted(evidence_ids)),
            diagnostic_ids=diagnostic_ids,
            attributes=observation.attributes,
        )
    )


def _inheritance_cycle_diagnostics(
    registry: _Registry,
) -> tuple[GraphDiagnostic, ...]:
    adjacency: dict[str, list[tuple[str, GraphEdge]]] = {}
    for edge in registry.edges.values():
        if (
            edge.kind is RelationshipKind.INHERITS
            and edge.resolution.status is ResolutionStatus.RESOLVED
            and edge.target_id
        ):
            adjacency.setdefault(edge.source_id, []).append((edge.target_id, edge))
    state: dict[str, int] = {}
    cyclic_edges: dict[str, GraphEdge] = {}

    def visit(node: str, stack: list[str], edges: list[GraphEdge]) -> None:
        state[node] = 1
        stack.append(node)
        for target, edge in sorted(adjacency.get(node, ()), key=lambda item: item[0]):
            if state.get(target, 0) == 0:
                visit(target, stack, [*edges, edge])
            elif state.get(target) == 1 and target in stack:
                start = stack.index(target)
                for cycle_edge in [*edges[start:], edge]:
                    cyclic_edges[cycle_edge.id] = cycle_edge
        stack.pop()
        state[node] = 2

    for node in sorted(adjacency):
        if state.get(node, 0) == 0:
            visit(node, [], [])
    result: list[GraphDiagnostic] = []
    for edge in sorted(cyclic_edges.values(), key=lambda item: item.id):
        identifier = diagnostic_id(
            "INHERITANCE_CYCLE", DiagnosticPhase.RESOLVING.value, discriminator=edge.id
        )
        result.append(
            GraphDiagnostic(
                id=identifier,
                code="INHERITANCE_CYCLE",
                severity=DiagnosticSeverity.WARNING,
                phase=DiagnosticPhase.RESOLVING,
                message="A statically resolved inheritance cycle is present.",
                entity_id=edge.source_id,
                edge_id=edge.id,
                recoverable=False,
                consequence="cycle_preserved",
            )
        )
    return tuple(result)


def _summary(parsed: ProjectParseResult, registry: _Registry) -> GraphSummaryCounts:
    def count(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(Counter(values).items()))

    excluded = sum(
        1 for item in parsed.diagnostics if item.code.value == "PATH_EXCLUDED"
    )
    failed = sum(1 for item in parsed.files if not item.parsed)
    return GraphSummaryCounts(
        source_units_total=len(parsed.scan.source_files),
        nodes_total=len(registry.nodes),
        edges_total=len(registry.edges),
        evidence_total=len(registry.evidence),
        diagnostics_total=len(registry.diagnostics),
        nodes_by_kind=count(item.kind.value for item in registry.nodes.values()),
        edges_by_kind=count(item.kind.value for item in registry.edges.values()),
        edges_by_resolution=count(
            item.resolution.status.value for item in registry.edges.values()
        ),
        edges_by_confidence=count(
            item.resolution.confidence.value for item in registry.edges.values()
        ),
        diagnostics_by_severity=count(
            item.severity.value for item in registry.diagnostics.values()
        ),
        diagnostics_by_code=count(item.code for item in registry.diagnostics.values()),
        excluded_entries=excluded,
        failed_files=failed,
        skipped_files=max(0, len(parsed.scan.source_files) - len(parsed.files)),
    )


def build_graph(
    parsed: ProjectParseResult,
    *,
    analyzer_version: str = __version__,
    compute_metrics: bool = False,
) -> GraphResult:
    """Build and validate a canonical graph without reading source files."""

    semantics = _project_semantics(parsed)
    project_fingerprint = content_digest(semantics)
    # ProjectParseResult intentionally carries no policy or source-byte digest.
    # These Phase 7 standalone identities therefore fingerprint the immutable
    # extraction snapshot and an explicit policy-unavailable marker. The future
    # coordinator must provide real job IDs and cache-grade fingerprints.
    policy_fingerprint = content_digest(("phase6_effective_policy_unavailable",))
    result_id = stable_digest(
        "res",
        project_fingerprint,
        analyzer_version,
        platform.python_version(),
        policy_fingerprint,
        "1.0",
    )
    graph_id = stable_digest("grf", result_id, SCHEMA_VERSION)
    analysis_id = stable_digest("ana", result_id, "standalone_phase7")
    project_name = parsed.scan.root_name or "project"
    registry = _Registry()
    project = GraphNode(
        id=node_id(NodeKind.PROJECT, "project"),
        kind=NodeKind.PROJECT,
        name=project_name,
        qualified_name="project",
        attributes=(("display_name", project_name),),
    )
    registry.node(project)

    file_ids_by_parser_id: dict[str, str] = {}
    file_ids_by_path: dict[str, str] = {}
    module_nodes: dict[str, GraphNode] = {}
    package_nodes: dict[str, GraphNode] = {}
    parser_to_node: dict[str, str] = {}
    parser_parent: dict[str, str | None] = {}
    parser_module: dict[str, str] = {}

    for source in parsed.scan.source_files:
        graph_file_id = node_id(NodeKind.FILE, source.relative_path)
        file_ids_by_parser_id[source.id] = graph_file_id
        file_ids_by_path[source.relative_path] = graph_file_id

    for file_result in parsed.files:
        if file_result.module is None:
            continue
        source = file_result.source_file
        module = file_result.module
        graph_file_id = file_ids_by_parser_id[source.id]
        if source.is_package:
            package_identifier = node_id(
                NodeKind.PACKAGE, source.relative_path, module.qualified_name
            )
            package_nodes[module.qualified_name] = GraphNode(
                id=package_identifier,
                kind=NodeKind.PACKAGE,
                name=module.name,
                qualified_name=module.qualified_name,
                file_id=graph_file_id,
                location=_location(graph_file_id, source.relative_path, module.span),
                attributes=(("parser_id", module.id),),
            )

    def package_parent(qualified_name: str) -> str:
        parent_name = qualified_name.rpartition(".")[0]
        while parent_name:
            if parent_name in package_nodes:
                return package_nodes[parent_name].id
            parent_name = parent_name.rpartition(".")[0]
        return project.id

    for name, package in tuple(package_nodes.items()):
        package_nodes[name] = replace(package, parent_id=package_parent(name))
        registry.node(package_nodes[name])

    parsed_by_source = {item.source_file.id: item for item in parsed.files}
    for source in parsed.scan.source_files:
        graph_file_id = file_ids_by_parser_id[source.id]
        matched_file = parsed_by_source.get(source.id)
        matched_module = matched_file.module if matched_file else None
        module_name = (
            matched_module.qualified_name if matched_module else source.module_name
        )
        owner_package_name = (
            module_name if source.is_package else module_name.rpartition(".")[0]
        )
        owner_id = (
            package_nodes[owner_package_name].id
            if owner_package_name in package_nodes
            else project.id
        )
        source_span = matched_module.span if matched_module else ParserSourceSpan(1, 1)
        file_node = GraphNode(
            id=graph_file_id,
            kind=NodeKind.FILE,
            name=source.relative_path.rsplit("/", 1)[-1],
            qualified_name=source.relative_path,
            parent_id=owner_id,
            location=_location(graph_file_id, source.relative_path, source_span),
            attributes=(("parser_id", source.id),),
        )
        registry.node(file_node)
        if matched_module is None:
            continue
        module_identifier = node_id(
            NodeKind.MODULE, source.relative_path, matched_module.qualified_name
        )
        module_node = GraphNode(
            id=module_identifier,
            kind=NodeKind.MODULE,
            name=matched_module.name,
            qualified_name=matched_module.qualified_name,
            parent_id=owner_id,
            file_id=graph_file_id,
            location=_location(
                graph_file_id, source.relative_path, matched_module.span
            ),
            attributes=(
                ("has_docstring", str(matched_module.has_docstring).lower()),
                ("parser_id", matched_module.id),
            ),
        )
        registry.node(module_node)
        module_nodes[matched_module.id] = module_node
        parser_to_node[matched_module.id] = module_identifier
        parser_parent[matched_module.id] = None
        parser_module[matched_module.id] = matched_module.id

    for file_result in parsed.files:
        if file_result.module is None:
            continue
        source = file_result.source_file
        graph_file_id = file_ids_by_parser_id[source.id]
        definitions: list[ClassDefinition | FunctionDefinition] = sorted(
            [*file_result.classes, *file_result.functions],
            key=lambda item: (*_span_key(item.span), item.id),
        )
        for definition in definitions:
            kind = (
                NodeKind.CLASS
                if isinstance(definition, ClassDefinition)
                else _node_kind(definition.kind)
            )
            parent_graph_id = parser_to_node[definition.enclosing_scope_id]
            identifier = node_id(
                kind, source.relative_path, definition.qualified_name, definition.id
            )
            modifiers = (
                ("async",)
                if kind in {NodeKind.ASYNC_FUNCTION, NodeKind.ASYNC_METHOD}
                else ()
            )
            node = GraphNode(
                id=identifier,
                kind=kind,
                name=definition.name,
                qualified_name=definition.qualified_name,
                parent_id=parent_graph_id,
                module_id=module_nodes[file_result.module.id].id,
                file_id=graph_file_id,
                location=_location(
                    graph_file_id, source.relative_path, definition.span
                ),
                modifiers=modifiers,
                attributes=(
                    ("has_docstring", str(definition.has_docstring).lower()),
                    ("parser_id", definition.id),
                ),
            )
            registry.node(node)
            parser_to_node[definition.id] = identifier
            parser_parent[definition.id] = definition.enclosing_scope_id
            parser_module[definition.id] = file_result.module.id

    # Canonical containment is derived only after every parent exists.
    for node in sorted(
        registry.nodes.values(),
        key=lambda item: (item.kind.value, item.qualified_name, item.id),
    ):
        if node.parent_id:
            relationship = (
                RelationshipKind.DEFINES
                if node.kind
                in {
                    NodeKind.CLASS,
                    NodeKind.FUNCTION,
                    NodeKind.ASYNC_FUNCTION,
                    NodeKind.METHOD,
                    NodeKind.ASYNC_METHOD,
                }
                else RelationshipKind.CONTAINS
            )
            _add_containment(
                registry, registry.nodes[node.parent_id], node, relationship
            )

    resolver = RelationshipResolver(
        parsed,
        tuple(registry.nodes.values()),
        parser_to_node,
        parser_parent,
        parser_module,
        project.id,
    )
    observations = [*resolver.resolve_imports()]
    observations.extend(resolver.resolve_inheritance())
    observations.extend(resolver.resolve_calls())
    for node in resolver.synthetic_nodes.values():
        registry.node(node)
    for observation in observations:
        _add_relationship(registry, observation, file_ids_by_parser_id)
    for diagnostic in _parser_diagnostics(parsed, file_ids_by_path):
        registry.diagnostic(diagnostic)
    for diagnostic in _inheritance_cycle_diagnostics(registry):
        registry.diagnostic(diagnostic)

    partial_reasons: list[str] = []
    if parsed.cancelled:
        partial_reasons.append("cancelled")
    if parsed.scan.limit_reached:
        partial_reasons.append("analysis_limit_reached")
    if any(not item.parsed for item in parsed.files):
        partial_reasons.append("file_parse_failure")
    if any(
        item.severity is DiagnosticSeverity.ERROR
        for item in registry.diagnostics.values()
    ):
        partial_reasons.append("error_diagnostic")
    metadata = GraphMetadata(
        analysis_id=analysis_id,
        result_id=result_id,
        graph_id=graph_id,
        schema_version=SCHEMA_VERSION,
        api_version="v1",
        analyzer_version=analyzer_version,
        python_runtime=platform.python_version(),
        source_language="python",
        source_grammar=f"python-{sys.version_info.major}.{sys.version_info.minor}",
        policy_fingerprint=policy_fingerprint,
        project_fingerprint=project_fingerprint,
        partial=parsed.partial or bool(partial_reasons),
        partial_reasons=tuple(sorted(set(partial_reasons))),
        exclusions=(
            (
                "excluded_entries",
                str(
                    sum(
                        1
                        for item in parsed.diagnostics
                        if item.code.value == "PATH_EXCLUDED"
                    )
                ),
            ),
        ),
        metrics_computed=compute_metrics,
    )
    raw_nodes = tuple(
        sorted(
            registry.nodes.values(),
            key=lambda item: (item.kind.value, item.qualified_name, item.id),
        )
    )
    raw_edges = tuple(
        sorted(
            registry.edges.values(),
            key=lambda item: (
                item.kind.value,
                item.source_id,
                item.target_id or item.target_reference or "",
                item.id,
            ),
        )
    )
    if compute_metrics:
        enriched_nodes = enrich_nodes_with_metrics(raw_nodes, raw_edges)
    else:
        enriched_nodes = raw_nodes
    graph = GraphResult(
        schema_version=SCHEMA_VERSION,
        metadata=metadata,
        summary=_summary(parsed, registry),
        nodes=enriched_nodes,
        edges=raw_edges,
        evidence=tuple(sorted(registry.evidence.values(), key=lambda item: item.id)),
        diagnostics=tuple(
            sorted(
                registry.diagnostics.values(),
                key=lambda item: (item.severity.value, item.code, item.id),
            )
        ),
    )
    assert_valid_graph(graph)
    return graph
