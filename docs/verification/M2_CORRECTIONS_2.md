# Milestone 2 Corrections Report 2: Adapter Community Parity, Fallback Testing, Metric/Stub Semantics Documentation, and Extended Real Smoke

**Date:** 2026-10-03  
**Status:** Ready for Codex review  
**Scope:** Milestone 2 within CS-008–011 and CS-018–019 only.

---

## 1. Review 2 Findings Resolution Matrix

| # | Review Finding | Root Cause & Remediation | Verification Evidence |
|---|---|---|---|
| 1 | **Community output differs between adapters on small graphs (CS-009/010)** | `DefaultAlgorithmAdapter` stopped modularity merging when $\Delta Q \le 10^{-9}$, whereas NetworkX continues merging zero-gain pairs ($\Delta Q = 0$) until $\Delta Q < 0$. Updated `DefaultAlgorithmAdapter` stopping condition to `best_dq < -1e-12` and aligned tie-breaking and community ID sorting. | `docs/verification/M2_review2_parity_probe.py` output: `Default partition: [['0', '1', '2', '3']] == NetworkX partition: [['0', '1', '2', '3']]`. Verified across full small-graph parity corpus in `test_small_graph_community_parity_corpus`. |
| 2 | **Algorithm port fallback untested when NetworkX is absent (CS-009)** | Previous tests only ran with NetworkX installed. Added explicit mock-import test `test_algorithm_port_fallback_when_networkx_missing` verifying `get_algorithm_port()` auto-selection falls back to `DefaultAlgorithmAdapter`, `force_adapter="networkx"` raises `RuntimeError`, and graph metrics compute cleanly. | `tests/test_metrics_and_networkx.py::test_algorithm_port_fallback_when_networkx_missing` PASSED. |
| 3 | **Metric semantics and stub scope undocumented in product/architecture docs (CS-010/018)** | Metric formulas and stub precedence only existed in tests/code. Documented exact semantics in `docs/development/architecture.md` and `docs/api/v1.md`: eligible edges, duplicate/self-loop treatment, component vs community distinction, module membership ($E(M)$ excluding container), $C_a/C_e$ counting, cohesion/density formulas (including empty and single-entity containers), `.py`/`.pyi` precedence, stub-only support, and external stub boundaries. Reconciled `docs/verification/M2.md`. | `docs/development/architecture.md`, `docs/api/v1.md`, and `docs/verification/M2.md` updated. |
| 4 | **Evidence and real-smoke claims overstated; bounded prompt references missing (CS-008/010/011)** | Explanation prompt contained only aggregate evidence count. Updated `format_explanation_prompt` in `llm_summary.py` to format bounded safe evidence references (`[id] origin (observation_kind) at path:start_line-end_line`). Extended `docs/verification/M2_real_smoke.py` to assert `metadata.metrics_computed` across false/true/cache-hit results, module node metrics for `service.py`, exact source range (`service.py:3-7`), and static evidence observations in prompt. | `docs/verification/M2_real_smoke.py` completed cleanly with code 0. |
| 5 | **Process tracking and audit artifacts out of sync** | Appended Review 1 corrections and Review 2 resolutions to `PROCESS_TRACKER.md`. Updated both audit copies (`docs/codestruct_audit.md` and `docs/codestruct_audit_2026-09-23_original.md`) to reflect Ready for Codex review status upon completion of all verification gates. | `PROCESS_TRACKER.md` and audit documents updated. |

---

## 2. Verification Evidence

### 2.1 Codex Review 2 Parity Probe
```text
$ .venv/Scripts/python.exe docs/verification/M2_review2_parity_probe.py
Default partition: [['0', '1', '2', '3']]
NetworkX partition: [['0', '1', '2', '3']]
```

### 2.2 Codex Review Probe (Location & Filtering)
```text
$ .venv/Scripts/python.exe docs/verification/M2_codex_review_probe.py
Canonical location: {'source_unit_id': 'n_c3u7nvsx2lron45amshjryhb44', 'path': 'app.py', 'start_line': 1, 'start_column': 1, 'end_line': 2, 'end_column': 13}
Extracted path/line/end_line: app.py 1 2
Unresolved target counted fan_out/fan_in: 0 0
M2 Review Probe: All assertions passed successfully.
```

### 2.3 Extended Real Backend Smoke
```text
$ .venv/Scripts/python.exe docs/verification/M2_real_smoke.py
{
  "id_no_m": "ana_0bnbmVb38rtF_ugxmqubUAGY",
  "id_m": "ana_EvzpJP1ZMD5Z5tRK2597U37_",
  "node_count": 23,
  "edge_count": 30,
  "metadata_metrics_computed_false": false,
  "metadata_metrics_computed_true": true,
  "metadata_metrics_computed_warm_cache": true,
  "module_service_metrics": {
    "ca": "2",
    "ce": "1",
    "centrality": "0.045",
    "cohesion": "0.00",
    "community": "10",
    "component": "9",
    "fan_in": "0",
    "fan_out": "1",
    "has_docstring": "false",
    "in_cycle": "false",
    "instability": "1.00",
    "module_instability": "0.33",
    "parser_id": "mod_43903dc709b5d99d97e40b70",
    "relational_density": "1.00"
  },
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
  "sample_node_location": {
    "end_column": 30,
    "end_line": 7,
    "path": "service.py",
    "source_unit_id": "n_axvdxo4mktcnp37rbvtttu34m3",
    "start_column": 1,
    "start_line": 3
  },
  "explanation_with_metrics": {
    "api_version": "v1",
    "request_id": "req_g1QWyVcfZY3r",
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
    "prompt": "You are an expert Python software architect analyzing a codebase architecture graph.\nAnalyze the following code entity and provide a clear, concise architectural summary:\n\nEntity: Service (class)\nQualified Name: service.Service\nFile: service.py:3-7\n\nArchitecture Metrics:\n- community_id: 1\n- component_id: 1\n- degree_centrality: 0.091\n- fan_in: 2\n- fan_out: 0\n- in_cycle: False\n- instability: 0.0\n\nDependency Network:\n- Incoming Callers (0): None\n- Outgoing Callees (0): None\n- Importers (1): main\n- Imported Modules (0): None\n\nStatic Evidence Observations (3):\n- [v_of3spf2ngauy4bafhkyfpqjhow] source_ast (definition) at service.py:3-7\n- [v_rkctii2fwggcj26slnjjtc7rzx] source_ast (from_import_statement) at main.py:2\n- [v_zveyqvfuvguxvqxqxzmu2byb2i] static_resolution (from_import_statement_resolution) at main.py:2\n\nProvide an explanation covering: 1) Architectural Role, 2) Summary of Responsibilities, 3) Coupling & Stability Analysis, and 4) Architectural Recommendations or Risks.",
    "provider": "rule-based"
  },
  "explanation_without_metrics": {
    "api_version": "v1",
    "request_id": "req_42Kpy8KbpsAP",
    "node_id": "n_u7j5llw7652snsiserx7g7v256",
    "name": "Service",
    "kind": "class",
    "role": "Class Component",
    "summary": "`Service` is a class in `service.py:3-7` serving as a class component within the codebase.",
    "dependencies_summary": "Has no recorded internal callers. Imported by 1 module(s).",
    "metrics_summary": "Observed connections: 1 incoming, 0 outgoing (graph metrics not computed).",
    "recommendations": [
      "Healthy architectural posture: No immediate coupling or cycle risks detected."
    ],
    "prompt": "You are an expert Python software architect analyzing a codebase architecture graph.\nAnalyze the following code entity and provide a clear, concise architectural summary:\n\nEntity: Service (class)\nQualified Name: service.Service\nFile: service.py:3-7\n\nArchitecture Metrics:\n\nDependency Network:\n- Incoming Callers (0): None\n- Outgoing Callees (0): None\n- Importers (1): main\n- Imported Modules (0): None\n\nStatic Evidence Observations (3):\n- [v_of3spf2ngauy4bafhkyfpqjhow] source_ast (definition) at service.py:3-7\n- [v_rkctii2fwggcj26slnjjtc7rzx] source_ast (from_import_statement) at main.py:2\n- [v_zveyqvfuvguxvqxqxzmu2byb2i] static_resolution (from_import_statement_resolution) at main.py:2\n\nProvide an explanation covering: 1) Architectural Role, 2) Summary of Responsibilities, 3) Coupling & Stability Analysis, and 4) Architectural Recommendations or Risks.",
    "provider": "rule-based"
  },
  "cache_hit_verified": true
}
```

### 2.4 Focused Review Test Suite
```text
$ .venv/Scripts/python.exe -m pytest tests/test_resolver_correctness.py tests/test_type_stubs.py tests/test_metrics_and_networkx.py tests/test_options_and_cache.py tests/test_explanation_canonical.py tests/test_explain_route.py tests/test_cache_integration.py --no-cov -p no:cacheprovider -q
35 passed, 1 warning in 19.31s
```

---

## 3. Stopping Condition

Milestone 2 is marked **Ready for Codex review**. Milestone 3 (Lovable frontend redesign) and Milestone 4 (interactive traces/navigation) remain unstarted.
