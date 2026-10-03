"""Tests for LLM/RAG semantic explanation layer."""

from __future__ import annotations

from typing import Any

import pytest
from codestruct.analysis.llm_summary import (
    OpenAICompatibleExplainer,
    RuleBasedExplainer,
    explain_node,
    extract_node_context,
    format_explanation_prompt,
)


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
            },
        ],
        "edges": [
            {
                "id": "edge-1",
                "source_id": "node-mod-app",
                "target_id": "node-fn-run",
                "kind": "CALL",
            },
            {
                "id": "edge-2",
                "source_id": "node-fn-cycle-a",
                "target_id": "node-fn-cycle-a",
                "kind": "CALL",
            },
        ],
    }


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


def test_extract_node_context_missing(sample_graph: dict[str, Any]) -> None:
    with pytest.raises(KeyError):
        extract_node_context(sample_graph, "nonexistent-id")


def test_format_explanation_prompt(sample_graph: dict[str, Any]) -> None:
    context = extract_node_context(sample_graph, "node-fn-run")
    prompt = format_explanation_prompt(context)
    assert "run (function)" in prompt
    assert "sample_app/app.py:10" in prompt
    assert "fan_in: 2" in prompt
    assert "runtime_calls: 15" in prompt
    assert "Incoming Callers" in prompt


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
    d = explanation.to_dict()
    assert d["role"] == "Function Component"
    assert len(d["recommendations"]) > 0


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


def test_explain_node_auto_fallback(sample_graph: dict[str, Any]) -> None:
    explanation = explain_node(sample_graph, "node-fn-run", provider="auto")
    assert explanation.node_id == "node-fn-run"
    assert explanation.name == "run"
    assert explanation.provider == "rule-based"


def test_openai_explainer_fallback_on_invalid_endpoint(
    sample_graph: dict[str, Any],
) -> None:
    context = extract_node_context(sample_graph, "node-fn-run")
    explainer = OpenAICompatibleExplainer(
        api_base="http://127.0.0.1:99999", timeout=0.1
    )
    explanation = explainer.explain(context, "dummy prompt")
    assert explanation.node_id == "node-fn-run"
    assert "llm-fallback" in explanation.provider
