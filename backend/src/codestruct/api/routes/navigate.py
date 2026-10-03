"""Editor navigation endpoint: lets the frontend request the IDE to open a file."""

from __future__ import annotations

import ipaddress
import urllib.parse
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestruct.jobs.service import AnalysisService, ProjectSelectionError

from ..dependencies import analysis_service
from ..errors import ApiError

router = APIRouter(prefix="/api/v1/editor", tags=["editor"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NavigateRequest(StrictModel):
    """Body for POST /api/v1/editor/navigate — sent by the frontend."""

    session_token: str = Field(
        min_length=1,
        max_length=128,
        description="Active editor capability ID returned by POST /api/v1/editor/selection.",
    )
    relative_path: str = Field(
        min_length=1,
        max_length=4096,
        description="Project-relative path of the file to open within authorized scope.",
    )
    line: int = Field(ge=1, description="1-indexed line number.")
    column: int | None = Field(
        default=None, ge=1, description="1-indexed column number."
    )

    @field_validator("relative_path")
    @classmethod
    def no_nul(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("path contains an invalid character")
        return v


class NavigateResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    command_id: str
    session_token: str
    status: str  # "queued"


class PendingNavigateResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    has_command: bool
    command_id: str | None = None
    relative_path: str | None = None
    line: int | None = None
    column: int | None = None


class AcknowledgeRequest(StrictModel):
    session_token: str = Field(min_length=1, max_length=128)
    command_id: str = Field(min_length=1, max_length=64)
    status: Literal["delivered", "failed"] = "delivered"
    reason: str | None = Field(default=None, max_length=256)


class AcknowledgeResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    acknowledged: bool
    status: str = "delivered"
    reason: str | None = None


# ---------------------------------------------------------------------------
# Loopback / Local & Origin check
# ---------------------------------------------------------------------------


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
            "Navigation requests are only permitted from local loopback origins.",
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/navigate", response_model=NavigateResponse)
def post_navigate_command(
    body: NavigateRequest,
    request: Request,
    service: AnalysisService = Depends(analysis_service),
) -> NavigateResponse:
    """Frontend → backend: request the IDE to open a specific file at a line.

    The session_token must identify an active, unexpired editor session.
    A public project alias is not an editor credential.
    The relative_path must reside within the permitted source scope of the session.
    """
    _validate_trusted_origin(request)

    try:
        cmd = service.queue_editor_navigation(
            capability_id=body.session_token,
            relative_path=body.relative_path,
            line=body.line,
            column=body.column,
        )
    except ProjectSelectionError as error:
        status_code = (
            403
            if error.code
            in ("SESSION_UNAUTHORIZED", "SCOPE_UNAUTHORIZED", "PROJECT_UNAUTHORIZED")
            else 404
            if error.code == "PROJECT_NOT_FOUND"
            else 400
        )
        raise ApiError(status_code, error.code, str(error)) from None

    return NavigateResponse(
        request_id=request.state.request_id,
        command_id=cmd.command_id,
        session_token=body.session_token,
        status=cmd.status,
    )


@router.get("/navigate/pending", response_model=PendingNavigateResponse)
def get_pending_navigate(
    request: Request,
    session_token: str = Query(min_length=1, max_length=128),
    service: AnalysisService = Depends(analysis_service),
) -> PendingNavigateResponse:
    """Thonny plugin → backend: poll for a pending navigate command.

    Only accessible from loopback.
    Revalidates active session and file scope before delivery.
    """
    _validate_trusted_origin(request)

    try:
        cmd = service.get_pending_navigation(session_token)
    except ProjectSelectionError as error:
        status_code = 403 if error.code == "SESSION_UNAUTHORIZED" else 400
        raise ApiError(status_code, error.code, str(error)) from None

    if cmd is None:
        return PendingNavigateResponse(
            request_id=request.state.request_id,
            has_command=False,
        )

    return PendingNavigateResponse(
        request_id=request.state.request_id,
        has_command=True,
        command_id=cmd.command_id,
        relative_path=cmd.relative_path,
        line=cmd.line,
        column=cmd.column,
    )


@router.post("/navigate/acknowledge", response_model=AcknowledgeResponse)
def acknowledge_navigate_command(
    body: AcknowledgeRequest,
    request: Request,
    service: AnalysisService = Depends(analysis_service),
) -> AcknowledgeResponse:
    """Thonny plugin → backend: mark a navigate command as consumed.

    Only accessible from loopback.
    Matches command ID to pending command and records delivered or failed outcome.
    """
    _validate_trusted_origin(request)

    try:
        acknowledged, outcome = service.acknowledge_navigation(
            capability_id=body.session_token,
            command_id=body.command_id,
            status=body.status,
            reason=body.reason,
        )
    except ProjectSelectionError as error:
        status_code = 403 if error.code == "SESSION_UNAUTHORIZED" else 400
        raise ApiError(status_code, error.code, str(error)) from None

    if not acknowledged:
        return AcknowledgeResponse(
            request_id=request.state.request_id,
            acknowledged=False,
            status=outcome,  # machine-readable code: "unknown_command", "command_expired", etc.
            reason=None,
        )

    return AcknowledgeResponse(
        request_id=request.state.request_id,
        acknowledged=acknowledged,
        status=outcome,
        reason=body.reason if outcome == "failed" else None,
    )
