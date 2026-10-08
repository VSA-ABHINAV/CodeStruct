# Antigravity task: Milestone 4 corrections — Codex Review 10

Date: 2026-10-08. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_10.md`, prior M4 reviews, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `9027740`. Work only on Review 10 findings. Preserve accepted milestones and the completed Lovable frontend. Do not begin M5.

## Required corrections

1. Prove full process-tree quiescence before scanning. Capture and assert child/descendant process exit or use a waitable Windows Job Object/process-tree mechanism. Extend the regression to assert the child is gone, not just the parent.
2. Make scanning reject Windows junctions and all reparse points, or safely prove canonical containment. Add a regression for reparse traversal.
3. Correct failure diagnostics: the public job response has no `error_code`, so do not claim to capture one when it is always `None`. Use the available sanitized message code or add a properly scoped API field if necessary.
4. Reconcile the task, tracker, report, and audit to Review 10 and the actual evidence.

## Required verification and stop condition

Run full backend coverage, plugin tests, frontend tests/lint/build, Ruff check/format, mypy, smoke-script syntax, `git diff --check`, and the real Windows backend/browser/Thonny workflow. Record sanitized evidence that descendant processes are gone before scanning and that reparse points fail closed. Commit/push only after all gates pass; verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_10.md. Implement only the listed M4 corrections: verify every child/descendant has exited before scanning, reject Windows junctions/reparse points or prove containment, make cancellation failure diagnostics accurate and sanitized, reconcile the handoff/tracker/audit/report, run all required gates and the real Windows backend/browser/Thonny workflow, record evidence, commit and verify remote parity only after all gates pass, then stop for Codex review. Do not begin Milestone 5.</span>
