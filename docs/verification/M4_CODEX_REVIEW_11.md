# Milestone 4 Codex Review 11 — Changes Required

Date: 2026-10-09  
Reviewed commit: `ac1e30a` (`main`, aligned with `origin/main`)  
Working tree at review start: clean.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The full automated gates and an independent real Windows workflow pass. However, the new process-tree helpers fail open when Toolhelp snapshots/enumeration fail, and the junction regression silently skips when it cannot create a junction. The handoff still points to Review 10 and commit `9027740`.

## Findings

1. **Fail closed on Toolhelp snapshot/enumeration errors.** `get_windows_process_tree_pids()` returns `{root_pid}` when `CreateToolhelp32Snapshot()` or `Process32FirstW()` fails. `get_all_active_pids_win32()` returns an empty set when its snapshot or first-entry call fails. The caller interprets that empty set as proof all tracked processes are gone, so a transient API failure can allow scanning while descendants survive. Propagate a sanitized failure instead. Also distinguish normal `Process32NextW` end-of-enumeration from an actual API error rather than accepting a partial process list. Add injected failure-path regressions.

2. **Require the Windows junction regression to execute.** The test only checks for rejection under `if junc_created:`. If `mklink /J` fails or `is_reparse_or_link()` misses the junction, the smoke continues successfully without exercising the required branch. On Windows, assert the junction was created and recognized, or explicitly report a blocked verification and fail the gate. Include a deterministic assertion that canonical containment rejects a link to a target outside the scan root.

3. **Refresh the handoff for this review.** `ANTIGRAVITY_TASK.md` still says Review 10 at base `9027740`, while the tracker/report submit Pass 11 at `ac1e30a`. Update the task to the exact remaining corrections and next review.

## Verification performed by Codex

- Backend coverage: **189 passed, 1 skipped, 85.42%**.
- Thonny plugin tests: **53 passed, 1 skipped**.
- Frontend Vitest: **104 passed**; ESLint and production build passed.
- Ruff check and format, mypy, smoke-script compilation, and `git diff --check`: passed.
- Independent real Windows workflow: **exit 0**; nonce `75b32a92`, cursor `4.4`, 186 nodes/247 edges with graph/table parity, terminal cancellation `cancelled`, and scan of 156 directories/387 files with zero token matches.
- Worktree was clean at review start and `HEAD` matched `origin/main`.
- Manual screen-reader observation remains pending.

## Stop condition

Correct findings 1–3, run all required gates and the real Windows workflow with fail-closed Toolhelp and a positively verified junction/reparse regression, record evidence, commit/push only after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin M5.
