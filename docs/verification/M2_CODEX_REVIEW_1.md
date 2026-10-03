# Milestone 2: Codex review 1

Date: 2026-10-02. Decision: **Changes required.** Do not begin M3 or M4.

## What passed

- Focused parser/stub/resolver/metrics/options/explanation/API selection: **19 passed**, one dependency deprecation warning.
- Submitted `M2_real_smoke.py` passes outside the sandbox and demonstrates distinct metrics false/true jobs, a metrics-true cache hit and rule-based explanations.
- The smoke itself exposes `File: service.py:?`, confirming canonical line loss described below.
- No source execution was observed in these checks.

The broader 174-test coverage run, plugin/frontend suites and lint/type results in `M2.md` are Antigravity-reported and were not independently repeated in this review.

## Blocking findings

1. **Canonical location still loses source lines (CS-011).** `graph_to_dict` serializes a flat location with `start_line` and `end_line`. `extract_node_context` only reads those values inside a nested `location.span`. The new unit test uses an invented nested location rather than real serializer output. `M2_codex_review_probe.py` produces a real canonical node at `app.py:1-2`, then extracts `app.py, None, None`. The submitted smoke prints `File: service.py:?`. Test `graph_to_dict(build_graph(...))` and the live explain route, including exact line and end line.
2. **Unresolved edges are counted as dependencies (CS-010/011).** Both metric adapters filter by relationship kind and target presence but never require `resolution_status == resolved`. The independent probe creates an unresolved call with a candidate target and gets fan-out/fan-in `1/1`. Filter metrics, cycles, module aggregation and explanation relationship lists to the explicitly defined eligible resolution/confidence policy. Add unresolved, ambiguous, syntactic-only, containment, duplicate and self-loop cases with exact expected values.
3. **Required architecture metrics and actual community detection are absent (CS-009/010).** The implementation provides per-node fan-in/out, instability, centrality and cycles. It does not implement module coupling, cohesion or density. `_detect_communities` and the NetworkX implementation are connected components, while output and explanations label them architectural communities. Separate a `component_id` from actual community assignment. Implement and document bounded deterministic community detection plus module-level coupling/cohesion/density with hand-checked fixtures. A connected graph with a weak bridge must prove community detection is not merely component detection.
4. **NetworkX dependency/fallback policy is undeclared (CS-009).** `pyproject.toml` does not declare NetworkX in runtime or optional dependencies. Current behavior depends on whatever happens to be installed in the environment. Declare the intended install policy and version range, document which adapter is active/fallback, and test both paths without leaking NetworkX objects into graph/API storage.
5. **Metrics option is not explicit in result metadata and handoff docs are stale (CS-008).** Cache fingerprints distinguish the flag and node attributes differ, but graph metadata does not state whether metrics were computed. `LOVABLE_FRONTEND_BRIEF.md` still says `metrics:true` is rejected until M2 and lists it under `OPTION_UNSUPPORTED`; other API architecture examples imply all custom options work. Add an explicit serialized option/metric-computed indicator, update schema version/fixtures if required, and reconcile the brief/API docs: metrics true is supported; custom grammar/patterns remain unsupported unless fully implemented. Test false, true and cache-hit metadata.
6. **The scoped static-correctness characterization is incomplete (CS-018/019).** The four new resolver tests cover nested calls, inheritance, a multi-dot case and `.py` over `.pyi`. They do not cover the requested alias forms, constructors, lexical shadowing/duplicate names, annotations, unsupported expressions, ambiguous/unresolved preservation, stub-only/external-stub boundary or evidence/location fidelity. Preserve stable issue meanings: CS-018 is stub/type scope; CS-019 is core resolver correctness. Add end-to-end expected graph tests and fix only demonstrated defects. Document unsupported cases rather than forcing false resolution.
7. **Explanation context does not carry evidence (CS-011).** `NodeContext` has no evidence field and the extractor ignores graph `evidence` and edge `evidence_ids`, despite the M2 exit requirement that path, line, evidence and metric values survive canonical extraction. Add bounded evidence references for the selected node's eligible relationships, preserve origin/location/excerpt identifiers, and test from a real serialized graph. Keep provider/RAG work in M6.

## Review probe

`docs/verification/M2_codex_review_probe.py` is static-only and creates a temporary file without importing or executing it. Current expected output demonstrates the two failures:

```text
Canonical location: ... start_line 1 ... end_line 2 ...
Extracted path/line/end_line: app.py None None
Unresolved target counted fan_out/fan_in: 1 1
```

Turn these into passing assertions after correction and retain the probe as review evidence.
