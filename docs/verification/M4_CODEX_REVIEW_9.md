# Milestone 4 Codex Review 9 — Changes Required

Date: 2026-10-08  
Reviewed commit: `8d0810b` (`main`, aligned with `origin/main`)  
Working tree at review start: clean.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The cache integration correction is passing the full suite, and the layout function is pure. Two independent runs of the real workflow did not agree: the first failed the cancellation lifecycle, while the second passed. Process-tree shutdown also ignores taskkill failures and confirms only the parent process has exited. Finally, the scanner silently skips entries that are neither regular files nor directories.

## Findings

1. **Make the real cancellation workflow deterministic and diagnosable.** The first Codex run of `M4_real_workflow_smoke.py` ended with `backend_terminal_state == "failed"` at the cancellation assertion; a second run on the same commit passed with terminal `cancelled`. The failure assertion reports only the state, so it does not expose the sanitized API `error_code`/`message_code` needed to diagnose the failed run. Fix the underlying race or fixture issue, include safe diagnostic fields on failure, and repeat the real workflow until the behavior is stable. Do not count a passing rerun as resolving the earlier failure by itself.

2. **Verify process-tree quiescence fail closed.** `stop_process_tree_and_wait()` invokes `taskkill /F /T` with `check=False`, suppresses launch exceptions, and then waits only for the direct `Popen` parent. A failed taskkill or surviving Chrome descendant does not fail the helper, so scanning may begin with profile files still open. Require successful tree termination (allowing only a clearly verified already-exited case) and verify descendants are gone before scanning; add a regression for taskkill failure or a surviving child.

3. **Do not silently skip unexpected filesystem entries.** `scan_for_secret_tokens()` only reads entries when `is_file()` and recurses when `is_dir()`. Any entry for which both are false is silently skipped. Fail closed on unsupported/special/reparse entries or explicitly prove and verify safe handling for them; retain sanitized errors and complete traversal counts.

4. **Reconcile the handoff and audit details.** `ANTIGRAVITY_TASK.md` still directs Review 8 work at `fe3b863`, while the tracker says Pass 9 is ready. The per-issue CS-006/CS-007 rows in `docs/codestruct_audit.md` still show Review 8 findings even though its history claims they were fixed. Update these records to the actual review state and next bounded scope.

## Verification performed by Codex

- Backend coverage: **189 passed, 1 skipped, 85.49%**.
- Thonny plugin tests: **53 passed, 1 skipped**.
- Frontend Vitest: **104 passed**.
- ESLint, frontend build, Ruff check/format, mypy, smoke-script compilation, and `git diff --check`: passed.
- Real Windows workflow run 1: failed; backend cancellation terminal state was `failed` instead of `cancelled`.
- Real Windows workflow run 2: passed; backend identity nonce `6b460f3a`, cursor `4.4`, 186 nodes/247 edges, complete graph/table parity, cancellation terminal `cancelled`, and recursive scan 413 directories/961 files with zero token matches.
- Worktree was clean at review start and `HEAD` matched `origin/main`.
- Manual screen-reader review remains pending as already recorded.

## Stop condition

Resolve findings 1–4, run every required gate and repeated real Windows workflow checks with stable cancellation and verified process-tree shutdown, record sanitized evidence, commit/push only after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin M5.
