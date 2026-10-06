# Milestone 4 Codex Review 6 — Changes Required

Date: 2026-10-06  
Reviewed commit: `640534e` (`main`, aligned with `origin/main`)  
Working tree at review start: clean.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The update improves redaction and adds nonce/layout/parity instrumentation, but the submitted quality gate fails and key paging/cancellation claims still are not demonstrated by the harness.

## Findings

1. **Frontend lint fails on render-time instrumentation.** `frontend/src/features/architecture/ArchitectureExplorer.jsx` calls impure `performance.now()` during render and mutates `window` from `useMemo`. `npm.cmd run lint --prefix frontend` reports five `react-hooks/purity` / `react-hooks/immutability` errors (around lines 92–98). Move timing instrumentation out of render in a way consistent with React purity, retain a verifiable measurement, and rerun lint/tests/build.

2. **Poller instrumentation is destroyed before measurement.** The smoke harness installs `window.__poll_request_log` and wraps `window.fetch` on the current page (`M4_real_workflow_smoke.py:1204–1216`), then performs a full `Page.navigate` to the cancellation viewer (`:1242–1251`). That navigation creates a new document and discards the log/wrapper. Later evaluations read `window.__poll_request_log.filter(...)` with `.get("value", 0)` fallback (`:1421–1438`); a JavaScript exception therefore becomes a zero count on both sides and can falsely pass. Install instrumentation in the new document before application scripts (or use CDP Network events), assert the logger exists and observed status requests before cancellation, and then assert no new status requests after terminal.

3. **Cancellation API acknowledgement is not exact.** The test accepts either `cancellation_requested` or `cancelled` in the DELETE response (`:1311–1328`) and then unconditionally sets `api_ack_seen = True`. This does not prove the requested intermediate acknowledgement. Preserve a deliberately slow job, capture the actual UI cancellation response, and require the exact `cancellation_requested` state before asserting terminal `cancelled`.

4. **Paging failure/retry is not exercised through the UI.** The test wraps `window.fetch`, manually issues a fabricated `?cursor=test_cursor` request, then manually retries the first page (`:1097–1147`). It does not trigger the Architecture Explorer's load-more action, assert a visible paging error/retry affordance, or establish the hook's loaded graph state was retained through an actual paging failure. Test the real UI action and retry, and assert loaded node/edge identities remain.

5. **Capability persistence is not fully isolated or checked.** Thonny diagnostics are now redacted before capture, which resolves the prior stderr leak. However, Chrome is launched without an explicit per-run `--user-data-dir`, while it visits the raw capability URL. The secret scan only scans the harness `temp_dir`; it cannot establish that Chrome profile/history files did not persist the URL. Use an isolated profile inside the unique temp directory, scan it before cleanup, or otherwise prove the browser does not persist the initial URL.

6. **Failure-path redaction regression is only a helper sample.** The self-test calls `redact_secrets()` on one hard-coded string (`:158–165`); it does not drive the real timeout/error construction and capture emitted output. Add a failure-path test that invokes the diagnostic formatting path and asserts the raw token is absent from emitted output.

7. **Evidence and phase status must remain blocked.** `PROCESS_TRACKER.md` and `docs/verification/M4.md` currently state every gate and the real workflow passed. Lint did not pass in Codex verification, and the paging/poller/acknowledgement assertions can pass without testing the claimed behavior. Reconcile the report/tracker/audit and keep M4 Changes Required.

## Verification performed by Codex

- Backend coverage suite: initial sandbox run had a Windows SQLite cleanup `WinError 32`; rerun outside the sandbox passed: **189 passed, 1 skipped, 85.49% coverage**.
- Thonny plugin suite (outside sandbox due temp fixture permissions): **53 passed, 1 skipped**.
- Frontend Vitest suite: **103 passed**.
- Frontend production build: passed.
- Ruff check and format: passed (203 files formatted); mypy passed (50 source files); smoke-script `py_compile` passed.
- Frontend lint: **failed**, five React purity/immutability errors in the new layout instrumentation.
- Real Windows workflow: **not run**. The checked-in smoke claims are not accepted while browser profile persistence is unisolated and its polling instrumentation is invalidated by navigation.
- `git diff --check`: not applicable to the clean submitted commit; rerun for the next working tree.

## Stop condition

Fix these findings, correct all M4 evidence, rerun the full required gates and safe real workflow, commit/push only after every required gate passes, verify remote parity, and stop for Codex review. Do not begin M5.
