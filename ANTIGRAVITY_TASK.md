# Antigravity task: Milestone 4 corrections — Codex Review 1

Date: 2026-10-04. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M4_CODEX_REVIEW_1.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and the M4 scope in the prior task/issue definitions. The reviewed implementation commit is `41a7da613592813be014032f9a7226fd657007a8`. M4 is **Changes required**. Work only on the findings in the Codex review; preserve the accepted M1/M2 behavior and the user-approved frontend design. Do not begin M5, M6, M7, or M8.

## Required corrections

1. **CS-007 large-graph behavior:** Implement and regression-test the M4 criteria: bounded/off-main-thread layout/render behavior as appropriate to the existing architecture, clear total-versus-loaded counts and partial state, graph/table parity, and page-fetch failure/retry behavior. Keep implementation consistent with the existing renderer; do not claim an unimplemented layout engine. DOT endpoint export is CS-017 and outside this task: remove the M4 DOT API/toolbar wiring and related M4 claims, preserving the preexisting client-side DOT export behavior.
2. **CS-021 cancellation:** Add a controlled long-running job test that proves the frontend invokes cancellation, shows acknowledgement/progress truthfully, reaches and displays the terminal state, stops polling when terminal, and surfaces failure/timeout. Do not count `completed` as proof that cancellation succeeded. Keep M8-only storage fault/restart tests deferred.
3. **CS-022 accessibility/browser workflow:** Verify actual keyboard operation and focus, accessible status/error announcements, zoom/reflow, and reduced motion in the supplied frontend. Automated axe checks are supplementary. Record a real Windows browser run; do not map editor navigation to CS-022.
4. **CS-006 real browser/Thonny navigation:** Keep API smoke evidence labeled accurately. The current `M4_real_workflow_smoke.py` uses Starlette `TestClient` for both navigation dispatch and pending poll; it is not a browser/Thonny test. Add a real local backend + Vite browser + Thonny/plugin workflow, demonstrate exact selected file/line/column navigation and visible success/failure states, and record sanitized evidence without tokens. Keep editor navigation mapped to CS-006.
5. **Evidence and issue mapping:** Correct `docs/verification/M4.md`, `PROCESS_TRACKER.md`, and `docs/codestruct_audit.md` so they accurately map CS-006 (integration/navigation), CS-007 (large graph), CS-021 (cancellation integration), and CS-022 (accessibility). Separate API-level checks, automated tests, and observed browser/Thonny behavior. Keep M4 Changes required/Ready for review as appropriate; Antigravity must not declare Accepted. Fix the whitespace/EOF issues reported by Codex.

## Gates and stop rule

Run focused regressions, the full required frontend tests/lint/build, backend suite with coverage, plugin suite, Ruff check/format, and mypy. Run the real Windows backend/browser/Thonny workflow described above. Record exact commands/results and any genuinely blocked platform checks. Keep tests and temporary data isolated; preserve user data and do not weaken gates. Synchronize the external audit mirror only if accessible; report a blocker rather than silently claiming synchronization.

After every required M4 gate passes, commit and push only these M4 corrections, verify clean worktree and remote parity, update the tracker, and stop for Codex review. If a gate is blocked, record it and stop without claiming completion. Do not start a later milestone, rewrite history, force-push, tag, release, publish, or deploy.

## Launch prompt

Read `ANTIGRAVITY_TASK.md` and `docs/verification/M4_CODEX_REVIEW_1.md`. Make only the bounded M4 corrections for CS-006, CS-007, CS-021, and CS-022: implement/test large-graph behavior, prove real cancellation through terminal UI state, verify accessibility in an actual Windows browser, and verify exact browser-to-Thonny source navigation. Remove M4 DOT-export scope creep and correct the issue mapping/evidence. Run required focused/full gates, record the real backend/browser/Thonny workflow and sanitized results, update `PROCESS_TRACKER.md` and the audit, commit/push the M4 correction pass only after gates pass, then stop for Codex review. Do not begin Milestone 5.
