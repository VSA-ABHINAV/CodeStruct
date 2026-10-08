# Milestone 4 Codex Review 10 — Changes Required

Date: 2026-10-08  
Reviewed commit: `9027740` (`main`, aligned with `origin/main`)  
Working tree at review start: clean.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The full automated suites and two independent real workflow runs pass. The process-tree check still verifies only the direct parent PID, and the scanner's symlink check does not cover Windows junction/reparse points. The task handoff is also still scoped to Review 9 despite Pass 10 being submitted.

## Findings

1. **Verify descendants, not only the parent.** `stop_process_tree_and_wait()` runs `taskkill /T`, but the subsequent `tasklist /FI "PID eq <root>"` checks only the root PID. The regression starts a child process but records/asserts only `test_spawn.poll()` for the parent. This does not demonstrate that child processes have exited before profile scanning. Capture and verify descendant PIDs (or use a Windows Job Object/process-tree mechanism that provides a waitable empty-tree guarantee), and make the regression assert the child is gone.

2. **Detect all Windows reparse points.** `scan_for_secret_tokens()` rejects `Path.is_symlink()`, but Windows junctions/reparse points are not necessarily symlinks; a junction may satisfy `is_dir()` and cause traversal outside the isolated temporary root. Reject reparse points (including junctions) or prove canonical containment before recursing. Add a regression for a junction/reparse entry where the environment supports it, with a deterministic mocked attribute fallback if necessary.

3. **Make the failure diagnostic claim accurate.** `backend_error_code = job_data.get("error_code")` reads a field absent from the public `JobResponse` schema, so it is always `None`. Either expose/use an approved sanitized error-code field or report the available `progress.message_code` without claiming an error code was captured. Keep failure output bounded and non-secret.

4. **Update the handoff to the current review.** `ANTIGRAVITY_TASK.md` still identifies Review 9 and base commit `8d0810b`; the tracker/report say Pass 10 at `9027740`. Reconcile it with Review 10 and the next bounded corrections.

## Verification performed by Codex

- Backend coverage: **189 passed, 1 skipped, 85.34%**.
- Thonny plugin tests: **53 passed, 1 skipped**.
- Frontend Vitest: **104 passed**; ESLint and production build passed.
- Ruff check/format, mypy, smoke-script compilation, and `git diff --check`: passed.
- Real Windows workflow run 1: passed; cancellation terminal `cancelled`, cursor `4.4`, 186 nodes/247 edges with graph/table parity, scanner 413 directories/982 files.
- Real Windows workflow run 2: passed with the same functional assertions; scanner 413 directories/982 files.
- Worktree was clean at review start and `HEAD` matched `origin/main`.
- Manual screen-reader observation remains pending.

## Stop condition

Correct findings 1–4, run all required gates and the real Windows workflow, record descendant/reparse and sanitized diagnostic evidence, commit/push only after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin M5.
