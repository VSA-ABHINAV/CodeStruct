# Milestone 4 Codex Review 4 — Changes Required

Date: 2026-10-04  
Reviewed checkout: `d1f34ee887ec66e33c435ece91184c3e5fac7bd5` (`main`, same as `origin/main`)  
Working tree: Antigravity changes are uncommitted; no new M4 commit is present.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The current M4 task, tracker, and verification report were not advanced to Review 4, and the smoke harness still contains several of the exact defects from the prior handoff.

## Findings

1. **Capability pipe can block before the browser starts.** The child prints the token-bearing viewer URL without `flush=True` (`M4_real_workflow_smoke.py:301`). Its stdout is a pipe, so Python may buffer the line. The parent immediately calls blocking `readline()` (`:334`) inside a nominal deadline loop; the deadline cannot interrupt that blocking read.

2. **Dynamic service isolation is incomplete.** Backend and frontend ports are selected dynamically, but Vite is not launched with `CODESTRUCT_BACKEND_URL`, so `frontend/vite.config.js:16` falls back to port 8000. Chrome is hardcoded to debugging port 9222 (`:360`, `:371`, `:816`), and cancellation navigates to frontend port 5173 (`:825`). Thus the real workflow can connect to unrelated services or fail after its startup checks.

3. **Dense-graph timing remains synthetic.** The harness constructs a grid with `nodes.map` and times that operation (`:756–768`); it does not call the product layout function or measure Architecture Explorer rendering/layout. It does not establish graph/table identity parity or the requested pagination failure/retry behavior.

4. **Cancellation evidence is incomplete.** The test clicks a matching button and later searches general page text for “cancelled” (`:871–928`). It does not assert the disabled “Stopping…” state, observe the API acknowledgement, inspect backend terminal state, verify the live announcement, or establish that polling stopped.

5. **Reduced-motion evidence is only media-query emulation.** It checks `matchMedia(...).matches` (`:565–585`) but not computed animation/transition behavior. No screen-reader observation is recorded.

6. **Submitted docs still overstate verification.** `docs/verification/M4.md` claims dynamic-looking full workflow results, actual dense layout/parity and completed cancellation/reduced-motion checks. `PROCESS_TRACKER.md` and `docs/codestruct_audit.md` still point to Review 3 as current and contain readiness claims unsupported by this checkout. Keep status Changes Required and reconcile these documents against rerun evidence.

## Verification performed by Codex

- `.venv\Scripts\python.exe -m pytest -q --cov=backend --cov-report=term-missing --cov-fail-under=84`: **189 passed, 1 skipped, 85.49% coverage**, exit code 0. This does not reproduce the reported six failures; Antigravity must reconcile the discrepancy with exact logs/checkout/command.
- `.venv\Scripts\python.exe -m py_compile docs\verification\M4_real_workflow_smoke.py`: passed.
- `git diff --check`: passed before this review report/task update.
- Real browser/Thonny workflow: **not run in this review**; the inspected hardcoded-port and stdout defects make the claimed run non-reproducible from the current harness. No acceptance credit is given for old tracker prose.
- Plugin/frontend/Ruff/mypy gates: not rerun in this review.

## Stop condition

Fix the six findings, capture exact gate output, run the real workflow after corrections, and update all M4 evidence truthfully. Commit/push only after all required gates pass, verify parity, and stop for Codex review. Do not start M5.
