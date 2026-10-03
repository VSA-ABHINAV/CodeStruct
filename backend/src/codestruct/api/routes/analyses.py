"""Analysis job HTTP resources."""

from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends, Query, Request, Response

from codestruct.analysis.llm_summary import explain_node
from codestruct.graph.export_dot import graph_to_dot
from codestruct.jobs.executor import QueueFullError
from codestruct.jobs.models import TERMINAL_STATES, JobRecord, JobState
from codestruct.jobs.service import AnalysisService, ProjectSelectionError

from ..dependencies import analysis_service
from ..errors import ApiError
from ..pagination import slice_graph
from ..schemas import (
    CreateAnalysisRequest,
    DiagnosticsResponse,
    JobResponse,
    Links,
    NodeExplanationResponse,
    Progress,
)

router = APIRouter(prefix="/api/v1/analyses", tags=["analyses"])


def _job(
    record: JobRecord, request_id: str, retry_ms: int, duplicate: str | None = None
) -> JobResponse:
    terminal = record.state in TERMINAL_STATES
    graph = record.graph
    usable = graph is not None and record.state in {
        JobState.COMPLETED,
        JobState.PARTIALLY_COMPLETED,
    }
    counts = Counter(
        str(item.get("severity", "warning")) for item in record.diagnostics
    )
    result = None
    if usable and graph is not None:
        metadata_value = graph.get("metadata")
        summary_value = graph.get("summary")
        metadata = metadata_value if isinstance(metadata_value, dict) else {}
        summary = summary_value if isinstance(summary_value, dict) else {}
        result = {
            "result_id": metadata.get("result_id"),
            "graph_id": metadata.get("graph_id"),
            "schema_version": graph.get("schema_version"),
            "partial": record.partial,
            "cache_hit": record.cache_hit,
            "summary": summary,
        }
    base = f"/api/v1/analyses/{record.analysis_id}"
    return JobResponse(
        request_id=request_id,
        analysis_id=record.analysis_id,
        state=record.state.value,
        terminal=terminal,
        revision=record.revision,
        progress=Progress(
            phase=record.state.value,
            completed=record.percent or 0,
            total=100,
            unit="milestone",
            percent=record.percent,
            message_code=record.message_code,
            updated_at=record.updated_at,
        ),
        created_at=record.created_at,
        started_at=record.started_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
        partial=record.partial,
        cache_hit=record.cache_hit,
        diagnostics_summary={
            key: counts.get(key, 0) for key in ("info", "warning", "error")
        },
        result=result,
        links=Links(
            self=base,
            graph=f"{base}/graph" if usable else None,
            diagnostics=f"{base}/diagnostics",
        ),
        duplicate_disposition=duplicate,
    )


def _require(service: AnalysisService, analysis_id: str) -> JobRecord:
    record = service.get(analysis_id)
    if record is None:
        if service.is_expired(analysis_id):
            raise ApiError(
                410, "RESULT_EXPIRED", "The requested analysis result has expired."
            )
        raise ApiError(
            404,
            "JOB_NOT_FOUND",
            "The requested analysis does not exist or has expired.",
        )
    return record


@router.post("", response_model=JobResponse, status_code=202)
def create_analysis(
    body: CreateAnalysisRequest,
    request: Request,
    response: Response,
    service: AnalysisService = Depends(analysis_service),
) -> JobResponse:
    if (
        body.options.include_patterns is not None
        or body.options.exclude_patterns is not None
        or body.options.source_grammar is not None
    ):
        raise ApiError(
            400,
            "OPTION_UNSUPPORTED",
            "Custom analysis options are not available in this version.",
        )
    try:
        effective_root = body.project.capability_id or body.project.root_id
        if not effective_root:
            raise ApiError(
                400,
                "PROJECT_SELECTION_REQUIRED",
                "Either capability_id or root_id is required.",
            )
        record = service.create(
            effective_root,
            body.project.relative_path,
            refresh=body.refresh,
            compute_metrics=body.options.metrics,
        )

    except ProjectSelectionError as error:
        raise ApiError(
            403 if error.code == "PROJECT_UNAUTHORIZED" else 404, error.code, str(error)
        ) from None
    except QueueFullError:
        raise ApiError(
            429,
            "QUEUE_FULL",
            "The analysis queue is currently full.",
            retry_after_seconds=1,
        ) from None
    response.headers["Location"] = f"/api/v1/analyses/{record.analysis_id}"
    response.headers["Retry-After"] = str(
        max(1, service.settings.polling_interval_ms // 1000)
    )
    if record.cache_hit:
        response.status_code = 200
    return _job(
        record,
        request.state.request_id,
        service.settings.polling_interval_ms,
        "cache_hit" if record.cache_hit else "new",
    )


@router.get("/{analysis_id}", response_model=JobResponse)
def get_analysis(
    analysis_id: str,
    request: Request,
    service: AnalysisService = Depends(analysis_service),
) -> JobResponse:
    return _job(
        _require(service, analysis_id),
        request.state.request_id,
        service.settings.polling_interval_ms,
    )


@router.get("/{analysis_id}/graph")
def get_graph(
    analysis_id: str,
    response: Response,
    limit: int | None = Query(default=None, ge=1),
    cursor: str | None = None,
    node_kind: str | None = None,
    edge_kind: str | None = None,
    resolution_status: str | None = None,
    service: AnalysisService = Depends(analysis_service),
) -> dict[str, object]:
    record = _require(service, analysis_id)
    if record.graph is None:
        if record.state in TERMINAL_STATES:
            raise ApiError(
                409, "RESULT_UNAVAILABLE", "This analysis has no usable graph result."
            )
        raise ApiError(409, "RESULT_NOT_READY", "The graph result is not ready yet.")
    raw_size = len(json.dumps(record.graph, separators=(",", ":")).encode())
    response.headers["Cache-Control"] = "private, no-store"
    if limit is None and raw_size > service.settings.max_full_graph_bytes:
        raise ApiError(
            413,
            "GRAPH_TOO_LARGE",
            "The complete graph exceeds the response limit; request a bounded page.",
        )
    if limit is None:
        return record.graph
    if limit > service.settings.max_graph_page_size:
        raise ApiError(
            413,
            "PAGE_LIMIT_EXCEEDED",
            "The requested graph page exceeds the server limit.",
        )
    try:
        return slice_graph(
            record.graph,
            limit=limit,
            cursor=cursor,
            node_kind=node_kind,
            edge_kind=edge_kind,
            resolution_status=resolution_status,
        )
    except ValueError:
        raise ApiError(
            400,
            "CURSOR_INVALID",
            "The graph cursor is invalid or belongs to another result.",
        ) from None


@router.get("/{analysis_id}/export/dot")
def export_dot(
    analysis_id: str,
    service: AnalysisService = Depends(analysis_service),
) -> Response:
    record = _require(service, analysis_id)
    if record.graph is None:
        raise ApiError(
            409,
            "GRAPH_UNAVAILABLE",
            "The analysis has not produced a graph result yet.",
        )
    dot_content = graph_to_dot(record.graph)
    filename = f"codestruct-{analysis_id}.dot"
    return Response(
        content=dot_content,
        media_type="text/vnd.graphviz",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{analysis_id}/nodes/{node_id}/explain",
    response_model=NodeExplanationResponse,
)
def explain_analysis_node(
    analysis_id: str,
    node_id: str,
    request: Request,
    provider: str = Query(
        "auto", description="LLM provider: 'auto', 'rule-based', or 'llm'"
    ),
    service: AnalysisService = Depends(analysis_service),
) -> NodeExplanationResponse:
    record = _require(service, analysis_id)
    if record.graph is None:
        raise ApiError(
            409,
            "GRAPH_UNAVAILABLE",
            "The analysis has not produced a graph result yet.",
        )
    try:
        explanation = explain_node(record.graph, node_id, provider=provider)
    except KeyError:
        raise ApiError(
            404,
            "NODE_NOT_FOUND",
            f"Node '{node_id}' does not exist in this analysis graph.",
        ) from None
    return NodeExplanationResponse(
        request_id=request.state.request_id,
        node_id=explanation.node_id,
        name=explanation.name,
        kind=explanation.kind,
        role=explanation.role,
        summary=explanation.summary,
        dependencies_summary=explanation.dependencies_summary,
        metrics_summary=explanation.metrics_summary,
        recommendations=explanation.recommendations,
        prompt=explanation.prompt,
        provider=explanation.provider,
    )


@router.get("/{analysis_id}/diagnostics", response_model=DiagnosticsResponse)
def get_diagnostics(
    analysis_id: str,
    request: Request,
    service: AnalysisService = Depends(analysis_service),
) -> DiagnosticsResponse:
    record = _require(service, analysis_id)
    counts = Counter(
        str(item.get("severity", "warning")) for item in record.diagnostics
    )
    return DiagnosticsResponse(
        request_id=request.state.request_id,
        analysis_id=analysis_id,
        provisional=record.state not in TERMINAL_STATES,
        items=record.diagnostics,
        totals=dict(counts),
    )


@router.delete("/{analysis_id}", response_model=JobResponse)
def cancel_analysis(
    analysis_id: str,
    request: Request,
    response: Response,
    service: AnalysisService = Depends(analysis_service),
) -> JobResponse:
    record = _require(service, analysis_id)
    if record.state in {
        JobState.COMPLETED,
        JobState.PARTIALLY_COMPLETED,
        JobState.FAILED,
    }:
        raise ApiError(
            409,
            "JOB_TERMINAL",
            "This analysis is already in a terminal state.",
            recoverable=False,
        )
    updated = service.cancel(analysis_id)
    if updated is None:
        raise ApiError(
            404,
            "JOB_NOT_FOUND",
            "The requested analysis does not exist or has expired.",
        )
    response.status_code = 200 if updated.state is JobState.CANCELLED else 202
    return _job(updated, request.state.request_id, service.settings.polling_interval_ms)
