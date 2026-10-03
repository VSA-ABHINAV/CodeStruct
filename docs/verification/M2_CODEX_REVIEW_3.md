# Milestone 2 Codex Review 3

**Date:** 2026-10-03  
**Decision:** Changes required  
**Scope reviewed:** CS-008–011 and CS-018–019 only.

The canonical-location, resolved-edge filtering, metrics metadata, module metrics, fallback behavior, stub/resolver characterization, prompt evidence, and real API/cache workflow now pass focused independent review. Milestone 2 is not Accepted because community results still depend on whether NetworkX is installed, and the final evidence/audit artifacts remain inaccurate.

## Blocking findings

1. **Adapter community parity still fails (CS-009/010).** The revised `M2_review2_parity_probe.py` enumerates every labeled simple undirected graph on four and five nodes. All 64 four-node graphs pass, but the five-node graph at mask 58 with edges `0–2`, `0–4`, `1–2`, `1–3` fails. Default returns `{0,2,4}/{1,3}`; NetworkX returns `{0,4}/{1,2,3}`. The submitted test named `test_small_graph_community_parity_corpus` contains only eight selected fixtures, so its “exhaustive” docstring and the reports' “100% parity” claims are false. Stop duplicating NetworkX tie behavior heuristically. Define one canonical community-partition routine shared by both adapters, while retaining genuine transient NetworkX use for the other NetworkX-backed computations, or otherwise prove identical canonical output across the exhaustive bounded corpus. Preserve deterministic IDs after normalizing partitions.

2. **The final verification documents remain stale or misidentified.** `docs/verification/M2.md` still reports 174 backend tests, only 3 metric tests, and the old smoke output without metrics metadata, component IDs, exact source range, module metrics, or evidence references. Reconcile it with the final implementation and current commands rather than changing only its summary bullets. `M2_CORRECTIONS_2.md` must include the required full backend coverage, Ruff check/format, mypy, and plugin commands/results instead of relying on tracker-only claims.

3. **The external audit mirror was not updated.** The internal audit SHA-256 differs from the external mirror at the path declared in the audit header. `docs/codestruct_audit_2026-09-23_original.md` is the preserved historical baseline, not the external audit copy; do not edit or describe it as a synchronized mirror. After corrections, update `docs/codestruct_audit.md` and copy that exact file to the declared external path, then verify matching hashes.

## Fresh verification

```text
M2_review2_parity_probe.py
PASS: all 64 labeled four-node graphs
FAIL: five nodes, mask 58, edges [('0','2'), ('0','4'), ('1','2'), ('1','3')]
Default:  [['0','2','4'], ['1','3']]
NetworkX: [['0','4'], ['1','2','3']]

Focused M2 suite: 35 passed, 1 warning
M2_codex_review_probe.py: PASS, app.py:1-2 and unresolved fan-in/fan-out 0/0
M2_real_smoke.py: PASS outside sandbox; false/true/warm-cache metadata, module metrics,
service.py:3-7, component/community fields, and three bounded evidence references verified
```

Preserve every verified M1 and M2 behavior. Correct only the remaining M2 parity and evidence reconciliation. Stop for Codex review; do not begin M3 or M4.
