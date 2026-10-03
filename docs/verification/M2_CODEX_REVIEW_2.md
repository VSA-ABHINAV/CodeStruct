# Milestone 2 Codex Review 2

**Date:** 2026-10-03  
**Decision:** Changes required  
**Scope reviewed:** CS-008–011 and CS-018–019 only.

The correction pass fixes the original canonical-location and unresolved-edge failures. A fresh focused suite passed with **33 tests**, `M2_codex_review_probe.py` passed, and the real backend smoke completed with distinct metrics-off/metrics-on analyses plus a warm cache hit. Milestone 2 is not Accepted because adapter behavior, documentation, and required process evidence remain inconsistent.

## Blocking findings

1. **Community output changes with the installed adapter (CS-009/010).** `docs/verification/M2_review2_parity_probe.py` uses a connected four-node triangle-with-leaf graph. The pure-Python adapter returns communities `{0,3}` and `{1,2}` while NetworkX returns `{0,1,2,3}`. This contradicts the reported 100% adapter parity and makes cached/API results environment-dependent. Define one canonical deterministic community policy, including zero-gain/tie behavior, and make both adapters expose the same partition. Add this regression plus a bounded small-graph parity corpus. Keep NetworkX transient and retain genuine NetworkX-backed work behind the port.

2. **The fallback path is not tested (CS-009).** `test_enrich_nodes_with_metrics_port_fallback` instantiates default, NetworkX, and auto selection while NetworkX is installed. It never makes the import unavailable, so it does not prove automatic fallback. Add a deterministic missing-NetworkX test and define forced-`networkx` behavior when the extra is absent.

3. **Metric semantics and stub scope are not documented in maintained product/architecture docs (CS-010/018).** The formulas exist only in implementation comments/tests and the correction report. Document eligible edge kinds/status/confidence, duplicate and self-loop treatment, normalization, component/community distinction, module membership, Ca/Ce counting units, cohesion/density formulas, empty/single-member behavior, algorithm bounds, optional-extra installation, and adapter selection. The current module test counts the module container itself as a member, which dilutes cohesion and makes an isolated container report perfect cohesion; either correct that denominator to contained program entities or explicitly justify and name the chosen semantics. Document `.py`/`.pyi` precedence, stub-only support, and the external-stub boundary. Reconcile the stale connected-component/100%-parity statements in `docs/verification/M2.md`.

4. **Evidence and real-smoke claims overstate what is shown (CS-008/010/011).** `NodeContext` now carries canonical evidence, but the explanation prompt includes only an evidence count, not the reported bounded ID/origin/location references. Include bounded safe evidence identifiers and locations in the prompt, or correct the report and provide the exact M2 behavior required by the canonical explanation context. Extend `M2_real_smoke.py` output/assertions to show `metadata.metrics_computed` for false, true, and warm-cache results, at least one module node's Ca/Ce/instability/cohesion/density, component/community labels, exact source range, and evidence identifiers. Do not add M6 provider/RAG behavior.

5. **Required tracking artifacts were not updated.** `PROCESS_TRACKER.md` still ends at the M1 correction pass. Both audit copies still lead with Review 1 and list CS-008–011/018–019 as Open/Partial, despite `M2_CORRECTIONS_1.md` claiming tracker/audit updates. Append the M2 submission, Review 1 correction, and this review outcome; update both audit copies to Ready for Codex review only after the remaining corrections and evidence are complete.

## Fresh verification

```text
.venv\Scripts\python.exe docs\verification\M2_codex_review_probe.py
PASS: canonical app.py:1-2 retained; unresolved fan-in/fan-out 0/0

.venv\Scripts\python.exe -m pytest tests/test_resolver_correctness.py tests/test_type_stubs.py tests/test_metrics_and_networkx.py tests/test_options_and_cache.py tests/test_explanation_canonical.py tests/test_explain_route.py tests/test_cache_integration.py --no-cov -p no:cacheprovider -q
33 passed, 1 warning

.venv\Scripts\python.exe docs\verification\M2_real_smoke.py
PASS: real API analysis/explanation/cache workflow; service.py:3-7 retained

.venv\Scripts\python.exe docs\verification\M2_review2_parity_probe.py
FAIL: Default [['0', '3'], ['1', '2']] != NetworkX [['0', '1', '2', '3']]
```

Preserve the verified location, resolved-edge filtering, metrics metadata, cache isolation, iterative SCC, resolver/stub tests, and M1 behavior. Stay within M2. Stop for Codex review without starting M3 or M4.
