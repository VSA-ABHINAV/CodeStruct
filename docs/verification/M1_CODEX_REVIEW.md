# Codex review — Milestone 1 first submission

2026-09-26. **Decision: Changes required. M1 is not Accepted.** No production code changed by Codex. Existing git changes predate this milestone, so review targets documented M1 behavior rather than attributing the entire diff to this submission.

## Independently verified

- Backend suite: 149 passed, 1 skipped; rerun without coverage.
- Combined navigation/editor/plugin: 81 passed.
- Frontend: 73 passed across 7 files; jsdom canvas warnings do not verify geometry.
- Bare mypy: passed, 50 files. Ruff lint including plugin: passed.
- Full required format check: failed, 13 files would be reformatted. Existing debt is not a new semantic defect, but the gate is not green.
- Actual Windows junction/session/API probes reproduced failures below. Runnable: `.venv\Scripts\python.exe docs\verification\M1_review_probes.py`. Initial sandbox SQLite access failed; outside-sandbox rerun passed. Script retains task-owned temporary fixtures under `.codestruct/m1-review-*`, without executing analyzed source or deleting user files.
- Normalizing `docs/frontend-contract/graph_slice.json` with the current frontend yields null source line/column and null evidence origin/location.

## Required corrections

### R1 — P0: Registered file scope can escape via replaced ancestor (CS-001/002)

`jobs/service.py:249` and `:309` resolve the registered path before checking reparse points, without comparing the resolved identity with registration. Plugin does the same at its `resolved.is_symlink()` check. Resolving removes link information. Reproduction: register selected/app.py, rename selected, make a Windows junction selected -> other, POST navigation. Result: 200 and pending=true for a path now addressing the other root. Reject original path-component/reparse replacement at queue, delivery and IDE open, and compare canonical scope against registration. Test a real junction ancestor swap where supported.

### R2 — P1: Credentials shared across IDE sessions; poller cannot switch (CS-001/002)

`register_editor_file` reuses a capability by path digest: independent registrations of the same file return the same token, allowing IDEs to consume each other's commands. `_start_navigation_polling` returns when polling is active. Globals switch to session B, but the recursive callback continues token A; execution rejects A and never polls B until the old loop stops. Give independent sessions distinct credentials, with explicit same-session reuse if needed; implement generation-safe poll switching/stale callback rejection. Test A->B without restarting IDE and two same-file IDE sessions.

### R3 — P1: Lovable brief/fixtures are not canonical (CS-004/026)

Graph fixture nests coordinates in `location.span`, uses node `metadata` instead of canonical dict `attributes`, and invents evidence/page shapes. Normalization loses coordinates/provenance. Brief lists POST /analyses/{id}/explain; implementation is GET /analyses/{id}/nodes/{node_id}/explain. It calls Cytoscape current and recommends retaining it; actual renderer is React Flow. Claimed 60 FPS/node limits have no project benchmark. It uses running/timed_out states absent from JobState and omits complete submit/cancel/error/cache/expiry/export/paging/accessibility/hosted-preview requirements. Regenerate from real serializer/API and add contract tests; correct methods/states, unsupported claims and renderer. Do not give this brief to Lovable yet.

### R4 — P1: Frontend keeps stale editor session; errors are console-only (CS-001/002)

App captures token in state with no setter; URL removal does not clear the state on later project analysis. New project B can use old session A, particularly wrong with identical basenames. Token is not scrubbed on initial handoff despite brief claiming it is. Failures only console.warn. Associate editor session with its analysis, scrub after safe capture, clear/rebind on new analysis, disable unavailable navigation and surface safe queued/failure feedback. Test identical names in separate projects and expired credentials.

### R5 — P1: No browser origin rejection; inaccurate delivery outcomes (CS-001/002)

Valid-token POST with Origin https://untrusted.invalid returns 200. Loopback transport is not an origin policy, especially behind Vite proxy; CORS headers alone cannot reject side effects. Define trusted local origin behavior and test it. Expired pending command acknowledgement returns [true, delivered]. Plugin fallbacks can report delivered when only opening file, with no cursor placement; raw exception strings can expose private paths in failure reasons. Enforce TTL/outcome correctness, safe reason codes and truthful user-visible delivery/failure/expiry status.

### R6 — P1: Quality and real-workflow evidence gates incomplete (CS-003/023)

CI/developer instructions still omit plugin tests/lint. INI/TOML config duplication can drift. Required full formatter gate fails; do not call it clean or weaken checks. Document separate formatter-only remediation. UI logic changed but frontend coverage not reported. Thonny evidence explicitly describes headless widget-call verification, which does not establish real browser-to-IDE cursor placement. Mark pending unless genuinely observed, and link actual artifacts/runnable smoke scripts. Preserve original M1.md submission evidence.

## Probe output

```json
{"two_registrations_share_session_token":true,"untrusted_origin_post_status":200,"expired_command_ack":[true,"delivered"],"junction_created":true,"retargeted_junction_post_status":200,"retargeted_junction_pending":true}
```

Return to Antigravity for correction pass within M1; add M1_CORRECTIONS.md. Do not begin M2 or frontend creation from the incorrect contract.
