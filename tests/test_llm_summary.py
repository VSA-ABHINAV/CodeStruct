"""Tests for LLM/RAG semantic explanation layer.

Covers:
- Strict Pydantic model validation (extra field forbidding, type checking, required fields).
- Canonical evidence reference validation (valid IDs vs hallucinated IDs).
- Claim provenance labeling (LLM_INFERRED vs RULE_SYNTHESIZED).
- Explicit opt-in provider selection (rule-based vs llm vs auto).
- Injected Fake provider testing with zero remote/paid API calls.
- Deterministic offline fallback on provider timeout, failure, or schema invalidity.
- Bounded context prompt formatting with source snippets and canonical evidence items.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from codestruct.analysis.llm_summary import (
    FakeExplanationProvider,
    LLMExplanationPayload,
    OpenAICompatibleExplainer,
    RuleBasedExplainer,
    explain_node,
    extract_node_context,
    format_explanation_prompt,
    validate_evidence_references,
)
from codestruct.analysis.retrieval import SourceSnippet
from pydantic import ValidationError


@pytest.fixture
def sample_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "node-mod-app",
                "name": "app",
                "qualified_name": "sample_app.app",
                "kind": "module",
                "file_path": "sample_app/app.py",
                "line": 1,
                "end_line": 50,
                "attributes": [
                    {"key": "docstring", "value": "Main application orchestrator."},
                    {"key": "fan_in", "value": 0},
                    {"key": "fan_out", "value": 4},
                    {"key": "instability", "value": 1.0},
                    {"key": "community_id", "value": 1},
                    {"key": "in_cycle", "value": False},
                ],
                "evidence_ids": ["ev-app-mod-01"],
            },
            {
                "id": "node-fn-run",
                "name": "run",
                "qualified_name": "sample_app.app.run",
                "kind": "function",
                "file_path": "sample_app/app.py",
                "line": 10,
                "end_line": 25,
                "attributes": [
                    {"key": "docstring", "value": "Execute primary application loop."},
                    {"key": "fan_in", "value": 2},
                    {"key": "fan_out", "value": 1},
                    {"key": "instability", "value": 0.33},
                    {"key": "community_id", "value": 1},
                    {"key": "in_cycle", "value": False},
                    {"key": "runtime_calls", "value": 15},
                    {"key": "runtime_duration_ms", "value": 12.45},
                ],
                "evidence_ids": ["ev-run-decl-01"],
            },
            {
                "id": "node-fn-cycle-a",
                "name": "ping",
                "qualified_name": "sample_app.ping",
                "kind": "function",
                "file_path": "sample_app/ping.py",
                "line": 1,
                "end_line": 10,
                "attributes": [
                    {"key": "fan_in", "value": 1},
                    {"key": "fan_out", "value": 1},
                    {"key": "instability", "value": 0.5},
                    {"key": "community_id", "value": 2},
                    {"key": "in_cycle", "value": True},
                ],
                "evidence_ids": ["ev-ping-01"],
            },
        ],
        "edges": [
            {
                "id": "edge-1",
                "source_id": "node-mod-app",
                "target_id": "node-fn-run",
                "kind": "CALL",
                "resolution_status": "resolved",
                "evidence_ids": ["ev-call-app-run-01"],
            },
            {
                "id": "edge-2",
                "source_id": "node-fn-cycle-a",
                "target_id": "node-fn-cycle-a",
                "kind": "CALL",
                "resolution_status": "resolved",
                "evidence_ids": ["ev-cycle-call-01"],
            },
        ],
        "evidence": [
            {
                "id": "ev-run-decl-01",
                "origin": "STATIC_AST",
                "observation_kind": "function_definition",
                "location": {"path": "sample_app/app.py", "start_line": 10},
                "excerpt": "def run():",
            },
            {
                "id": "ev-call-app-run-01",
                "origin": "STATIC_AST",
                "observation_kind": "call_site",
                "location": {"path": "sample_app/app.py", "start_line": 35},
                "excerpt": "run()",
            },
        ],
    }


# ---------------------------------------------------------------------------
# 1. Strict Pydantic Output Validation Tests
# ---------------------------------------------------------------------------


def test_llm_payload_valid() -> None:
    data = {
        "role": "Core Utility",
        "summary": "Handles core arithmetic logic.",
        "dependencies_summary": "Invoked by payment processor.",
        "metrics_summary": "High stability (0.1).",
        "recommendations": ["Maintain unit test coverage."],
        "evidence_references": ["ev-1", "ev-2"],
        "claims": [
            {
                "statement": "Performs pure calculations.",
                "claim_type": "architectural_interpretation",
                "evidence_ids": ["ev-1"],
                "provenance": "LLM_INFERRED",
            }
        ],
    }
    payload = LLMExplanationPayload.model_validate(data)
    assert payload.role == "Core Utility"
    assert len(payload.claims) == 1
    assert payload.claims[0].provenance == "LLM_INFERRED"


def test_llm_payload_forbids_extra_fields() -> None:
    data = {
        "role": "Core Utility",
        "summary": "Summary text.",
        "dependencies_summary": "Dep text.",
        "metrics_summary": "Metric text.",
        "recommendations": [],
        "evidence_references": [],
        "claims": [],
        "unauthorized_extra_field": "injected_data",
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        LLMExplanationPayload.model_validate(data)


def test_llm_payload_rejects_missing_required_fields() -> None:
    # Missing summary
    data = {
        "role": "Core Utility",
        "dependencies_summary": "Dep text.",
        "metrics_summary": "Metric text.",
    }
    with pytest.raises(ValidationError, match="Field required"):
        LLMExplanationPayload.model_validate(data)


def test_llm_payload_rejects_invalid_types() -> None:
    data = {
        "role": 12345,  # int instead of str
        "summary": "Summary text.",
        "dependencies_summary": "Dep text.",
        "metrics_summary": "Metric text.",
        "recommendations": "not a list",
    }
    with pytest.raises(ValidationError):
        LLMExplanationPayload.model_validate(data)


# ---------------------------------------------------------------------------
# 2. Canonical Evidence Citation Validation Tests
# ---------------------------------------------------------------------------


def test_validate_evidence_references() -> None:
    canonical = {"ev-1", "ev-2", "ev-3"}

    # All valid
    is_valid, valid, invalid = validate_evidence_references(["ev-1", "ev-3"], canonical)
    assert is_valid is True
    assert valid == ["ev-1", "ev-3"]
    assert invalid == []

    # Hallucinated evidence ID
    is_valid, valid, invalid = validate_evidence_references(
        ["ev-1", "ev-hallucinated-99"], canonical
    )
    assert is_valid is False
    assert valid == ["ev-1"]
    assert invalid == ["ev-hallucinated-99"]


# ---------------------------------------------------------------------------
# 3. Context Extraction & Prompt Formatting Tests
# ---------------------------------------------------------------------------


def test_extract_node_context(sample_graph: dict[str, Any]) -> None:
    context = extract_node_context(sample_graph, "node-fn-run")
    assert context.node_id == "node-fn-run"
    assert context.name == "run"
    assert context.qualified_name == "sample_app.app.run"
    assert context.kind == "function"
    assert context.line == 10
    assert context.docstring == "Execute primary application loop."
    assert context.metrics["fan_in"] == 2
    assert context.metrics["fan_out"] == 1
    assert context.runtime_stats["runtime_calls"] == 15
    assert context.runtime_stats["runtime_duration_ms"] == 12.45
    assert "sample_app.app" in context.callers
    assert "ev-run-decl-01" in context.canonical_evidence_ids
    assert "ev-call-app-run-01" in context.canonical_evidence_ids


def test_extract_node_context_missing(sample_graph: dict[str, Any]) -> None:
    with pytest.raises(KeyError):
        extract_node_context(sample_graph, "nonexistent-id")


def test_format_explanation_prompt_with_source_and_evidence(
    sample_graph: dict[str, Any],
) -> None:
    context = extract_node_context(sample_graph, "node-fn-run")
    prompt = format_explanation_prompt(context)
    assert "run (function)" in prompt
    assert "sample_app/app.py:10" in prompt
    assert "fan_in: 2" in prompt
    assert "runtime_calls: 15" in prompt
    assert "Incoming Callers" in prompt
    assert "Canonical Evidence Observations" in prompt
    assert "ev-run-decl-01" in prompt
    assert "Do NOT hallucinate evidence IDs" in prompt


# ---------------------------------------------------------------------------
# 4. Deterministic Offline Rule-Based Explainer Tests
# ---------------------------------------------------------------------------


def test_rule_based_explainer_healthy(sample_graph: dict[str, Any]) -> None:
    context = extract_node_context(sample_graph, "node-fn-run")
    explanation = RuleBasedExplainer.explain(context)
    assert explanation.node_id == "node-fn-run"
    assert explanation.name == "run"
    assert "Execute primary application loop." in explanation.summary
    assert "Invoked by 1 caller(s)" in explanation.dependencies_summary
    assert "Instability index is 0.33" in explanation.metrics_summary
    assert "community cluster #1" in explanation.metrics_summary
    assert "15 execution(s)" in explanation.metrics_summary
    assert explanation.provider == "rule-based"
    assert explanation.fallback_used is False
    assert explanation.fallback_reason is None
    assert len(explanation.claims) >= 3
    # Provenance of rule-based claims is RULE_SYNTHESIZED
    for c in explanation.claims:
        assert c.provenance == "RULE_SYNTHESIZED"

    d = explanation.to_dict()
    assert d["role"] == "Function Component"
    assert len(d["recommendations"]) > 0
    assert d["fallback_used"] is False


def test_rule_based_explainer_cycle(sample_graph: dict[str, Any]) -> None:
    context = extract_node_context(sample_graph, "node-fn-cycle-a")
    explanation = RuleBasedExplainer.explain(context)
    assert explanation.role == "Cyclic Dependency Hotspot"
    assert any("Cycle Participation" in r for r in explanation.recommendations)


def test_rule_based_explainer_orchestrator(sample_graph: dict[str, Any]) -> None:
    context = extract_node_context(sample_graph, "node-mod-app")
    explanation = RuleBasedExplainer.explain(context)
    assert (
        "Architectural Subsystem" in explanation.role
        or "Entrypoint" in explanation.role
    )
    assert "highly flexible / unstable" in explanation.metrics_summary


# ---------------------------------------------------------------------------
# 5. Injected Fake Provider & Strict Validation Regressions
# ---------------------------------------------------------------------------


def test_explain_node_with_valid_fake_provider(sample_graph: dict[str, Any]) -> None:
    fake_payload = {
        "role": "Application Driver",
        "summary": "Drives the application loop and coordinates workflows.",
        "dependencies_summary": "Called by sample_app.app entrypoint.",
        "metrics_summary": "Moderate coupling with instability 0.33.",
        "recommendations": ["Add telemetry for long-running executions."],
        "evidence_references": ["ev-run-decl-01", "ev-call-app-run-01"],
        "claims": [
            {
                "statement": "Drives core loops.",
                "claim_type": "architectural_interpretation",
                "evidence_ids": ["ev-run-decl-01"],
                "provenance": "LLM_INFERRED",
            }
        ],
    }
    fake_provider = FakeExplanationProvider(payload=fake_payload, name="test-mock-llm")

    explanation = explain_node(
        sample_graph,
        "node-fn-run",
        provider="llm",
        custom_provider=fake_provider,
    )

    assert explanation.node_id == "node-fn-run"
    assert explanation.provider == "test-mock-llm"
    assert explanation.fallback_used is False
    assert explanation.fallback_reason is None
    assert explanation.role == "Application Driver"
    assert "Drives the application loop" in explanation.summary
    assert explanation.cited_evidence_ids == ["ev-run-decl-01", "ev-call-app-run-01"]

    # All claims strictly labeled LLM_INFERRED
    assert len(explanation.claims) >= 1
    for c in explanation.claims:
        assert c.provenance == "LLM_INFERRED"


def test_explain_node_hallucinated_evidence_triggers_fallback(
    sample_graph: dict[str, Any],
) -> None:
    hallucinated_payload = {
        "role": "Application Driver",
        "summary": "Summary text.",
        "dependencies_summary": "Dep text.",
        "metrics_summary": "Metric text.",
        "recommendations": [],
        "evidence_references": ["ev-run-decl-01", "ev-hallucinated-fake-999"],
        "claims": [],
    }
    fake_provider = FakeExplanationProvider(
        payload=hallucinated_payload, name="hallucinating-llm"
    )

    explanation = explain_node(
        sample_graph,
        "node-fn-run",
        provider="llm",
        custom_provider=fake_provider,
    )

    # Must cleanly fall back to rule-based!
    assert explanation.fallback_used is True
    assert "invalid or unknown evidence IDs" in str(explanation.fallback_reason)
    assert "ev-hallucinated-fake-999" in str(explanation.fallback_reason)
    assert "rule-based" in explanation.provider


def test_explain_node_provider_timeout_triggers_fallback(
    sample_graph: dict[str, Any],
) -> None:
    timeout_provider = FakeExplanationProvider(
        error=TimeoutError("Request timed out after 6.0s")
    )

    explanation = explain_node(
        sample_graph,
        "node-fn-run",
        provider="llm",
        custom_provider=timeout_provider,
    )

    assert explanation.fallback_used is True
    assert "TimeoutError" in str(explanation.fallback_reason)
    assert "rule-based" in explanation.provider


def test_explain_node_provider_malformed_schema_triggers_fallback(
    sample_graph: dict[str, Any],
) -> None:
    # Payload missing required 'summary' field and having extra field
    malformed_payload = {
        "role": "Broken",
        "extra_bad_field": 123,
    }
    broken_provider = FakeExplanationProvider(payload=malformed_payload)

    explanation = explain_node(
        sample_graph,
        "node-fn-run",
        provider="llm",
        custom_provider=broken_provider,
    )

    assert explanation.fallback_used is True
    assert "validation error" in str(explanation.fallback_reason).lower()
    assert "rule-based" in explanation.provider


# ---------------------------------------------------------------------------
# 6. Opt-In Behavior Tests
# ---------------------------------------------------------------------------


def test_explain_node_explicit_rule_based_ignores_custom_provider(
    sample_graph: dict[str, Any],
) -> None:
    fake_provider = FakeExplanationProvider(
        payload={
            "role": "ShouldNotBeCalled",
            "summary": "",
            "dependencies_summary": "",
            "metrics_summary": "",
        }
    )
    # When provider='rule-based', never invokes custom_provider
    explanation = explain_node(
        sample_graph,
        "node-fn-run",
        provider="rule-based",
        custom_provider=fake_provider,
    )
    assert explanation.provider == "rule-based"
    assert explanation.fallback_used is False
    assert len(fake_provider.calls) == 0


def test_explain_node_llm_without_config_falls_back(
    sample_graph: dict[str, Any], monkeypatch
) -> None:
    monkeypatch.delenv("CODESTRUCT_LLM_API_BASE", raising=False)
    explanation = explain_node(sample_graph, "node-fn-run", provider="llm")
    assert explanation.fallback_used is True
    assert "CODESTRUCT_LLM_API_BASE unset" in str(explanation.fallback_reason)
    assert "rule-based" in explanation.provider


def test_explain_node_auto_without_config_defaults_cleanly(
    sample_graph: dict[str, Any], monkeypatch
) -> None:
    monkeypatch.delenv("CODESTRUCT_LLM_API_BASE", raising=False)
    explanation = explain_node(sample_graph, "node-fn-run", provider="auto")
    assert explanation.fallback_used is False
    assert explanation.provider == "rule-based"


# ---------------------------------------------------------------------------
# 7. OpenAICompatibleExplainer Fallback Tests
# ---------------------------------------------------------------------------


def test_openai_explainer_invalid_url(sample_graph: dict[str, Any]) -> None:
    context = extract_node_context(sample_graph, "node-fn-run")
    explainer = OpenAICompatibleExplainer(api_base="ftp://invalid.host")
    explanation = explainer.explain(context, "prompt")
    assert explanation.fallback_used is True
    assert "Invalid API base URL" in str(explanation.fallback_reason)
    assert "rule-based" in explanation.provider


def test_openai_explainer_connection_refused(sample_graph: dict[str, Any]) -> None:
    context = extract_node_context(sample_graph, "node-fn-run")
    explainer = OpenAICompatibleExplainer(
        api_base="http://127.0.0.1:59999", timeout=0.1
    )
    explanation = explainer.explain(context, "prompt")
    assert explanation.fallback_used is True
    assert "LLM provider failed" in str(explanation.fallback_reason)
    assert "rule-based" in explanation.provider


def test_openai_explainer_successful_http_response(
    sample_graph: dict[str, Any], monkeypatch
) -> None:
    from unittest.mock import MagicMock

    fake_resp_data = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "role": "Orchestrator",
                            "summary": "Coordinates workflows via HTTP API.",
                            "dependencies_summary": "Calls internal services.",
                            "metrics_summary": "Stable coupling.",
                            "recommendations": ["Add monitoring."],
                            "evidence_references": ["ev-run-decl-01"],
                            "claims": [
                                {
                                    "statement": "Coordinates workflows.",
                                    "claim_type": "architectural_interpretation",
                                    "evidence_ids": ["ev-run-decl-01"],
                                    "provenance": "LLM_INFERRED",
                                }
                            ],
                        }
                    )
                }
            }
        ]
    }
    raw_bytes = json.dumps(fake_resp_data).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = raw_bytes
    mock_resp.__enter__.return_value = mock_resp

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: mock_resp)

    context = extract_node_context(sample_graph, "node-fn-run")
    explainer = OpenAICompatibleExplainer(
        api_base="http://mock-llm.local",
        api_key="sk-testkey",
        model="gpt-mock",
    )
    explanation = explainer.explain(context, "test prompt")
    assert explanation.fallback_used is False
    assert explanation.provider == "llm:gpt-mock"
    assert explanation.role == "Orchestrator"
    assert len(explanation.claims) == 1
    assert explanation.claims[0].provenance == "LLM_INFERRED"


def test_openai_explainer_http_non_200_fallback(
    sample_graph: dict[str, Any], monkeypatch
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.reason = "Internal Server Error"
    mock_resp.__enter__.return_value = mock_resp

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: mock_resp)

    context = extract_node_context(sample_graph, "node-fn-run")
    explainer = OpenAICompatibleExplainer(api_base="http://mock-llm.local")
    explanation = explainer.explain(context, "test prompt")
    assert explanation.fallback_used is True
    assert "HTTP 500" in str(explanation.fallback_reason)


def test_rule_based_roles_and_recommendations(sample_graph: dict[str, Any]) -> None:
    # 1. Abstract base class role
    base_graph = {
        "nodes": [
            {
                "id": "node-base-cls",
                "name": "BaseHandler",
                "kind": "class",
                "attributes": [
                    {"key": "fan_in", "value": 2},
                    {"key": "fan_out", "value": 1},
                    {"key": "instability", "value": 0.1},
                    {"key": "ca", "value": 4},
                    {"key": "ce", "value": 2},
                    {"key": "cohesion", "value": 0.8},
                ],
            },
            {
                "id": "node-sub-cls",
                "name": "SubHandler",
                "kind": "class",
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source_id": "node-sub-cls",
                "target_id": "node-base-cls",
                "kind": "INHERITS",
                "resolution_status": "resolved",
            }
        ],
    }
    context = extract_node_context(base_graph, "node-base-cls")
    explanation = RuleBasedExplainer.explain(context)
    assert explanation.role == "Abstract Base / Extension Point"
    assert any("Stable Abstraction Principle" in r for r in explanation.recommendations)
    assert (
        "Module Architecture: Ca=4, Ce=2, Cohesion: 0.80" in explanation.metrics_summary
    )


def test_rule_based_high_coupling_recommendations() -> None:
    coupled_graph = {
        "nodes": [
            {
                "id": "node-coupled",
                "name": "HeavyHub",
                "kind": "class",
                "attributes": [
                    {"key": "fan_in", "value": 12},
                    {"key": "fan_out", "value": 15},
                ],
            }
        ],
        "edges": [],
    }
    context = extract_node_context(coupled_graph, "node-coupled")
    explanation = RuleBasedExplainer.explain(context)
    assert any("High Fan-In" in r for r in explanation.recommendations)
    assert any("High Fan-Out" in r for r in explanation.recommendations)


def test_format_explanation_prompt_with_truncated_snippet() -> None:
    snippet = SourceSnippet(
        file_path="service.py",
        start_line=1,
        end_line=50,
        content="def run(): pass\n",
        byte_count=16,
        line_count=1,
        is_truncated=True,
    )
    from codestruct.analysis.retrieval import RetrievedEvidenceContext

    ctx = RetrievedEvidenceContext(
        node_id="n1",
        name="run",
        qualified_name="pkg.run",
        kind="function",
        source_snippet=snippet,
        docstring="Doc string.",
        inherits=["BaseClass"],
        inherited_by=["SubClass"],
    )
    prompt = format_explanation_prompt(ctx)
    assert "Bounded Source Code Snippet" in prompt
    assert "Source snippet was bounded by size limit." in prompt
    assert "Docstring: Doc string." in prompt
    assert "Inherits From: BaseClass" in prompt
    assert "Inherited By: SubClass" in prompt
