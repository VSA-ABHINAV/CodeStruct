"""Tests for Graphviz DOT export conversion and HTTP endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from codestruct.api.app import create_app
from codestruct.graph.export_dot import graph_to_dot
from codestruct.jobs.models import JobRecord, JobState
from codestruct.settings import Settings
from fastapi.testclient import TestClient

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"


def test_graph_to_dot_generates_valid_syntax():
    graph_dict = {
        "metadata": {"analysis_id": "test_ana_123"},
        "nodes": [
            {
                "id": "node_1",
                "name": "UserModel",
                "kind": "class",
                "qualified_name": "app.models.UserModel",
                "attributes": {"fan_in": "2", "fan_out": "3", "instability": "0.60"},
            },
            {
                "id": "node_2",
                "name": "authenticate",
                "kind": "function",
                "qualified_name": "app.auth.authenticate",
                "attributes": {},
            },
        ],
        "edges": [
            {
                "id": "edge_1",
                "source_id": "node_2",
                "target_id": "node_1",
                "kind": "calls",
                "resolution_status": "resolved",
            }
        ],
    }

    dot = graph_to_dot(graph_dict)
    assert dot.startswith("digraph ")
    assert "node_node_1" in dot
    assert "node_node_2" in dot
    assert "UserModel" in dot
    assert "authenticate" in dot
    assert "node_node_2 -> node_node_1" in dot
    assert 'label="calls"' in dot
    assert dot.endswith("}\n")


@pytest.fixture(scope="module")
def app_client():
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield app, c
    if hasattr(app.state, "analysis_service"):
        app.state.analysis_service.shutdown()


def test_get_export_dot_endpoint(app_client):
    app, client = app_client
    service = app.state.analysis_service

    # Create and add a completed job record with a mock graph
    job = JobRecord(
        "ana_dot_test",
        "sample",
        str(SAMPLE),
        state=JobState.COMPLETED,
        percent=100,
        graph={
            "metadata": {"analysis_id": "ana_dot_test"},
            "nodes": [
                {
                    "id": "n1",
                    "name": "App",
                    "kind": "class",
                    "qualified_name": "pkg.App",
                }
            ],
            "edges": [],
        },
    )
    service.registry.add(job)

    resp = client.get("/api/v1/analyses/ana_dot_test/export/dot")
    assert resp.status_code == 200
    assert "text/vnd.graphviz" in resp.headers["content-type"]
    assert (
        'filename="codestruct-ana_dot_test.dot"' in resp.headers["content-disposition"]
    )
    assert "digraph " in resp.text
    assert "pkg.App" in resp.text


def test_get_export_dot_when_graph_unavailable(app_client):
    app, client = app_client
    service = app.state.analysis_service

    # Job is still running (no graph)
    job = JobRecord(
        "ana_dot_running",
        "sample",
        str(SAMPLE),
        state=JobState.PARSING,
        percent=20,
        graph=None,
    )
    service.registry.add(job)

    resp = client.get("/api/v1/analyses/ana_dot_running/export/dot")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "GRAPH_UNAVAILABLE"
