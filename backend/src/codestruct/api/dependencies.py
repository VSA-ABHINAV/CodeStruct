"""FastAPI dependency accessors."""

from fastapi import Request

from codestruct.jobs.service import AnalysisService


def analysis_service(request: Request) -> AnalysisService:
    return request.app.state.analysis_service
