"""FastAPI application factory and transitional legacy routes."""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from codestruct import __version__
from codestruct.jobs.service import AnalysisService
from codestruct.settings import Settings, load_settings
from codestruct.storage.errors import StorageError
from codestruct.web import SPAStaticFiles, frontend_directory

from .errors import ApiError, api_error_handler
from .routes.analyses import router as analyses_router
from .routes.editor import router as editor_router
from .routes.navigate import router as navigate_router
from .routes.projects import router as projects_router


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or load_settings()
    service = AnalysisService(configuration)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        service.shutdown()

    application = FastAPI(title="CodeStruct", version=__version__, lifespan=lifespan)
    application.state.analysis_service = service

    @application.middleware("http")
    async def request_identity(request: Request, call_next):
        request.state.request_id = "req_" + secrets.token_urlsafe(9)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "private, no-store")
        return response

    application.add_exception_handler(ApiError, api_error_handler)

    @application.exception_handler(StorageError)
    @application.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, _error: Exception):
        return JSONResponse(
            status_code=503,
            content={
                "api_version": "v1",
                "request_id": request.state.request_id,
                "error": {
                    "code": "STORAGE_UNAVAILABLE",
                    "message": "Persistent analysis storage is temporarily unavailable.",
                    "recoverable": True,
                    "field_errors": [],
                    "safe_context": {},
                    "retry_after_seconds": 1,
                },
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "api_version": "v1",
                "request_id": request.state.request_id,
                "error": {
                    "code": "REQUEST_INVALID",
                    "message": "The request did not match the API contract.",
                    "recoverable": True,
                    "field_errors": [],
                    "safe_context": {},
                    "retry_after_seconds": None,
                },
            },
        )

    if configuration.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(configuration.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Accept", "Content-Type"],
        )
    application.include_router(projects_router)
    application.include_router(analyses_router)
    application.include_router(editor_router)
    application.include_router(navigate_router)

    @application.get("/")
    def home():
        return {"message": "CodeStruct Backend is Working!"}

    @application.get("/health/live")
    def live():
        return {"status": "live", "version": __version__}

    @application.get("/health/ready")
    def ready():
        if not service.executor.available:
            raise ApiError(
                status=503,
                code="SERVICE_NOT_READY",
                message="The analysis service is not ready.",
                recoverable=True,
            )
        service.registry.get("__readiness__")
        return {"status": "ready", "version": __version__}

    @application.get("/api/v1/version")
    def version():
        return {"api_version": "v1", "version": __version__}

    @application.get("/analyze")
    def analyze_legacy():
        # Transitional frozen contract; removed only after migration exit gates pass.
        from analyzer import analyze_project, create_dependency_graph

        project = Path(__file__).resolve().parents[4] / "sample_project"
        return {
            "files": analyze_project(project),
            "dependencies": create_dependency_graph(project),
        }

    web = frontend_directory()
    if web.joinpath("index.html").is_file():
        application.mount(
            "/app", SPAStaticFiles(directory=web, html=True), name="frontend"
        )
    else:

        @application.get("/app", status_code=503)
        def frontend_missing():
            return {
                "error": "Bundled frontend assets are not available in this checkout."
            }

    return application


app = create_app()
