"""Deterministic JSON serialization for canonical graph records."""

from __future__ import annotations

import json
from typing import Any

from .enums import (
    Confidence,
    DiagnosticPhase,
    DiagnosticSeverity,
    EvidenceOrigin,
    NodeKind,
    RelationshipKind,
    ResolutionStatus,
)
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
from .validation import assert_valid_graph


def _attributes(value: tuple[tuple[str, str], ...]) -> dict[str, str]:
    return {key: item for key, item in value}


def _source(value: SourceReference | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "source_unit_id": value.source_unit_id,
        "path": value.path,
        "start_line": value.span.start_line,
        "start_column": value.span.start_column,
        "end_line": value.span.end_line,
        "end_column": value.span.end_column,
    }


def graph_to_dict(graph: GraphResult) -> dict[str, object]:
    assert_valid_graph(graph)
    metadata = graph.metadata
    summary = graph.summary
    return {
        "schema_version": graph.schema_version,
        "metadata": {
            "analysis_id": metadata.analysis_id,
            "result_id": metadata.result_id,
            "graph_id": metadata.graph_id,
            "schema_version": metadata.schema_version,
            "api_version": metadata.api_version,
            "analyzer_version": metadata.analyzer_version,
            "python_runtime": metadata.python_runtime,
            "source_language": metadata.source_language,
            "source_grammar": metadata.source_grammar,
            "policy_fingerprint": metadata.policy_fingerprint,
            "project_fingerprint": metadata.project_fingerprint,
            "started_at": metadata.started_at,
            "finished_at": metadata.finished_at,
            "duration_ms": metadata.duration_ms,
            "cache": _attributes(metadata.cache),
            "partial": metadata.partial,
            "partial_reasons": list(metadata.partial_reasons),
            "exclusions": _attributes(metadata.exclusions),
            "limits": _attributes(metadata.limits),
            "metrics_computed": metadata.metrics_computed,
        },
        "summary": {
            "source_units_total": summary.source_units_total,
            "nodes_total": summary.nodes_total,
            "edges_total": summary.edges_total,
            "evidence_total": summary.evidence_total,
            "diagnostics_total": summary.diagnostics_total,
            "nodes_by_kind": dict(summary.nodes_by_kind),
            "edges_by_kind": dict(summary.edges_by_kind),
            "edges_by_resolution": dict(summary.edges_by_resolution),
            "edges_by_confidence": dict(summary.edges_by_confidence),
            "diagnostics_by_severity": dict(summary.diagnostics_by_severity),
            "diagnostics_by_code": dict(summary.diagnostics_by_code),
            "excluded_entries": summary.excluded_entries,
            "failed_files": summary.failed_files,
            "skipped_files": summary.skipped_files,
            "describes_full_result": summary.describes_full_result,
        },
        "nodes": [
            {
                "id": item.id,
                "kind": item.kind.value,
                "name": item.name,
                "qualified_name": item.qualified_name,
                "parent_id": item.parent_id,
                "module_id": item.module_id,
                "file_id": item.file_id,
                "location": _source(item.location),
                "modifiers": list(item.modifiers),
                "attributes": _attributes(item.attributes),
            }
            for item in graph.nodes
        ],
        "edges": [
            {
                "id": item.id,
                "kind": item.kind.value,
                "source_id": item.source_id,
                "target_id": item.target_id,
                "target_reference": item.target_reference,
                "resolution_status": item.resolution.status.value,
                "confidence": item.resolution.confidence.value,
                "confidence_reason": item.resolution.reason_code,
                "candidate_ids": list(item.resolution.candidate_ids),
                "evidence_ids": list(item.evidence_ids),
                "occurrence_count": item.occurrence_count,
                "diagnostic_ids": list(item.diagnostic_ids),
                "attributes": _attributes(item.attributes),
            }
            for item in graph.edges
        ],
        "evidence": [
            {
                "evidence_id": item.id,
                "origin": item.origin.value,
                "observation_kind": item.observation_kind,
                "location": _source(item.location),
                "observed_text_hash": item.observed_text_hash,
                "excerpt": item.excerpt,
                "explanation": item.explanation,
                "expression": item.expression,
            }
            for item in graph.evidence
        ],
        "diagnostics": [
            {
                "id": item.id,
                "code": item.code,
                "severity": item.severity.value,
                "phase": item.phase.value,
                "message": item.message,
                "location": _source(item.location),
                "entity_id": item.entity_id,
                "edge_id": item.edge_id,
                "recoverable": item.recoverable,
                "consequence": item.consequence,
                "suggested_action": item.suggested_action,
                "details": _attributes(item.details),
            }
            for item in graph.diagnostics
        ],
    }


def graph_to_json(graph: GraphResult) -> str:
    return json.dumps(
        graph_to_dict(graph), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _pairs(value: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(item)) for key, item in value.items()))


def _read_source(value: dict[str, Any] | None) -> SourceReference | None:
    if value is None:
        return None
    return SourceReference(
        source_unit_id=value["source_unit_id"],
        path=value["path"],
        span=SourceSpan(
            value["start_line"],
            value["start_column"],
            value["end_line"],
            value["end_column"],
        ),
    )


def graph_from_dict(value: dict[str, Any]) -> GraphResult:
    metadata_value = value["metadata"]
    summary_value = value["summary"]
    metadata = GraphMetadata(
        analysis_id=metadata_value["analysis_id"],
        result_id=metadata_value["result_id"],
        graph_id=metadata_value["graph_id"],
        schema_version=metadata_value["schema_version"],
        api_version=metadata_value["api_version"],
        analyzer_version=metadata_value["analyzer_version"],
        python_runtime=metadata_value["python_runtime"],
        source_language=metadata_value["source_language"],
        source_grammar=metadata_value["source_grammar"],
        policy_fingerprint=metadata_value["policy_fingerprint"],
        project_fingerprint=metadata_value["project_fingerprint"],
        started_at=metadata_value["started_at"],
        finished_at=metadata_value["finished_at"],
        duration_ms=metadata_value["duration_ms"],
        cache=_pairs(metadata_value["cache"]),
        partial=metadata_value["partial"],
        partial_reasons=tuple(metadata_value["partial_reasons"]),
        exclusions=_pairs(metadata_value["exclusions"]),
        limits=_pairs(metadata_value["limits"]),
        metrics_computed=metadata_value.get("metrics_computed", False),
    )
    summary = GraphSummaryCounts(
        source_units_total=summary_value["source_units_total"],
        nodes_total=summary_value["nodes_total"],
        edges_total=summary_value["edges_total"],
        evidence_total=summary_value["evidence_total"],
        diagnostics_total=summary_value["diagnostics_total"],
        nodes_by_kind=tuple(sorted(summary_value["nodes_by_kind"].items())),
        edges_by_kind=tuple(sorted(summary_value["edges_by_kind"].items())),
        edges_by_resolution=tuple(sorted(summary_value["edges_by_resolution"].items())),
        edges_by_confidence=tuple(sorted(summary_value["edges_by_confidence"].items())),
        diagnostics_by_severity=tuple(
            sorted(summary_value["diagnostics_by_severity"].items())
        ),
        diagnostics_by_code=tuple(sorted(summary_value["diagnostics_by_code"].items())),
        excluded_entries=summary_value["excluded_entries"],
        failed_files=summary_value["failed_files"],
        skipped_files=summary_value["skipped_files"],
        describes_full_result=summary_value["describes_full_result"],
    )
    nodes = tuple(
        GraphNode(
            id=item["id"],
            kind=NodeKind(item["kind"]),
            name=item["name"],
            qualified_name=item["qualified_name"],
            parent_id=item["parent_id"],
            module_id=item["module_id"],
            file_id=item["file_id"],
            location=_read_source(item["location"]),
            modifiers=tuple(item["modifiers"]),
            attributes=_pairs(item["attributes"]),
        )
        for item in value["nodes"]
    )
    edges = tuple(
        GraphEdge(
            id=item["id"],
            kind=RelationshipKind(item["kind"]),
            source_id=item["source_id"],
            target_id=item["target_id"],
            target_reference=item["target_reference"],
            resolution=ResolutionRecord(
                ResolutionStatus(item["resolution_status"]),
                Confidence(item["confidence"]),
                item["confidence_reason"],
                tuple(item["candidate_ids"]),
            ),
            evidence_ids=tuple(item["evidence_ids"]),
            occurrence_count=item["occurrence_count"],
            diagnostic_ids=tuple(item["diagnostic_ids"]),
            attributes=_pairs(item["attributes"]),
        )
        for item in value["edges"]
    )
    evidence = tuple(
        EvidenceRecord(
            id=item["evidence_id"],
            origin=EvidenceOrigin(item["origin"]),
            observation_kind=item["observation_kind"],
            location=_read_source(item["location"]),
            observed_text_hash=item["observed_text_hash"],
            excerpt=item["excerpt"],
            explanation=item["explanation"],
            expression=item["expression"],
        )
        for item in value["evidence"]
    )
    diagnostics = tuple(
        GraphDiagnostic(
            id=item["id"],
            code=item["code"],
            severity=DiagnosticSeverity(item["severity"]),
            phase=DiagnosticPhase(item["phase"]),
            message=item["message"],
            location=_read_source(item["location"]),
            entity_id=item["entity_id"],
            edge_id=item["edge_id"],
            recoverable=item["recoverable"],
            consequence=item["consequence"],
            suggested_action=item["suggested_action"],
            details=_pairs(item["details"]),
        )
        for item in value["diagnostics"]
    )
    graph = GraphResult(
        value["schema_version"], metadata, summary, nodes, edges, evidence, diagnostics
    )
    assert_valid_graph(graph)
    return graph


def graph_from_json(value: str) -> GraphResult:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("graph JSON must contain an object")
    return graph_from_dict(decoded)
