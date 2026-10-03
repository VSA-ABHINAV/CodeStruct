"""Bundled frontend serving without intercepting versioned API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, MutableMapping

from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles


def frontend_directory() -> Path:
    return Path(__file__).with_name("web")


class SPAStaticFiles(StaticFiles):
    async def get_response(
        self, path: str, scope: MutableMapping[str, Any]
    ) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or "." in Path(path).name:
                raise
            response = FileResponse(frontend_directory() / "index.html")
        request_path = str(scope.get("path", ""))
        if "/assets/" in request_path and "-" in Path(path).name:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers.setdefault("Cache-Control", "no-cache")
        return response
