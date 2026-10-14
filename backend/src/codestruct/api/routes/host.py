"""Host bridge routes for native desktop integration and folder selection."""

from __future__ import annotations

import os
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, Request

from codestruct.host import (
    FolderValidationError,
    choose_folder_dialog,
    validate_project_folder,
)
from codestruct.jobs.service import AnalysisService

from ..dependencies import analysis_service
from ..errors import ApiError

router = APIRouter(prefix="/api/v1/host", tags=["host"])


def _verify_host_token(
    request: Request,
    x_codestruct_host_token: str | None = Header(None, alias="X-CodeStruct-Host-Token"),
) -> None:
    expected_token = os.environ.get("CODESTRUCT_HOST_TOKEN")
    if expected_token:
        if not x_codestruct_host_token or x_codestruct_host_token != expected_token:
            raise ApiError(
                403,
                "HOST_AUTHENTICATION_REQUIRED",
                "A valid host authentication token is required to invoke desktop host actions.",
            )


@router.post("/choose-folder")
async def choose_project_folder(
    request: Request,
    service: AnalysisService = Depends(analysis_service),
    _auth: None = Depends(_verify_host_token),
) -> dict[str, Any]:
    """Invoke the native Windows folder chooser and automatically register and analyze the selected folder."""
    raw_path = choose_folder_dialog(title="Select Project Folder")
    if not raw_path:
        return {
            "cancelled": True,
            "root_id": None,
            "project_name": None,
            "path": None,
            "analysis_id": None,
        }

    try:
        validated_path = validate_project_folder(raw_path)
    except FolderValidationError as exc:
        raise ApiError(400, "INVALID_PROJECT_FOLDER", str(exc)) from exc

    # Generate safe, deterministic root_id
    base_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", validated_path.name.lower()).strip("_")
    if not base_slug:
        base_slug = "proj"
    root_id = base_slug
    suffix = 1
    while (
        root_id in service.settings.authorized_roots
        and service.settings.authorized_roots[root_id] != validated_path
    ):
        root_id = f"{base_slug}_{suffix}"
        suffix += 1

    # Register root dynamically
    service.settings.authorized_roots[root_id] = validated_path

    # Automatically start initial analysis
    job_record = service.create(
        root_id, relative_path="", refresh=False, compute_metrics=False
    )

    return {
        "cancelled": False,
        "root_id": root_id,
        "project_name": validated_path.name,
        "path": str(validated_path),
        "analysis_id": job_record.analysis_id,
    }
