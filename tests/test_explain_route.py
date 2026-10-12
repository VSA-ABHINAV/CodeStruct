"""Tests for node explanation HTTP route.

Covers:
- Standard rule-based explanation with truthful M6 metadata and claims.
- 404 for nonexistent node and 409 for pending/unbuilt graph.
- Opt-in LLM explanation with injected fake provider (valid payload, claims with LLM_INFERRED).
- Fallback on provider failure and on hallucinated evidence IDs.
- Path containment and secret protection via API endpoint.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from codestruct.analysis.llm_summary import FakeExplanationProvider
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
                "evidence_ids": ["ev_calc_decl_01"],
            }
        ],
        "edges": [],
        "evidence": [
            {
                "id": "ev_calc_decl_01",
                "origin": "STATIC_AST",
                "observation_kind": "function_definition",
            }
        ],
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
    assert data["fallback_used"] is False
    assert data["fallback_reason"] is None
    assert "ev_calc_decl_01" in data["retrieved_evidence_ids"]
    assert len(data["claims"]) >= 3
    # Check claim provenance
    assert all(c["provenance"] == "RULE_SYNTHESIZED" for c in data["claims"])


def test_explain_node_with_injected_llm_provider(app_client):
    client, service = app_client

    graph_dict = {
        "metadata": {"analysis_id": "job_exp_injected"},
        "nodes": [
            {
                "id": "node-target-2",
                "name": "process_payment",
                "kind": "function",
                "qualified_name": "billing.process_payment",
                "file_path": "billing/payment.py",
                "line": 15,
                "attributes": [
                    {"key": "fan_in", "value": 2},
                    {"key": "fan_out", "value": 3},
                ],
                "evidence_ids": ["ev_pay_01"],
            }
        ],
        "edges": [],
        "evidence": [{"id": "ev_pay_01", "origin": "STATIC_AST"}],
    }

    record = JobRecord(
        "job_exp_injected",
        "sample",
        str(SAMPLE),
        state=JobState.COMPLETED,
        graph=graph_dict,
        percent=100,
    )
    service.registry.add(record)

    fake_payload = {
        "role": "Transaction Processor",
        "summary": "Executes card transaction processing.",
        "dependencies_summary": "Coordinates gateway calls.",
        "metrics_summary": "Moderate coupling.",
        "recommendations": ["Enforce transaction idempotency."],
        "evidence_references": ["ev_pay_01"],
        "claims": [
            {
                "statement": "Coordinates payment gateway transactions.",
                "claim_type": "architectural_interpretation",
                "evidence_ids": ["ev_pay_01"],
                "provenance": "LLM_INFERRED",
            }
        ],
    }
    service.custom_explanation_provider = FakeExplanationProvider(
        payload=fake_payload,
        name="test-fake-provider",
    )

    resp = client.get(
        "/api/v1/analyses/job_exp_injected/nodes/node-target-2/explain?provider=llm"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "test-fake-provider"
    assert data["fallback_used"] is False
    assert data["role"] == "Transaction Processor"
    assert data["cited_evidence_ids"] == ["ev_pay_01"]
    assert len(data["claims"]) == 1
    assert data["claims"][0]["provenance"] == "LLM_INFERRED"


def test_explain_node_injected_provider_fallback_on_failure(app_client):
    client, service = app_client

    graph_dict = {
        "metadata": {"analysis_id": "job_exp_fail"},
        "nodes": [
            {
                "id": "node-target-3",
                "name": "notify",
                "kind": "function",
                "qualified_name": "billing.notify",
                "file_path": "billing/notify.py",
                "line": 1,
                "attributes": [],
            }
        ],
        "edges": [],
    }

    record = JobRecord(
        "job_exp_fail",
        "sample",
        str(SAMPLE),
        state=JobState.COMPLETED,
        graph=graph_dict,
        percent=100,
    )
    service.registry.add(record)

    service.custom_explanation_provider = FakeExplanationProvider(
        error=RuntimeError("Simulated LLM gateway 503 error"),
    )

    resp = client.get(
        "/api/v1/analyses/job_exp_fail/nodes/node-target-3/explain?provider=llm"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fallback_used"] is True
    assert "503 error" in str(data["fallback_reason"])
    assert "rule-based" in data["provider"]


def test_explain_node_injected_provider_hallucination_triggers_fallback(app_client):
    client, service = app_client

    graph_dict = {
        "metadata": {"analysis_id": "job_exp_halluc"},
        "nodes": [
            {
                "id": "node-target-4",
                "name": "log_event",
                "kind": "function",
                "qualified_name": "billing.log_event",
                "file_path": "billing/log.py",
                "line": 1,
                "attributes": [],
                "evidence_ids": ["ev_valid_01"],
            }
        ],
        "edges": [],
        "evidence": [{"id": "ev_valid_01", "origin": "STATIC_AST"}],
    }

    record = JobRecord(
        "job_exp_halluc",
        "sample",
        str(SAMPLE),
        state=JobState.COMPLETED,
        graph=graph_dict,
        percent=100,
    )
    service.registry.add(record)

    hallucinating_payload = {
        "role": "Logger",
        "summary": "Logs events.",
        "dependencies_summary": "None.",
        "metrics_summary": "Leaf.",
        "recommendations": [],
        "evidence_references": ["ev_valid_01", "ev_fake_hallucinated_id_404"],
        "claims": [],
    }
    service.custom_explanation_provider = FakeExplanationProvider(
        payload=hallucinating_payload
    )

    resp = client.get(
        "/api/v1/analyses/job_exp_halluc/nodes/node-target-4/explain?provider=llm"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fallback_used"] is True
    assert "ev_fake_hallucinated_id_404" in str(data["fallback_reason"])
    assert "rule-based" in data["provider"]


def test_explain_node_safeguards_sensitive_and_traversal_paths(app_client):
    client, service = app_client
    service.custom_explanation_provider = None

    # Node pointing to secret file .env and node pointing to traversal path
    graph_dict = {
        "metadata": {"analysis_id": "job_exp_security"},
        "nodes": [
            {
                "id": "node-secret",
                "name": "secret_config",
                "kind": "variable",
                "file_path": ".env",
                "line": 1,
                "attributes": [],
            },
            {
                "id": "node-traversal",
                "name": "escaped_fn",
                "kind": "function",
                "file_path": "../../etc/passwd",
                "line": 1,
                "attributes": [],
            },
        ],
        "edges": [],
    }

    record = JobRecord(
        "job_exp_security",
        "sample",
        str(SAMPLE),
        state=JobState.COMPLETED,
        graph=graph_dict,
        percent=100,
    )
    service.registry.add(record)

    # 1. Secret file node: safe explanation generated without reading secret
    resp_secret = client.get(
        "/api/v1/analyses/job_exp_security/nodes/node-secret/explain"
    )
    assert resp_secret.status_code == 200
    assert resp_secret.json()["node_id"] == "node-secret"

    # 2. Traversal path node: safe explanation generated without reading outside file
    resp_trav = client.get(
        "/api/v1/analyses/job_exp_security/nodes/node-traversal/explain"
    )
    assert resp_trav.status_code == 200
    assert resp_trav.json()["node_id"] == "node-traversal"


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
