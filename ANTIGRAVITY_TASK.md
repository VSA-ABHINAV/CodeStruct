# Antigravity task: Milestone 4 corrections — Codex Review 9

Date: 2026-10-08. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_9.md`, prior M4 reviews, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `8d0810b`. Work only on Review 9 findings. Preserve accepted milestones and the completed Lovable frontend. Do not begin M5.

## Required corrections

1. Diagnose the real smoke cancellation failure (`backend_terminal_state == "failed"` on the first Codex run, `cancelled` on a second run). Fix the underlying cause, expose sanitized `error_code`/`message_code` diagnostics when a terminal assertion fails, and demonstrate repeatable real-workflow success.
2. Make process-tree teardown fail closed. Do not suppress `taskkill` launch/exit failures or treat parent exit as proof that descendants are gone. Verify the entire process tree is quiescent before scanning; add a focused failure-path regression.
3. Make the recursive secret scanner fail closed on every entry. Do not silently skip entries that are neither regular files nor directories; handle reparse/special entries safely or fail with a sanitized error. Keep directory/file counts truthful.
4. Reconcile `ANTIGRAVITY_TASK.md`, tracker, M4 report, audit history, and CS-006/CS-007 status with this review and actual verification evidence.

## Required verification and stop condition

Run full backend coverage, plugin tests, frontend tests/lint/build, Ruff check/format, mypy, smoke-script syntax, `git diff --check`, and repeated real Windows backend/browser/Thonny workflow runs. Record sanitized cancellation diagnostics and process-tree proof. Commit/push only after all gates pass and repeated workflow runs are stable; verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_9.md. Implement only the listed M4 corrections: diagnose and eliminate the real cancellation workflow failure with sanitized failure details, make process-tree shutdown and every filesystem scan entry fail closed, reconcile the task/tracker/audit/report, run all required gates and repeated real Windows backend/browser/Thonny workflows until stable, record evidence, commit and verify remote parity only after all gates pass, then stop for Codex review. Do not begin Milestone 5.</span>
