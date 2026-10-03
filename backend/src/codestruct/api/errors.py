"""Safe public API error envelopes."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        recoverable: bool = True,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.retry_after_seconds = retry_after_seconds


async def api_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ApiError):
        raise error
    request_id = getattr(request.state, "request_id", "unavailable")
    return JSONResponse(
        status_code=error.status,
        content={
            "api_version": "v1",
            "request_id": request_id,
            "error": {
                "code": error.code,
                "message": error.message,
                "recoverable": error.recoverable,
                "field_errors": [],
                "safe_context": {},
                "retry_after_seconds": error.retry_after_seconds,
            },
        },
    )
