"""Trusted local editor capability registration."""

from __future__ import annotations

import ipaddress
import urllib.parse

from fastapi import APIRouter, Depends, Request

from codestruct.jobs.service import AnalysisService, ProjectSelectionError

from ..dependencies import analysis_service
from ..errors import ApiError
from ..schemas import EditorSelectionRequest, EditorSelectionResponse

router = APIRouter(prefix="/api/v1/editor", tags=["editor"])


def _is_loopback_client(request: Request) -> bool:
    if not request.client:
        return True
    host = request.client.host
    if not host or host.lower() in (
        "127.0.0.1",
        "localhost",
        "::1",
        "testclient",
        "testserver",
    ):
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _validate_trusted_origin(request: Request) -> None:
    if not _is_loopback_client(request):
        raise ApiError(
            403,
            "EDITOR_ACCESS_DENIED",
            "Editor integration endpoints are only accessible from loopback.",
        )
    origin = request.headers.get("origin")
    if origin:
        parsed = urllib.parse.urlsplit(origin)
        hostname = (parsed.hostname or "").lower()
        if hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
            "testclient",
            "testserver",
        ):
            raise ApiError(
                403,
                "UNTRUSTED_ORIGIN",
                f"Requests from untrusted origin '{origin}' are forbidden.",
            )
    referer = request.headers.get("referer")
    if referer:
        parsed_ref = urllib.parse.urlsplit(referer)
        hostname = (parsed_ref.hostname or "").lower()
        if hostname and hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
            "testclient",
            "testserver",
        ):
            raise ApiError(
                403,
                "UNTRUSTED_ORIGIN",
                f"Requests from untrusted referer '{referer}' are forbidden.",
            )


@router.post("/selection", response_model=EditorSelectionResponse)
def register_editor_selection(
    body: EditorSelectionRequest,
    request: Request,
    service: AnalysisService = Depends(analysis_service),
) -> EditorSelectionResponse:
    _validate_trusted_origin(request)

    try:
        capability = service.register_editor_file(body.file_path)
    except ProjectSelectionError as error:
        status_code = (
            403
            if error.code in ("PROJECT_UNAUTHORIZED", "PERMISSION_DENIED")
            else 400
            if error.code in ("INVALID_PATH", "UNSUPPORTED_EXTENSION")
            else 404
        )
        raise ApiError(status_code, error.code, str(error)) from None
    except Exception as error:
        raise ApiError(
            400,
            "INVALID_SELECTION",
            f"The specified file cannot be analyzed: {error}",
        ) from None

    return EditorSelectionResponse(
        request_id=request.state.request_id,
        capability_id=capability.capability_id,
        root_id=capability.capability_id,
        relative_path=capability.filename,
        display_name=capability.filename,
    )
