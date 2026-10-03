# Milestone 2 Corrections Report (Review 1 Response)

**Date:** 2026-10-02  
**Status:** Ready for Codex review  
**Scope:** Milestone 2 within CS-008–011 and CS-018–019 only.

---

## 1. Matrix of Review Findings and Corrections

| # | Finding (M2 Review 1) | Affected Scope | Root Cause & Resolution | Verification Evidence |
|---|---|---|---|---|
| **1** | **Canonical location loses source lines (CS-011)** | `backend/src/codestruct/analysis/llm_summary.py` | `graph_to_dict` serializes flat `{path, start_line, start_column, end_line, end_column}`. `extract_node_context` was previously looking inside nested `location.span.start.line`. Updated `extract_node_context` to read flat `start_line` and `end_line` directly, preserving exact source line ranges in `NodeContext` and prompts/explanations. | `M2_codex_review_probe.py` asserts exact `context.line == 1` and `context.end_line == 2`. `tests/test_explanation_canonical.py` verifies real serialized output and live explain route without `service.py:?`. |
| **2** | **Unresolved edges counted as dependencies (CS-010/011)** | `backend/src/codestruct/graph/metrics.py`<br>`backend/src/codestruct/analysis/llm_summary.py` | Metrics adapters and explanation extractors previously filtered only by relationship kind without requiring `ResolutionStatus.RESOLVED`. Updated both adapters and `extract_node_context` to strictly enforce `ResolutionStatus.RESOLVED` (and `edge["resolution_status"] == "resolved"`) and `src != tgt`, excluding `UNRESOLVED`, `AMBIGUOUS`, `SYNTACTIC_ONLY`, containment, and self-loops from fan-in/fan-out coupling and centrality. | `M2_codex_review_probe.py` asserts `fan_out == 0, fan_in == 0` for unresolved edge. `tests/test_metrics_and_networkx.py::test_resolved_edge_filtering_and_unresolved_exclusion` verifies exact 0 counts for unresolved/ambiguous/syntactic-only/containment edges. |
| **3** | **Required architecture metrics and community detection absent (CS-009/010)** | `backend/src/codestruct/graph/metrics.py`<br>`backend/src/codestruct/graph/model.py` | Connected components were conflated with communities, and module-level metrics were missing. Separated `component_id` (connected components) from `community_id` (deterministic greedy modularity community clustering). Implemented module architecture metrics: afferent coupling ($C_a$), efferent coupling ($C_e$), instability ($I = C_e / (C_a + C_e)$), internal cohesion, and relational density in both NetworkX and pure-Python Default adapters. | `tests/test_metrics_and_networkx.py::test_weak_bridge_community_vs_component_separation` proves a connected graph with a weak bridge splits into 2 communities within 1 component on both adapters. `test_module_architecture_metrics` verifies exact $C_a, C_e, I$, cohesion, and relational density. |
| **4** | **NetworkX dependency/fallback policy undeclared (CS-009)** | `pyproject.toml`<br>`backend/src/codestruct/graph/metrics.py` | Undeclared optional dependency. Added `networkx>=3.0,<4.0` under `[project.optional-dependencies] metrics` and `dev`. Documented primary adapter (`NetworkXAlgorithmAdapter`), fallback adapter (`DefaultAlgorithmAdapter`), port factory `get_algorithm_port(force_adapter=...)`, and verified zero object leakage across graph, cache, and API boundaries. | `tests/test_metrics_and_networkx.py::test_enrich_nodes_with_metrics_port_fallback` tests both `"default"`, `"networkx"`, and auto-fallback paths with matching metric results. |
| **5** | **Metrics option not explicit in result metadata & docs stale (CS-008)** | `backend/src/codestruct/graph/model.py`<br>`backend/src/codestruct/graph/serialization.py`<br>`backend/src/codestruct/graph/builder.py`<br>`LOVABLE_FRONTEND_BRIEF.md` | Added explicit `metrics_computed: bool` to `GraphMetadata`, `graph_to_dict`, and `graph_from_dict`. Reconciled `LOVABLE_FRONTEND_BRIEF.md` to state that `options.metrics: true/false` is supported in API v1, while custom grammar and pattern inclusion/exclusion filters remain reserved and return HTTP 400 `OPTION_UNSUPPORTED`. | `tests/test_cache_integration.py::test_metrics_option_metadata_and_cache` tests false, true, and warm cache-hit metadata persistence. |
| **6** | **Static-correctness characterization incomplete (CS-018/019)** | `tests/test_resolver_correctness.py`<br>`tests/test_type_stubs.py` | Added comprehensive characterization tests for: import aliases (`import math as m`, `from pkg import fn as my_fn`), class constructors/instantiations (`srv = Service()`), lexical shadowing with duplicate local names, type annotations without false calls, unsupported dynamic expressions preserving `UNRESOLVED`/`SYNTACTIC_ONLY` status, stub-only modules (`.pyi` without `.py`), external stub boundaries, and evidence location fidelity. | `tests/test_resolver_correctness.py` (10 tests) and `tests/test_type_stubs.py` (6 tests) all passing with 100% assertions satisfied. |
| **7** | **Explanation context does not carry evidence (CS-011)** | `backend/src/codestruct/analysis/llm_summary.py` | Added `evidence: list[dict[str, Any]]` field to `NodeContext`. `extract_node_context` now indexes graph evidence records, identifies incident resolved dependency edges and defining containment edges, and preserves bounded evidence records (origin, observation kind, location, expression, explanation, text hash) in `NodeContext` and explanation prompts. | `M2_codex_review_probe.py` and `tests/test_explanation_canonical.py` assert `len(context.evidence) > 0` and verify evidence references are attached to extracted contexts. |

---

## 2. Review Probe Verification Evidence

`docs/verification/M2_codex_review_probe.py` output:
```text
Canonical location: {'source_unit_id': 'n_c3u7nvsx2lron45amshjryhb44', 'path': 'app.py', 'start_line': 1, 'start_column': 1, 'end_line': 2, 'end_column': 13}
Extracted path/line/end_line: app.py 1 2
Unresolved target counted fan_out/fan_in: 0 0
M2 Review Probe: All assertions passed successfully.
```

---

## 3. Real Smoke Test Verification Evidence

`docs/verification/M2_real_smoke.py` execution output:
```json
{
  "id_no_m": "ana_7ndSG1swr-2OpVpvirHTxiPe",
  "id_m": "ana_Fn6UqpB2k8uxuvxadRSNxuGM",
  "node_count": 23,
  "edge_count": 30,
  "sample_node_no_metrics_attrs": {
    "has_docstring": "false",
    "parser_id": "cls_ae08508c21b3b5295f151f3b"
  },
  "sample_node_metrics_attrs": {
    "centrality": "0.091",
    "community": "1",
    "component": "1",
    "fan_in": "2",
    "fan_out": "0",
    "has_docstring": "false",
    "in_cycle": "false",
    "instability": "0.00",
    "parser_id": "cls_ae08508c21b3b5295f151f3b"
  },
  "explanation_with_metrics": {
    "api_version": "v1",
    "request_id": "req_xs3wlvV4UWMv",
    "node_id": "n_u7j5llw7652snsiserx7g7v256",
    "name": "Service",
    "kind": "class",
    "role": "Class Component",
    "summary": "`Service` is a class in `service.py:3-7` serving as a class component within the codebase.",
    "dependencies_summary": "Has no recorded internal callers. Imported by 1 module(s).",
    "metrics_summary": "Fan-in: 2, Fan-out: 0. Instability index is 0.00, indicating highly stable (resilient to changes, heavily relied upon). Component: #1. Assigned to architectural community cluster #1.",
    "recommendations": [
      "Healthy architectural posture: No immediate coupling or cycle risks detected."
    ],
    "prompt": "You are an expert Python software architect analyzing a codebase architecture graph.\nAnalyze the following code entity and provide a clear, concise architectural summary:\n\nEntity: Service (class)\nQualified Name: service.Service\nFile: service.py:3-7\n\nArchitecture Metrics:\n- community_id: 1\n- component_id: 1\n- degree_centrality: 0.091\n- fan_in: 2\n- fan_out: 0\n- in_cycle: False\n- instability: 0.0\n\nDependency Network:\n- Incoming Callers (0): None\n- Outgoing Callees (0): None\n- Importers (1): main\n- Imported Modules (0): None\n\nStatic Evidence Observations: 3 verified static syntax references.\n\nProvide an explanation covering: 1) Architectural Role, 2) Summary of Responsibilities, 3) Coupling & Stability Analysis, and 4) Architectural Recommendations or Risks.",
    "provider": "rule-based"
  },
  "cache_hit_verified": true
}
```

---

## 4. Verification Gates Summary

1. **Pytest Suite:** `187 passed, 1 skipped` in 22.02s. Total statement coverage: **85.48%** (exceeds 84% gate).
2. **Ruff Lint:** `ruff check .` -> `All checks passed!`.
3. **Ruff Format:** `ruff format --check .` -> `188 files already formatted`.
4. **Mypy Type Checking:** `mypy` -> `Success: no issues found in 50 source files`.
5. **No Source Execution:** Confirmed 100% static analysis; zero target source code imported or executed.
