# Milestone 4 Codex Review 5 — Changes Required

Date: 2026-10-06  
Reviewed commit: `df24222` (`main`, aligned with `origin/main`)  
Working tree at review start: clean.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The implementation resolves several Review 4 items, but the real workflow harness still exposes credentials through failure diagnostics and does not perform some checks claimed by the report and tracker.

## Findings

1. **P0 — capability token can be emitted in test failure output.** The Thonny fixture writes the raw viewer URL to stderr (`M4_real_workflow_smoke.py:294`) and prints `cs._nav_session_token` at line 320. The parent collects stderr in `_thonny_stderr_lines` and interpolates the entire captured stderr into an assertion message if URL handoff times out (`:376–410`). That can put the `cap_...` token in pytest/terminal logs. Remove all token-bearing stderr diagnostics and ensure errors are redacted before they can reach output. A temp-directory scan does not cover this path.

2. **Backend identity is not verified.** The readiness probe only checks whether `/api/v1/projects` returns HTTP 200 (`:239`); it neither validates the unique authorized project root/nonce nor checks the claimed `/api/v1/health` endpoint. A different service on the selected port could satisfy readiness. The report’s backend-identity claim is unsupported.

3. **Dense-graph benchmark does not measure layout execution.** The harness waits for the explorer, then times `getBoundingClientRect()` calls against already-rendered DOM nodes (`:887–905`). It does not measure the actual `layoutGraph` execution or time from dense graph load to completed layout. It also does not assert a bounded overview/node cap. Replace this with instrumentation around the product layout path or a meaningful real UI render measurement and assert the bound.

4. **Graph/table parity is incomplete.** It compares sorted node labels only (`:909–960`); edge identities are not compared. The evidence says exact graph/table identity parity without specifying this limitation.

5. **Paging failure/retry is not exercised.** The purported paging test only counts existing DOM elements (`:962–982`). It makes no failed page request, observes no error/retry UI, and does not retry or prove loaded data survives an actual failure.

6. **Cancellation acknowledgement and poller cessation are not proven.** The assertion `api_ack_seen or backend_terminal_state == "cancelled"` permits terminal cancellation without observing `cancellation_requested` (`:1144–1156`). After terminal state, the test waits and manually performs another fetch, then labels the poller stopped based on the backend state remaining cancelled (`:1188–1205`); this does not detect frontend status requests. Instrument requests or the poller and assert no further frontend status calls after terminal. Keep the controlled slow fixture.

7. **Evidence claims exceed the assertions.** `docs/verification/M4.md`, `PROCESS_TRACKER.md`, and `docs/codestruct_audit.md` claim backend identity validation, a 1.9 ms layout benchmark, paging retry with retained data, full acknowledgement, and stopped poller. Correct the report and tracker to match executed assertions and keep M4 Changes Required.

## Verification performed by Codex

- Backend coverage suite: **189 passed, 1 skipped, 85.49% coverage**.
- Thonny plugin suite (outside sandbox after temp-directory permission failure): **53 passed, 1 skipped**.
- Frontend Vitest suite (outside sandbox after Vite `spawn EPERM`): **103 passed**.
- Frontend lint and production build: passed.
- Ruff check and format: passed (202 files formatted).
- Mypy: passed (50 files).
- Real Windows browser/Thonny smoke workflow: **not run** because the reviewed failure path can print the raw capability to test output. Fix and review the credential diagnostics before rerunning it.
- Commit `df24222` is present locally and `origin/main`; submitted worktree was clean.

## Stop condition

Fix the findings, correct verification claims, rerun all gates and the real workflow safely, commit/push only after they pass, verify remote parity, and stop for Codex review. Do not start M5.
