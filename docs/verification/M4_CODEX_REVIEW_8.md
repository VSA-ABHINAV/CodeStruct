# Milestone 4 Codex Review 8 — Changes Required

Date: 2026-10-08  
Reviewed commit: `fe3b863` (`main`, previously reported aligned with `origin/main`)  
Working tree at review start: clean.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The latest frontend and static checks pass, but the layout measurement adds global side effects during React render, and the secret scan still cannot prove that every directory was traversed. The full backend run also had one cache integration failure; that test passed when run alone, so the full-suite result is not clean or deterministic yet.

## Findings

1. **Keep layout computation pure.** `ArchitectureExplorer.jsx` calls `layoutGraph()` from `useMemo` during render. `graphLayout.js` now writes timing and graph counts onto `window` inside that function. This makes normal render computation mutate global state and leaves test/benchmark instrumentation in the product path. Preserve the single layout pass, but move measurement to an explicit opt-in/test instrumentation path that does not mutate globals from render.

2. **Prove complete secret-scan traversal.** `scan_for_secret_tokens()` uses `Path.rglob()` and catches errors reading yielded files, but recursive glob traversal can suppress filesystem scanning errors. The `scanned_file_count > 0` assertion does not establish that every directory was enumerated. Use traversal that surfaces directory enumeration failures, and fail closed on any unreadable entry. Process cleanup waits for the direct Chrome `Popen` process only; demonstrate profile quiescence including Chrome descendants before scanning, or use a process-tree/job mechanism and verify it is empty.

3. **Make the required backend gate reliable.** Full coverage run: **1 failed, 188 passed, 1 skipped, 85.56% coverage**. The failing `CacheIntegrationTests.test_cold_warm_refresh_and_restart` asserted that the warm request hit cache; a standalone rerun passed (**1 passed**), indicating a flaky/interference-sensitive test. Resolve or isolate the cause and rerun the full suite successfully before claiming all gates pass.

## Verification performed by Codex

- Frontend Vitest: **103 passed**.
- Frontend ESLint: completed with exit 0.
- Frontend production build: passed.
- Ruff check and format: passed (205 files already formatted).
- mypy: passed (48 source files).
- Smoke script `py_compile`: passed.
- Backend full coverage: failed as described above; standalone failing test passed on rerun.
- Real Windows backend/browser/Thonny workflow: **not rerun for this commit**. Prior-commit evidence does not verify the current layout instrumentation or scanner changes.
- No M5 work was reviewed or authorized.

## Stop condition

Correct findings 1–3, run every required gate and the real Windows workflow on the resulting commit, record sanitized evidence, commit/push only after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin M5.
