# Antigravity task: Milestone 4 corrections — Codex Review 7

Date: 2026-10-07. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_7.md`, prior M4 reviews, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `83d88ba`. Work only on Review 7. Preserve earlier accepted milestones and frontend design. Do not begin M5.

## Required corrections

1. Remove the second production `layoutGraph()` execution currently performed in `useEffect` after the same graph was already laid out in `useMemo`. Keep useful actual-layout evidence through a test-only instrumentation path or another approach that does not duplicate normal product work. Preserve React purity and rerun frontend lint/tests/build plus the real layout smoke assertion.
2. Make `scan_for_secret_tokens()` fail closed: do not continue when a profile/temp file cannot be inspected. Report a sanitized error without file contents or secrets. Ensure Chrome and any child processes have fully exited before scanning; if a process must be killed, wait for termination before scanning. Claim zero persisted tokens only if the entire isolated profile and temp directory were readable and scanned.
3. Reconcile M4 report, tracker, and audit with the actual resulting assertions and gates.

## Required verification and stop condition

Run full backend coverage, plugin tests, frontend tests/lint/build, Ruff check/format, mypy, smoke-script syntax, `git diff --check`, and the real Windows backend/browser/Thonny workflow. Capture sanitized output and distinguish any unreadable-file or process-cleanup failure. Commit/push only after every required gate passes, verify clean worktree and remote parity, then stop for Codex review. Do not begin M5.

## Launch prompt

```text
Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_7.md. Implement only the listed M4 corrections, preserve the real layout measurement without a second production layout computation, make secret scanning fail closed and wait for Chrome/profile quiescence, run all required gates and the real Windows workflow, update evidence and tracker/audit truthfully, commit/push only after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.
```
