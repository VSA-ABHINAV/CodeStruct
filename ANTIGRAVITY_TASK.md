# Antigravity task: Milestone 4 corrections — Codex Review 4

Date: 2026-10-04. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_4.md`, prior M4 Codex reviews, current `PROCESS_TRACKER.md`, `docs/verification/M4.md`, and `docs/codestruct_audit.md`. M4 remains **Changes required** at `d1f34ee887ec66e33c435ece91184c3e5fac7bd5`; no new M4 commit is present. Work only on Review 4 findings. Preserve accepted earlier milestones and frontend design. Do not begin M5.

## Required corrections

1. Fix capability handoff so the Thonny child flushes its stdout line (`flush=True` or unbuffered mode), and the parent reads it without a blocking `readline()` that can hang past its deadline. Keep the token out of disk files and persisted logs.
2. Use dynamic ports consistently. Pass the chosen backend URL to the Vite process environment; use the selected frontend port and Chrome debugging port for every launch, readiness check, CDP connection, and navigation. Verify the backend identity for this run, not just that some server responds.
3. Replace the synthetic dense-graph grid benchmark with actual Architecture Explorer layout behavior. Exercise the deterministic dense graph in the UI, verify bounded overview behavior, compare actual graph/table node and edge identities, and cover paging failure/retry while retaining loaded data.
4. Complete cancellation assertions using a deliberately slow fixture: assert disabled “Stopping…” after the UI action, observe the API acknowledgement `cancellation_requested`, prove backend terminal state is exactly `cancelled`, verify the live cancellation announcement, and prove status polling stops.
5. Under reduced-motion emulation, assert computed animation/transition behavior is reduced. Keep manual screen-reader/platform observations explicitly pending unless actually performed.
6. Reconcile `docs/verification/M4.md`, `PROCESS_TRACKER.md`, and `docs/codestruct_audit.md` with assertions actually executed. Remove unsupported claims and keep M4 Changes Required until all gates pass.

## Required verification and stop condition

Run the full backend coverage suite (`python -m pytest -q --cov=backend --cov-report=term-missing --cov-fail-under=84`), plugin tests, frontend tests/lint/build, Ruff check/format, mypy, `git diff --check`, and the real Windows backend/browser/Thonny workflow. The current full-suite rerun passed 189 tests, skipped 1, and reported 85.49% coverage; the six-failure report has not reproduced in this checkout and must be reconciled with captured command output.

Record exact, sanitized evidence. Do not claim the real workflow passed unless it was rerun after these corrections. Commit and push only this bounded M4 correction after all gates pass, verify clean worktree and remote parity, then stop for Codex review. If a gate cannot run or fails, record the exact blocker and do not commit/push. Do not start M5.

## Launch prompt

```text
Read ANTIGRAVITY_TASK.md and docs/verification/M4_CODEX_REVIEW_4.md. Implement only the outstanding M4 corrections, run the required full gates and real Windows backend/browser/Thonny workflow, record exact evidence, update the tracker and audit truthfully, and commit/push only after all required gates pass. Verify clean worktree and remote parity, then stop for Codex review. Do not begin Milestone 5.
```
