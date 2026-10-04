# Codex Review 1 — Milestone 4

**Date:** 2026-10-04
**Decision:** Changes required
**Reviewed commit:** `41a7da613592813be014032f9a7226fd657007a8` (`feat(m4): integrate lovable frontend with backend services and verify real workflow`)

## What I verified

- Worktree at review start was clean; `main` tracked `origin/main` at the reviewed commit.
- `npm.cmd test -- --reporter=dot` in `frontend/`: **10 test files, 96 tests passed**.
- `docs/verification/M4_real_workflow_smoke.py`: passed after rerunning with an isolated database bootstrap path outside the sandbox. The first run was blocked by Windows temporary-directory permissions.
- The smoke script exercises real FastAPI routes and job/storage behavior, but uses `starlette.testclient.TestClient`; it does not start Vite, open a browser, run the Thonny plugin, or exercise UI accessibility.
- `git diff HEAD^ HEAD --check` reports trailing whitespace in `docs/verification/M4.md` and an extra blank line at EOF in `DetailsPanel.component.test.jsx`.

## Findings

1. **CS-007 remains unimplemented/unverified.** The audit defines this as dense-graph layout/render caps, aggregation or progressive loading, loaded/total counts, table parity, and page failure/retry behavior. The code diff adds no such layout or graph/table behavior; the smoke only checks a backend page response. DOT export is CS-017 work and was expressly outside the M4 task. Remove the M4 DOT endpoint/UI integration and its M4 claims, leaving the existing client-side export behavior intact, or otherwise keep it out of this milestone. Implement and test the bounded CS-007 behavior from the task.
2. **CS-021 cancellation evidence is not a passing cancellation test.** The smoke accepts `completed` as a valid response to an immediate cancellation request and never polls for a terminal cancellation outcome. It does not exercise the frontend cancel control, acknowledgement-to-terminal transition, polling stop, timeout, or UI error feedback. Use a controlled long-running job, assert the actual cancellation request/acknowledgement and terminal state, and add a frontend regression for the visible lifecycle and failure path.
3. **CS-022 real accessibility/workflow gate is missing.** The report maps editor navigation to CS-022, while the audit defines CS-022 as accessibility and platform/browser verification. The cited axe tests are automated support and were not added in this commit; there is no actual keyboard/focus, screen-reader/status, zoom/reflow, reduced-motion, or browser verification evidence. Perform and record the required Windows browser workflow against the supplied design. Keep editor navigation under CS-006.
4. **The smoke is misdescribed as browser/Thonny end-to-end.** It posts navigation and directly polls `/api/v1/editor/navigate/pending` using the same `TestClient`; this does not prove the browser dispatched through `analysisApi` or that Thonny consumed the command and moved to the exact cursor. Rename/relabel it as an API smoke, and provide separate real local backend + frontend browser + Thonny/plugin evidence for M4.
5. **Correct milestone/issue mapping and audit claims.** Architecture explanations and DOT endpoint export were reported under CS-021/CS-007, which is inaccurate. Keep the correction bounded to M4, correctly map CS-006/007/021/022, do not start M5/M6/M7, and do not claim Acceptance. Ensure report, tracker, and audit distinguish verified API smoke from pending real UI evidence.

## Next review gate

Keep M4 at **Changes required**. After the scoped corrections, rerun the affected frontend/backend/plugin tests and applicable quality gates, perform the actual Windows browser/Thonny workflow, record sanitized evidence, update tracker/audit, commit and push only the M4 correction pass, and stop for Codex review. No later milestone is authorized by this review.
