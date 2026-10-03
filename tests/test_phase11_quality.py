"""Phase 11 quality, contract, and failure-boundary regression tests."""

from __future__ import annotations

import ast
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from codestruct.analysis import AnalysisPolicy, parse_project
from codestruct.api.app import create_app
from codestruct.api.pagination import decode_cursor, slice_graph
from codestruct.graph import build_graph, graph_to_dict, graph_to_json
from codestruct.jobs.models import JobRecord, JobState
from codestruct.jobs.registry import InvalidTransitionError, JobRegistry
from codestruct.settings import Settings, load_settings
from codestruct.storage import SQLiteRepository
from codestruct.storage.errors import StorageError
from fastapi.testclient import TestClient

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"
BACKEND_PACKAGE = REPOSITORY / "backend" / "src" / "codestruct"


def settings(database: Path | None = None) -> Settings:
    return Settings(
        authorized_roots={"sample": SAMPLE},
        database_path=database,
        max_concurrent_jobs=1,
        max_queued_jobs=1,
        analysis_timeout_seconds=20,
        cancellation_grace_seconds=1,
        result_retention_seconds=60,
        polling_interval_ms=250,
    )


@pytest.mark.parametrize(
    "states",
    [
        [
            JobState.VALIDATING,
            JobState.QUEUED,
            JobState.SCANNING,
            JobState.PARSING,
            JobState.RESOLVING,
            JobState.BUILDING_GRAPH,
            JobState.COMPLETED,
        ],
        [JobState.VALIDATING, JobState.CACHE_HIT, JobState.COMPLETED],
        [JobState.CANCELLATION_REQUESTED, JobState.CANCELLED],
    ],
)
def test_registry_accepts_documented_paths_and_rejects_post_terminal_changes(states):
    registry = JobRegistry(60)
    registry.add(JobRecord("analysis", "sample", "redacted"))
    for index, state in enumerate(states, start=1):
        record = registry.transition("analysis", state, percent=index * 10)
        assert record.state is state
    with pytest.raises(InvalidTransitionError):
        registry.transition("analysis", JobState.FAILED)


def test_registry_rejects_invalid_transitions_and_decreasing_progress():
    registry = JobRegistry(60)
    registry.add(JobRecord("analysis", "sample", "redacted"))
    with pytest.raises(InvalidTransitionError):
        registry.transition("analysis", JobState.PARSING)
    registry.transition("analysis", JobState.VALIDATING, percent=20)
    with pytest.raises(InvalidTransitionError):
        registry.transition("analysis", JobState.QUEUED, percent=19)


def test_settings_reject_wildcard_cors_and_invalid_limits(monkeypatch):
    monkeypatch.setenv("CODESTRUCT_CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="wildcard"):
        load_settings()
    monkeypatch.setenv("CODESTRUCT_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("CODESTRUCT_MAX_FILES", "0")
    with pytest.raises(ValueError, match="CODESTRUCT_MAX_FILES"):
        load_settings()


def test_graph_is_identical_across_ten_repeated_analyses():
    policy = AnalysisPolicy(authorized_roots=(SAMPLE,))
    payloads = {
        graph_to_json(build_graph(parse_project(SAMPLE, policy))) for _ in range(10)
    }
    assert len(payloads) == 1


def test_cursor_is_bound_to_graph_and_filters():
    policy = AnalysisPolicy(authorized_roots=(SAMPLE,))
    graph = graph_to_dict(build_graph(parse_project(SAMPLE, policy)))
    first = slice_graph(
        graph,
        limit=2,
        cursor=None,
        node_kind=None,
        edge_kind=None,
        resolution_status=None,
    )
    cursor = first["page"]["next_cursor"]
    assert cursor
    with pytest.raises(ValueError, match="invalid graph cursor"):
        decode_cursor(cursor, "different-graph", {"limit": 2})
    with pytest.raises(ValueError, match="invalid graph cursor"):
        slice_graph(
            graph,
            limit=3,
            cursor=cursor,
            node_kind=None,
            edge_kind=None,
            resolution_status=None,
        )


def test_browser_page_title_names_the_product():
    index = (REPOSITORY / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "<title>CodeStruct Architecture Explorer</title>" in index


def test_sqlite_oversized_terminal_write_rolls_back(tmp_path):
    repository = SQLiteRepository(
        tmp_path / "rollback.sqlite3", 60, max_payload_bytes=128
    )
    repository.add(JobRecord("analysis", "sample", "redacted"))
    for state in (
        JobState.VALIDATING,
        JobState.QUEUED,
        JobState.SCANNING,
        JobState.PARSING,
        JobState.RESOLVING,
        JobState.BUILDING_GRAPH,
    ):
        repository.transition("analysis", state)
    with pytest.raises(StorageError, match="storage limit"):
        repository.transition(
            "analysis",
            JobState.COMPLETED,
            graph={"payload": "x" * 1024},
        )
    assert repository.get("analysis").state is JobState.BUILDING_GRAPH


def test_sqlite_supports_bounded_concurrent_independent_writers(tmp_path):
    repository = SQLiteRepository(tmp_path / "concurrent.sqlite3", 60)

    def add(index: int) -> str:
        identifier = f"analysis-{index}"
        repository.add(JobRecord(identifier, "sample", "redacted"))
        return repository.get(identifier).analysis_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        expected = sorted(f"analysis-{index}" for index in range(12))
        assert sorted(pool.map(add, range(12))) == expected


def test_locked_database_fails_boundedly(tmp_path):
    path = tmp_path / "locked.sqlite3"
    repository = SQLiteRepository(path, 60, busy_timeout_ms=10)
    with closing(sqlite3.connect(path, isolation_level=None)) as blocker:
        blocker.execute("BEGIN EXCLUSIVE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            repository.add(JobRecord("analysis", "sample", "redacted"))


@pytest.mark.contract
def test_api_errors_cors_and_openapi_are_structured(tmp_path):
    app = create_app(settings(tmp_path / "api.sqlite3"))
    try:
        with TestClient(app) as client:
            missing = client.get("/api/v1/analyses/not-present")
            assert missing.status_code == 404
            assert set(missing.json()) == {"api_version", "request_id", "error"}
            assert missing.json()["error"]["code"] == "JOB_NOT_FOUND"

            invalid = client.post("/api/v1/analyses", json={})
            assert invalid.status_code == 422
            assert invalid.json()["error"]["code"] == "REQUEST_INVALID"

            unauthorized = client.post(
                "/api/v1/analyses",
                json={"project": {"root_id": "missing", "relative_path": "."}},
            )
            assert unauthorized.status_code == 403
            assert str(REPOSITORY) not in unauthorized.text

            preflight = client.options(
                "/api/v1/analyses",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert (
                preflight.headers["access-control-allow-origin"]
                == "http://localhost:5173"
            )

            schema = client.get("/openapi.json").json()
            for route in (
                "/api/v1/analyses",
                "/api/v1/analyses/{analysis_id}",
                "/api/v1/analyses/{analysis_id}/graph",
                "/api/v1/analyses/{analysis_id}/diagnostics",
            ):
                assert route in schema["paths"]
    finally:
        app.state.analysis_service.shutdown()


def test_core_never_uses_executable_deserialization_or_source_execution():
    forbidden_imports = {"pickle", "marshal"}
    forbidden_calls = {"eval", "exec", "compile", "__import__"}
    for path in BACKEND_PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        imported = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert not (imported & forbidden_imports), path.name
        assert not (calls & forbidden_calls), path.name


def test_installed_package_imports_from_a_different_working_directory(tmp_path):
    completed = subprocess.run(
        [sys.executable, "-c", "import codestruct; print(codestruct.__version__)"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    from codestruct import __version__

    assert completed.stdout.strip() == __version__
