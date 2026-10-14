"""Directory tree and symbol hierarchy API endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from codestruct.analysis.tree import build_project_tree
from codestruct.jobs.service import AnalysisService

from ..dependencies import analysis_service
from ..errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["tree"])


@router.get("/analyses/{analysis_id}/tree")
def get_analysis_tree(
    analysis_id: str,
    request: Request,
    service: AnalysisService = Depends(analysis_service),
) -> dict[str, Any]:
    """Retrieve the full directory structure and nested Python symbol hierarchy for an analysis."""
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

    project_root = Path(record.project_root)
    if not project_root.exists() or not project_root.is_dir():
        raise ApiError(
            404,
            "ROOT_NOT_FOUND",
            f"Project directory '{project_root}' is not accessible.",
        )

    graph_nodes = None
    if record.graph and isinstance(record.graph, dict):
        raw_nodes = record.graph.get("nodes")
        if isinstance(raw_nodes, list):
            graph_nodes = raw_nodes

    tree, excluded = build_project_tree(project_root, graph_nodes=graph_nodes)

    return {
        "api_version": "v1",
        "request_id": request.state.request_id,
        "analysis_id": analysis_id,
        "root_id": record.root_id,
        "root_path": str(project_root.resolve()),
        "tree": tree,
        "excluded": excluded,
    }


@router.get("/projects/{root_id}/tree")
def get_project_tree(
    root_id: str,
    request: Request,
    service: AnalysisService = Depends(analysis_service),
) -> dict[str, Any]:
    """Retrieve the directory structure for an authorized root without requiring a completed analysis."""
    project_root = service.settings.authorized_roots.get(root_id)
    if project_root is None:
        raise ApiError(
            404,
            "PROJECT_NOT_FOUND",
            f"Project root '{root_id}' is not authorized or not found.",
        )

    p_root = Path(project_root)
    if not p_root.exists() or not p_root.is_dir():
        raise ApiError(
            404,
            "ROOT_NOT_FOUND",
            f"Project directory '{project_root}' is not accessible.",
        )

    tree, excluded = build_project_tree(p_root, graph_nodes=None)

    return {
        "api_version": "v1",
        "request_id": request.state.request_id,
        "analysis_id": None,
        "root_id": root_id,
        "root_path": str(p_root.resolve()),
        "tree": tree,
        "excluded": excluded,
    }
