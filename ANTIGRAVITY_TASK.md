# Antigravity task: Milestone 4 corrections — Codex Review 6

Date: 2026-10-06. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_6.md`, prior M4 reviews, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `640534e`. Work only on Review 6; preserve earlier accepted milestones and the frontend design. Do not begin M5.

## Required corrections

1. Move `layoutGraph` timing out of React render/`useMemo` so lint passes and the measurement still reports the actual product layout work.
2. Fix the cancellation poller probe: its current instrumentation is installed before a full-page navigation and is discarded. Install the fetch/network instrumentation in the new document before app code (or use CDP Network events), assert it records status calls before cancellation, and prove no new status calls occur after terminal. Fail if instrumentation is absent or its count is zero before cancellation.
3. Make the cancellation fixture reliably slow and require the UI's actual DELETE acknowledgement state to be exactly `cancellation_requested`; remove any acceptance of a response already in terminal `cancelled` as the acknowledgement. Then verify backend terminal `cancelled` and live UI announcement.
4. Exercise pagination through the actual Architecture Explorer action. Force its next-page request to fail, assert the visible error/retry UI and unchanged loaded node/edge identities, activate retry, and verify it succeeds and merges the expected page.
5. Isolate Chrome with a unique `--user-data-dir` under the smoke temp directory (or give equally concrete evidence the raw viewer URL cannot be persisted). Scan the isolated profile for the capability before deleting it. Keep tokens out of all diagnostics and add a failure-path test of the actual formatted output path, not only the redaction helper.
6. Correct `docs/verification/M4.md`, `PROCESS_TRACKER.md`, and `docs/codestruct_audit.md` to match actual test evidence. Keep M4 Changes Required until every gate and the real workflow pass.

## Required verification and stop condition

Run full backend coverage, plugin tests, frontend tests/lint/build, Ruff check/format, mypy, smoke-script syntax, `git diff --check`, and the real Windows backend/browser/Thonny workflow. Capture sanitized output. Do not claim completion for a skipped or failed gate. Commit/push only this bounded M4 correction after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin M5.

## Launch prompt

```text
Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_6.md. Implement only the listed M4 corrections, run all required gates and the real Windows backend/browser/Thonny workflow with an isolated Chrome profile and no capability in any output, update verification evidence and tracker/audit truthfully, commit/push only after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.
```
