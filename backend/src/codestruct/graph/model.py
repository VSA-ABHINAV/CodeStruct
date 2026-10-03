"""Framework-independent immutable graph domain records."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import (
    Confidence,
    DiagnosticPhase,
    DiagnosticSeverity,
    EvidenceOrigin,
    NodeKind,
    RelationshipKind,
    ResolutionStatus,
)

Attribute = tuple[str, str]


@dataclass(frozen=True, slots=True, order=True)
class SourceSpan:
    start_line: int
    start_column: int
    end_line: int | None = None
    end_column: int | None = None


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_unit_id: str
    path: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    id: str
    origin: EvidenceOrigin
    observation_kind: str
    location: SourceReference | None
    observed_text_hash: str | None
    excerpt: str | None
    explanation: str
    expression: str | None = None


@dataclass(frozen=True, slots=True)
class ResolutionRecord:
    status: ResolutionStatus
    confidence: Confidence
    reason_code: str
    candidate_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str
    kind: NodeKind
    name: str
    qualified_name: str
    parent_id: str | None = None
    module_id: str | None = None
    file_id: str | None = None
    location: SourceReference | None = None
    modifiers: tuple[str, ...] = ()
    attributes: tuple[Attribute, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphEdge:
    id: str
    kind: RelationshipKind
    source_id: str
    target_id: str | None
    target_reference: str | None
    resolution: ResolutionRecord
    evidence_ids: tuple[str, ...]
    occurrence_count: int = 1
    diagnostic_ids: tuple[str, ...] = ()
    attributes: tuple[Attribute, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphDiagnostic:
    id: str
    code: str
    severity: DiagnosticSeverity
    phase: DiagnosticPhase
    message: str
    location: SourceReference | None = None
    entity_id: str | None = None
    edge_id: str | None = None
    recoverable: bool = True
    consequence: str = "partial"
    suggested_action: str | None = None
    details: tuple[Attribute, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphMetadata:
    analysis_id: str
    result_id: str
    graph_id: str
    schema_version: str
    api_version: str
    analyzer_version: str
    python_runtime: str
    source_language: str
    source_grammar: str
    policy_fingerprint: str
    project_fingerprint: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    cache: tuple[Attribute, ...] = ()
    partial: bool = False
    partial_reasons: tuple[str, ...] = ()
    exclusions: tuple[Attribute, ...] = ()
    limits: tuple[Attribute, ...] = ()
    metrics_computed: bool = False


@dataclass(frozen=True, slots=True)
class GraphSummaryCounts:
    source_units_total: int
    nodes_total: int
    edges_total: int
    evidence_total: int
    diagnostics_total: int
    nodes_by_kind: tuple[tuple[str, int], ...]
    edges_by_kind: tuple[tuple[str, int], ...]
    edges_by_resolution: tuple[tuple[str, int], ...]
    edges_by_confidence: tuple[tuple[str, int], ...]
    diagnostics_by_severity: tuple[tuple[str, int], ...]
    diagnostics_by_code: tuple[tuple[str, int], ...]
    excluded_entries: int
    failed_files: int
    skipped_files: int
    describes_full_result: bool = True


@dataclass(frozen=True, slots=True)
class GraphResult:
    schema_version: str
    metadata: GraphMetadata
    summary: GraphSummaryCounts
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    evidence: tuple[EvidenceRecord, ...]
    diagnostics: tuple[GraphDiagnostic, ...]
