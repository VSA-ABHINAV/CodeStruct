# Antigravity task: Milestone 4 corrections — Codex Review 12

Date: 2026-10-09. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_12.md`, prior M4 reviews, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `e1d6e52`. Work only on Review 12 findings. Preserve accepted milestones and the completed Lovable frontend. Do not begin M5.

## Required corrections

1. Diagnose and fix the configured Thonny workflow environment: `D:\REP\thonny\venv\Scripts\python.exe` has `minny==0.0.1a2` without `minny.target`, causing Thonny to exit before browser startup. Restore a compatible, documented Thonny test setup or configure a supported isolated workbench that skips only incompatible optional built-ins while still loading and exercising CodeStruct. Do not treat plugin unit tests or a partial smoke as proof of the real workflow.
2. Update this handoff, tracker, report, and audit to Review 12 and current evidence.

## Required verification and stop condition

Run full backend coverage, plugin tests, frontend tests/lint/build, Ruff check/format, mypy, smoke-script syntax, `git diff --check`, and the complete real Windows backend/browser/Thonny workflow. Record the interpreter/environment used, prove the CodeStruct Thonny plugin loaded, and capture navigation to the live editor cursor. Commit/push only after all gates pass; verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_12.md. Implement only the listed M4 corrections: repair or select a compatible documented Thonny workflow environment so the real workbench and CodeStruct plugin start despite the missing minny.target in the current venv, preserve and verify live editor navigation, reconcile task/tracker/audit/report, run all required gates and the complete real Windows backend/browser/Thonny workflow, record evidence, commit and verify remote parity only after all gates pass, then stop for Codex review. Do not begin Milestone 5.</span>
