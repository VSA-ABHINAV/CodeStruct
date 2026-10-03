"""Tests for node explanation HTTP route."""

from __future__ import annotations

from pathlib import Path

import pytest
from codestruct.api.app import create_app
from codestruct.jobs.models import JobRecord, JobState
from codestruct.settings import Settings
from fastapi.testclient import TestClient

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"


@pytest.fixture(scope="module")
def app_client():
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, app.state.analysis_service
    if hasattr(app.state, "analysis_service"):
        app.state.analysis_service.shutdown()


def test_explain_node_success(app_client):
    client, service = app_client

    graph_dict = {
        "metadata": {"analysis_id": "job_exp_1"},
        "nodes": [
            {
                "id": "node-target-1",
                "name": "calc_total",
                "kind": "function",
                "qualified_name": "billing.calc_total",
                "file_path": "billing/calc.py",
                "line": 42,
                "attributes": [
                    {"key": "fan_in", "value": 3},
                    {"key": "fan_out", "value": 1},
                    {"key": "instability", "value": 0.25},
                    {"key": "docstring", "value": "Compute order subtotal."},
                ],
            }
        ],
        "edges": [],
    }

    record = JobRecord(
        "job_exp_1",
        "sample",
        str(SAMPLE),
        state=JobState.COMPLETED,
        graph=graph_dict,
        percent=100,
    )
    service.registry.add(record)

    resp = client.get("/api/v1/analyses/job_exp_1/nodes/node-target-1/explain")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_id"] == "node-target-1"
    assert data["name"] == "calc_total"
    assert data["kind"] == "function"
    assert "Compute order subtotal" in data["summary"]
    assert "Instability index is 0.25" in data["metrics_summary"]
    assert data["provider"] == "rule-based"


def test_explain_node_not_found(app_client):
    client, service = app_client

    record = JobRecord(
        "job_exp_2",
        "sample",
        str(SAMPLE),
        state=JobState.COMPLETED,
        graph={"nodes": [], "edges": []},
        percent=100,
    )
    service.registry.add(record)

    resp = client.get("/api/v1/analyses/job_exp_2/nodes/nonexistent-node/explain")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "NODE_NOT_FOUND"


def test_explain_node_no_graph(app_client):
    client, service = app_client

    record = JobRecord(
        "job_exp_pending",
        "sample",
        str(SAMPLE),
        state=JobState.SCANNING,
        graph=None,
        percent=50,
    )
    service.registry.add(record)

    resp = client.get("/api/v1/analyses/job_exp_pending/nodes/any-node/explain")
    assert resp.status_code == 409
    data = resp.json()
    assert data["error"]["code"] == "GRAPH_UNAVAILABLE"
