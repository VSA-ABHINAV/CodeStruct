# Antigravity task: Milestone 4 corrections — Codex Review 11

Date: 2026-10-09. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_11.md`, prior M4 reviews, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `ac1e30a`. Work only on Review 11 findings. Preserve accepted milestones and the completed Lovable frontend. Do not begin M5.

## Required corrections

1. Make Win32 Toolhelp process enumeration fail closed. Snapshot creation, first-entry failure, and unexpected iteration errors must not become `{root_pid}` or an empty active set. Distinguish normal end-of-enumeration; add injected failure-path regressions.
2. Make junction/reparse verification mandatory on Windows. Fail if the regression cannot create and recognize a junction instead of silently skipping it. Verify outside-root containment rejection.
3. Reconcile this task, tracker, M4 report, and audit to Review 11 and actual evidence.

## Required verification and stop condition

Run full backend coverage, plugin tests, frontend tests/lint/build, Ruff check/format, mypy, smoke-script syntax, `git diff --check`, and the real Windows backend/browser/Thonny workflow. Record sanitized Toolhelp failure evidence and positively verified junction/reparse behavior. Commit/push only after all gates pass; verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_11.md. Implement only the listed M4 corrections: make every Win32 Toolhelp snapshot/enumeration failure fail closed with regression coverage, require a positively verified Windows junction/reparse and outside-root containment test, reconcile the task/tracker/audit/report, run all required gates plus the real Windows backend/browser/Thonny workflow, record evidence, commit and verify remote parity only after all gates pass, then stop for Codex review. Do not begin Milestone 5.</span>
