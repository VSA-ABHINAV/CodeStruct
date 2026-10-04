# Antigravity task: Milestone 4 — integrate the completed frontend

Date: 2026-10-04. Repository: `D:\REP\Codestruct\Codestruct`.

The user confirms the Lovable frontend was completed earlier and authorizes moving on to backend/frontend integration and remaining feature work. Treat the current frontend export in `frontend/` as the supplied design. **Do not redesign or replace its visual UI.** Milestones 1 and 2 are Codex-accepted. M3 was marked “design not started” in an older tracker snapshot; reconcile the tracker to say the user reports frontend design complete, with Codex visual review evidence not yet recorded. Do not claim CS-005 Accepted without evidence or silently reopen its design scope. Proceed with the explicit user-authorized M4 integration scope below.

Read `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, `docs/verification/M1_CODEX_REVIEW_8_ACCEPTED.md`, `docs/verification/M2_CODEX_REVIEW_4_ACCEPTED.md`, `LOVABLE_FRONTEND_BRIEF.md`, `docs/api/v1.md`, current architecture docs, and `CONTRIBUTING.md`. Inspect current source and Git state before edits. The audit's CS-006, CS-007, CS-021, and CS-022 entries are the M4 source of truth. Keep changes within those integration/verification concerns; do not begin M5 runtime, M6 semantic/RAG, M7 cache/Graphviz, or M8 release/evaluation work.

## Scope

1. **CS-006 — real frontend/backend integration:** Use one configured API base and consistent client/error handling for every backend request, including graph explanations. Make navigation outcomes visible and truthful; handle unavailable or stale IDE sessions, request failure, timeout/expiry, and successful acknowledgement. Preserve exact file/line/column navigation and avoid fabricated data. Keep cancellation, refresh/retrieval, loading, partial, cache-hit, expired, and error states consistent with the real API contract.
2. **CS-007 — usable large-graph behavior:** Verify and fix worker/off-main-thread layout where needed, render/layout caps, graph aggregation or progressive loading, total-vs-loaded counts, table parity, and page-fetch failure/retry behavior. Avoid duplicate Fit/zoom controls. Keep graph and table representations consistent with the same loaded data and clearly identify partial graph slices. Do not claim ELK or another layout engine unless the implementation actually uses it.
3. **CS-021 — M4 cancellation integration:** Connect the UI to actual cancellation acknowledgement and terminal job state. Verify cancellation while queued/running, timeout/error feedback, polling stop behavior, and result expiry using controlled fixtures or temporary test data. Defer storage fault matrix/restart stress owned by M8 unless needed to fix a directly encountered integration defect.
4. **CS-022 — M4 real-workflow accessibility:** Preserve the supplied design while fixing integration-level keyboard/focus, screen-reader labels/status announcements, zoom/reflow and reduced-motion issues found during the actual workflow. Run automated accessibility checks as supporting evidence, not as a replacement for keyboard and browser testing.

## Required workflow and preservation

- Keep M1/M2 behavior, API contracts, Thonny capability security, URL-token scrubbing, and source path/line/column semantics intact. Do not weaken tests, expose capabilities in logs, add fake success, or call a paid/remote provider.
- Use real backend responses for integration tests. Add focused regressions for each changed behavior. Keep test servers/data isolated and temporary; preserve user databases and project files.
- Run relevant focused backend/frontend/plugin tests, then the project-required frontend tests, lint, production build, backend suite with coverage, plugin suite, Ruff check/format, and mypy. Record exact commands, exit results, counts, and coverage; distinguish environmental blockers from product failures.
- Run the real local workflow on Windows: start the backend and frontend, connect Thonny, select/open an exact source location, verify visible success and failure paths, job cancellation and graph paging/partial state, keyboard traversal and responsive zoom/reflow. Capture concise sanitized evidence in `docs/verification/M4.md` (screenshots only if useful; never include session/capability tokens). Mocks/component tests alone do not satisfy this gate.
- Update `PROCESS_TRACKER.md` with the user-confirmed M3 design status and M4 results. Update `docs/codestruct_audit.md` only with evidenced status/details, preserve archived evidence, and synchronize the declared external audit mirror only if the environment/path is available; report if it is blocked. Antigravity must not mark any item or milestone Accepted; use Ready for Codex review.
- Follow `CONTRIBUTING.md`: after all M4 checks pass, commit and push only M4 changes before handoff. Do not include later milestones, rewrite history, force-push, tag, release, deploy, publish packages, or alter unrelated work. If a gate fails, record it, make bounded corrections, and commit verified correction passes separately. Leave a clean tree and report commit SHA(s) and remote parity.

## Stop condition

Complete only M4. Update the process tracker and write the verification report, set M4 to Ready for Codex review, commit/push this bounded phase after gates pass, and stop. Do not start M5 or any later milestone. Codex will independently review source, tests, real workflow evidence, documentation and commits before assigning Accepted.

## Launch prompt

Read `ANTIGRAVITY_TASK.md` and implement only Milestone 4 integration for CS-006, CS-007, CS-021, and CS-022. The user confirms the Lovable frontend is already complete: preserve its visual design and connect it to real backend behavior. Update `PROCESS_TRACKER.md`, record focused and full gate results plus the real Windows backend/browser/Thonny workflow in `docs/verification/M4.md`, update only evidenced audit statuses, commit and push the bounded M4 changes after all gates pass, verify a clean tree and remote parity, then stop for Codex review. Do not begin Milestone 5.
