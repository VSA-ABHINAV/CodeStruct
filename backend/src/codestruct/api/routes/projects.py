"""Safe discovery of configured project capabilities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from codestruct.jobs.service import AnalysisService

from ..dependencies import analysis_service
from ..schemas import ProjectsResponse, ProjectSummary

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _display_name(root_id: str) -> str:
    return root_id.replace("_", " ").replace("-", " ").strip().title()


@router.get("", response_model=ProjectsResponse)
def list_projects(
    request: Request,
    service: AnalysisService = Depends(analysis_service),
) -> ProjectsResponse:
    projects = [
        ProjectSummary(id=root_id, display_name=_display_name(root_id))
        for root_id in sorted(service.settings.authorized_roots)
    ]
    return ProjectsResponse(request_id=request.state.request_id, projects=projects)
