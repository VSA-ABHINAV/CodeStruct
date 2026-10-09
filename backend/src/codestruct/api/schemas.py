"""Strict Pydantic DTOs for API v1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectSelection(StrictModel):
    root_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    capability_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    relative_path: str = Field(default=".", min_length=1, max_length=1024)

    @field_validator("relative_path")
    @classmethod
    def no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("path contains an invalid character")
        return value

    @model_validator(mode="after")
    def validate_identifier(self) -> ProjectSelection:
        effective = self.capability_id or self.root_id
        if not effective:
            raise ValueError("Either capability_id or root_id is required.")
        if not self.root_id:
            self.root_id = effective
        return self


class AnalysisOptions(StrictModel):
    source_grammar: str | None = Field(default=None, pattern=r"^3\.(10|11|12|13|14)$")
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    metrics: bool = False


class CreateAnalysisRequest(StrictModel):
    project: ProjectSelection
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)
    refresh: bool = False
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class Progress(StrictModel):
    phase: str
    completed: int
    total: int
    unit: str
    percent: int | None
    message_code: str
    updated_at: str


class Links(StrictModel):
    self: str
    graph: str | None
    diagnostics: str


class JobResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    analysis_id: str
    state: str
    terminal: bool
    revision: int
    progress: Progress
    created_at: str
    started_at: str | None
    updated_at: str
    completed_at: str | None
    partial: bool
    cache_hit: bool = False
    diagnostics_summary: dict[str, int]
    result: dict[str, object] | None
    links: Links
    duplicate_disposition: str | None = None


class DiagnosticsResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    schema_version: str = "1.0.0"
    analysis_id: str
    provisional: bool
    items: list[dict[str, object]]
    totals: dict[str, int]


class ProjectSummary(StrictModel):
    id: str
    display_name: str
    description: str | None = None
    available: bool = True


class ProjectsResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    projects: list[ProjectSummary]


class EditorSelectionRequest(StrictModel):
    file_path: str = Field(min_length=1, max_length=4096)

    @field_validator("file_path")
    @classmethod
    def no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("path contains an invalid character")
        return value.strip()


class EditorSelectionResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    capability_id: str
    root_id: str
    relative_path: str
    display_name: str


class NodeExplanationResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    node_id: str
    name: str
    kind: str
    role: str
    summary: str
    dependencies_summary: str
    metrics_summary: str
    recommendations: list[str]
    prompt: str | None = None
    provider: str = "rule-based"


class ExecuteRuntimeRequest(StrictModel):
    target_file: str = Field(default="main.py", min_length=1, max_length=4096)
    entry_function: str | None = Field(default=None, max_length=256)
    args: list[str] = Field(default_factory=list)
    timeout_seconds: float = Field(default=10.0, ge=0.5, le=30.0)
    max_events: int = Field(default=50000, ge=100, le=500000)

    @field_validator("target_file")
    @classmethod
    def no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("path contains an invalid character")
        return value.strip()


class RuntimeSessionSummary(StrictModel):
    session_id: str
    analysis_id: str
    target_file: str
    entry_function: str | None = None
    status: str
    total_calls: int
    execution_time_seconds: float
    overhead_seconds: float
    covered_nodes: int
    total_nodes: int
    coverage_percent: float
    trace_events_count: int
    created_at: str
    error_message: str | None = None


class ExecuteRuntimeResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    session: RuntimeSessionSummary
    graph_updated: bool = True
    links: Links


class RuntimeSessionsResponse(StrictModel):
    api_version: Literal["v1"] = "v1"
    request_id: str
    analysis_id: str
    sessions: list[RuntimeSessionSummary]
