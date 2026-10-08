# Antigravity task: Milestone 4 corrections — Codex Review 8

Date: 2026-10-08. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_8.md`, prior M4 reviews, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `fe3b863`. Work only on Review 8 findings. Preserve accepted milestones and the completed Lovable frontend. Do not begin M5.

## Required corrections

1. Keep `layoutGraph()` pure during React render. Preserve one product layout execution and expose real layout timing/count evidence only through explicit test/benchmark instrumentation that does not write globals during render. Keep the actual dense-graph layout assertion meaningful.
2. Make secret scanning fail closed for directory enumeration and file reads. Replace traversal that can suppress filesystem errors with traversal that surfaces every inaccessible directory/entry. Ensure Chrome and all descendants have exited and the isolated profile is quiescent before scanning; do not claim zero persisted tokens unless the entire temp tree was enumerated and inspected.
3. Investigate and resolve the flaky full-suite `CacheIntegrationTests.test_cold_warm_refresh_and_restart` result. It failed in the full coverage run but passed alone; full suite must pass reliably.
4. Reconcile audit, tracker, M4 report, and review evidence with the actual changes and gates.

## Required verification and stop condition

Run full backend coverage, plugin tests, frontend tests/lint/build, Ruff check/format, mypy, smoke-script syntax, `git diff --check`, and the real Windows backend/browser/Thonny workflow against the resulting commit. Record sanitized output, including traversal coverage and process-tree cleanup evidence. Commit/push only after every required gate passes; verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_8.md. Implement only the listed M4 corrections, keep layoutGraph pure during React render while preserving one real layout pass and testable timing evidence, make complete temp/profile scanning and Chrome descendant shutdown fail closed, resolve the flaky full-suite cache test, run every required gate plus the real Windows backend/browser/Thonny workflow, update PROCESS_TRACKER.md and audit/report evidence, commit and verify remote parity only after all gates pass, then stop for Codex review. Do not begin Milestone 5.</span>
