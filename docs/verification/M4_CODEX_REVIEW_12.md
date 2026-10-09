# Milestone 4 Codex Review 12 — Changes Required

Date: 2026-10-09  
Reviewed commit: `e1d6e52` (`main`, aligned with `origin/main`)  
Working tree at review start: clean.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The automated quality gates pass, and the smoke harness completed its new Toolhelp failure injections and mandatory junction/containment regressions. The required live workflow then failed before browser startup because the configured Thonny environment could not import `minny.target`. The handoff file also still points to Review 11 and base commit `ac1e30a`.

## Findings

1. **Restore a reproducible real Thonny workflow.** Independent run of `M4_real_workflow_smoke.py` exited 1 at the Thonny startup assertion. The configured interpreter is `D:\REP\thonny\venv\Scripts\python.exe`; it has `minny` version `0.0.1a2`, but `importlib.util.find_spec("minny.target")` returns `None`. Thonny exits while loading its `calliope`, `microbit`, `rp2040`, and `rpi_pico` plugins with `ModuleNotFoundError: No module named 'minny.target'`, before the browser/backend/Thonny integration assertions run. Repair or select a compatible, documented Thonny test environment, or use a supported isolated Thonny configuration that skips those incompatible optional built-ins while still loading and exercising CodeStruct. Then rerun the complete real workflow and record proof that the actual workbench and CodeStruct plugin started.

2. **Update the handoff for this review.** `ANTIGRAVITY_TASK.md` still says Review 11 and base `ac1e30a`, while the tracker/report say Pass 12 at `e1d6e52`. Replace it with the exact bounded Thonny environment/workflow task and current review reference.

## Verification performed by Codex

- Backend coverage: **189 passed, 1 skipped, 85.34%**.
- Thonny plugin tests: **53 passed, 1 skipped**.
- Frontend Vitest: **104 passed**; ESLint and production build passed.
- Ruff check/format, mypy, smoke-script compilation, and `git diff --check`: passed.
- Real Windows smoke: **failed before browser startup** at Thonny launch due to missing `minny.target`. The new step-0 Toolhelp failure injections and junction checks occur earlier in the script and completed successfully before this failure.
- Thonny environment inspection: package `minny` version `0.0.1a2` is installed in the configured venv; `minny.target` is absent.
- Worktree was clean at review start and `HEAD` matched `origin/main`.
- Manual screen-reader observation remains pending.

## Stop condition

Correct findings 1–2, rerun all required gates and the complete real Windows browser/backend/Thonny workflow, record sanitized evidence, commit/push only after all gates pass, verify clean worktree and remote parity, then stop for Codex review. Do not begin M5.
