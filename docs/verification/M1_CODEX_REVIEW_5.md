# Milestone 1: Codex review 5

Date: 2026-09-28. Decision: implementation checks remain passing; contract-only corrections still required. Do not begin M2.

## Fresh verification

- Backend contract, navigation and editor suites: 47 passed (`.venv\Scripts\python.exe -m pytest tests/test_contract_fixtures.py tests/test_navigate_routes.py tests/test_editor_integration.py --no-cov -p no:cacheprovider -q`).
- Frontend contract + real-hook StrictMode startup: 10 passed, 2 files (`npm.cmd test -- --reporter=dot src/api/contractFixtures.test.js src/App.strictReview.test.jsx`). Vite initially encountered sandbox EPERM; rerun outside sandbox passed.
- `M1_review5_contract_probe.py`: default 4194304 bytes; actual documented cursor rejected with `invalid graph cursor`; parser fixture produces 5 diagnostics with null locations. Temporary syntax-error fixture is statically parsed, never executed. Probe required elevated rerun after sandbox denied temporary-file access.
- Full suites/coverage/lint/build were reported by Antigravity but were not independently repeated in this narrow review. Earlier implementation review evidence remains preserved. Physical Thonny cursor observation remains pending.

## Remaining handoff errors

1. Brief sections 5.5/5.6 say full-graph cap defaults to 10MB. Both `Settings.max_full_graph_bytes` and `load_settings` default to **4 * 1024 * 1024 = 4194304 bytes (4 MiB)**. Configuration can override it. Correct documentation and evidence; compare the documented default to Settings in a regression test. Do not change backend settings to fit documentation.
2. Section 5.6's supposedly copy-pastable paged response contains a fabricated cursor ending `.a1b2c3d4e5f6`. The actual decoder rejects it. This inline response also omits endpoint nodes for its returned edge, whereas `slice_graph` includes endpoints (returned node count can exceed limit). Generate the documented page from `slice_graph` with deterministic fixture metadata, retain its exact opaque cursor, and test the actual markdown example by decoding its cursor and following it with matching graph/filter/limit context. Existing tests decode a separately generated sample, never the invalid example. The checked-in graph fixture is a complete toy graph; clearly label that versus a generated page. No pagination implementation change needed.
3. Section 5.7 guarantees every diagnostic has a structured location. Actual scanner/root/graph diagnostics can have `location=null`; 5 examples occur in the checked-in parser project. Document nullable location/references and optional span endpoints; disable source navigation when no usable start location exists. Add contract normalization checks using an actual locationless diagnostic, not a hand-written assertion that every item has a dictionary location. Null does not mean fabricate a path or line.

Other previous corrections are materially improved: supported create request now reaches the route, summary field names are canonical, error envelope fields are correct, creation graph link is null, cancellation idempotency is documented. Tests still compare summary keys rather than generated values; do not claim generated-value equality when only shape was tested. The synthetic toy graph's counts can remain if accurately labeled and internally consistent.

## Scope

CS-004/CS-023/contract CS-026 only: brief, focused fixture/document tests, evidence and tracker/audit. Preserve passing production code. These small discrepancies do not justify rerunning or rewriting the complete milestone implementation. Record corrections and stop for Codex review.
