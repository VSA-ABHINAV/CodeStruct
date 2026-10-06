# Antigravity task: Milestone 4 corrections — Codex Review 5

Date: 2026-10-06. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_5.md`, prior M4 Codex reviews, current `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `df24222`. Work only on Review 5. Preserve earlier accepted milestones and frontend design. Do not begin M5.

## Required corrections

1. **P0 credential redaction:** Remove all raw capability-bearing URLs/tokens from Thonny stderr diagnostics, captured errors, assertion messages, and any persisted logs. Redact before formatting errors. Add a failure-path regression that proves the secret never appears in output, not only a temp-directory scan.
2. **Backend identity:** After starting the backend, verify an endpoint response contains this run's unique root/database nonce (and verify the expected health route if one is documented). A generic HTTP 200 from `/api/v1/projects` is not sufficient to show the service belongs to this run.
3. **CS-007 layout:** Measure actual dense graph layout execution or meaningful render completion around the product's `layoutGraph`/Architecture Explorer path; do not time post-render `getBoundingClientRect()` calls as layout execution. Assert the defined bounded overview behavior on the deterministic dense graph.
4. **CS-007 parity and paging:** Compare both node and edge identities between graph and table views. Trigger an actual paging failure, assert its visible error state, retry, and prove already-loaded data remains.
5. **CS-021 exact cancellation:** Require observation of `cancellation_requested` (remove the `or terminal cancelled` escape), then assert terminal `cancelled`. Instrument API/status requests or the poller itself to demonstrate that the frontend makes no more status polls after terminal; a manual backend fetch and unchanged status do not prove that.
6. Correct `docs/verification/M4.md`, `PROCESS_TRACKER.md`, and `docs/codestruct_audit.md` so every claim corresponds to an assertion and evidence actually captured. Keep screen-reader checks marked pending unless performed.

## Required verification and stop condition

Run the full backend coverage suite, plugin tests, frontend tests/lint/build, Ruff check/format, mypy, `git diff --check`, and the real Windows backend/browser/Thonny workflow after fixing credential diagnostics. Record exact sanitized output. Do not claim completion if a gate fails or was not run. Commit/push only this bounded M4 correction once all gates pass, verify a clean worktree and remote parity, then stop for Codex review. Do not begin M5.

## Launch prompt

```text
Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_5.md. Implement only the listed M4 corrections, run all required gates and the real Windows backend/browser/Thonny workflow without exposing the capability in any output, update verification evidence and tracker/audit truthfully, commit/push only after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.
```
