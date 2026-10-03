# Antigravity task — Milestone 1 correction pass

## Active task — third Codex review (2026-09-27)

Read `docs/verification/M1_CODEX_REVIEW_3.md` first. Most earlier corrections are now implemented; do not redo fixed backend security, plugin poll generations, session clearing or CI commands. This section overrides historical correction lists below where they describe already-fixed code.

Finish three concrete remaining items within M1:

1. Fix Thonny/IDE URL startup under actual React StrictMode. Codex added `frontend/src/App.strictReview.test.jsx`; real hook/poller loads without StrictMode and stalls under StrictMode because effect cleanup stops polling after URL scrub. Keep this regression, preserve StrictMode and immediate credential scrub. Capture initial analysis handoff independently, safely replay/start polling, and test plain analysis_id plus session_token and subsequent project changes.
2. Make Lovable handoff exact. Correct limit omission/default server cap (1000), ANALYSIS_TIMEOUT, cursor integrity semantics (not HMAC), and planned-vs-current virtualization/Dagre/queue/metric claims. Include real submit/cancel/error/retry/expiry examples and unavailable later capabilities. Strengthen fixture tests through real serializer/pagination/route/service responses rather than generic dictionary DTO acceptance/manual expected fields. No crypto redesign, renderer redesign or M2 implementation.
3. Stop plugin tests modifying checked-in fixture contents. Use temporary copies/roots or restore originals. Run full formatter check both before and after tests; all must pass and user source unchanged. Do not merely format fixtures once or exclude them from gates.

Run targeted startup test, full backend/plugin/frontend suites and required lint/mypy/build/coverage gates from original scope. Evidence must distinguish the submitted 89-test baseline from newly added StrictMode regression. Keep desktop cursor observation pending unless genuinely observed. Add `docs/verification/M1_CORRECTIONS_3.md`, update tracker/audit accurately, and stop for Codex review. Do not begin M2.

## Current pass: finish omitted corrections (Codex second review)

Read `docs/verification/M1_CODEX_REVIEW_2.md` first. Backend uniqueness/origin/expiry/junction probe failures now reject correctly, and graph coordinates/evidence normalize correctly. Preserve those improvements. M1 is still not Accepted.

**Implement remaining work rather than repeating the completed probes:**

- Use plugin generation/resolved-identity state in actual poll switching and execution; declarations alone do not fix behavior. Add A->B/stale callback/junction-open regressions.
- Complete R4 frontend session/analysis association, URL credential scrub, clear on project change and visible error/outcome behavior. Add tests and run coverage.
- Correct the Lovable brief now, including renderer, endpoint/method, real states and every original handoff requirement. These are explicitly M1 scope and may not be deferred to M3. Generate/validate actual fixtures via permanent contract tests.
- Finish plugin cursor delivery/failure and safe reason codes; no raw exception/path upload and no delivered claim for open-only fallback.
- Add plugin tests/lint to CI and developer instructions. Format the six named test files only as formatter-only changes; keep gates intact. Demonstrate authoritative/parity mypy config. Keep real GUI gate pending unless actually observed.

Map every item above to implementation, regression tests and exact evidence in `M1_CORRECTIONS_2.md` (or append a clearly dated second-pass section). Original requirements below still apply; do not claim all R1–R6 addressed if a requested item remains. Stop for Codex review; do not begin M2.

Status: **Changes required after Codex review. M1 is not Accepted. Do not begin M2.**
Repo: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M1_CODEX_REVIEW.md` in full. Original scope and all required checks remain applicable in `docs/verification/M1_original_task.md`. Read technology summary, audit, tracker and prior `docs/verification/M1.md`. Fix R1–R6 within CS-001–004/023 and contract portion CS-026. Preserve all user/staged/untracked work. No reset, clean, commits, deployment, feature expansion or frontend redesign. Lovable creates the later frontend.

## Required correction work

1. **R1 — Path identity:** Backend/plugin must reject replaced registered paths and ancestor junction/reparse/symlink escapes before and after resolution at registration, queue, delivery and IDE open. Compare resolved scope with registered identity; checking links only after resolve fails. Test a real Windows junction swap in task-owned temporary roots. Define safe ordinary content-edit behavior without authorizing another path.
2. **R2 — Sessions and poll lifecycle:** Independent IDE registrations of the same file must not share credentials. Define bounded session storage, explicit same-session reuse/revocation. Switch polling A->B with generations and discard stale callbacks/results; no duplicate/leaked threads. Test actual lifecycle without restarting plugin, not merely direct execute calls with pre-set globals.
3. **R3 — Real contracts:** Generate fixtures from actual serializer/API responses and validate them in permanent tests, including source coordinates, evidence, paging, jobs/results, errors, cancel/cache/expiry, exports and editor outcomes. Correct explanation method/path and actual JobState values. Current renderer is React Flow; Cytoscape is an alternative. Remove unmeasured performance promises. Complete LOVABLE_FRONTEND_BRIEF.md with original task requirements: copy-pastable design brief, responsive accessible table/keyboard/focus/reduced motion, all actual request/response contracts, local export/proxy deployment, hosted preview fixtures explicitly labeled, no new backend/remote source upload/fabricated live results, unavailable later-feature labels. Do not implement M2 logic to make fixtures convenient.
4. **R4 — Frontend session binding:** Associate captured editor token with its analysis; safely scrub URL after capture while retaining analysis handoff. Clear/rebind on different project/analysis; no project B navigation through A's credential when names match. Disable unavailable navigation and display safe queued/failure feedback. Use shared API client and regression tests. Minimal behavioral corrections only; no visual redesign.
5. **R5 — Origin/outcomes:** Enforce explicit trusted local browser-origin policy compatible with local proxy/IDE clients; test hostile Origin through actual boundary. IP/CORS alone is insufficient. Expired/wrong/replaced commands cannot acknowledge delivered. Cursor-unavailable fallback cannot claim exact navigation success. Use safe reason codes, not raw exceptions/private paths; provide bounded validated outcome visibility to frontend as needed.
6. **R6 — Checks/evidence:** Include plugin tests/lint in CI and developer instructions. Consolidate mypy config or enforce parity. Full format gate fails on 13 files; remediate only as separately recorded formatter-only changes with no semantics or weakened checks. Run frontend coverage for changed logic. Link actual artifacts and runnable safe smoke script. Real browser/backend/Thonny cursor evidence remains pending unless genuinely observed; mock/widget method calls cannot be labeled real IDE success.

## Verification and deliverables

Add regressions for every reproduced failure: two same-file sessions, A->B poll switch/stale callbacks, ancestor junction swap at queue/delivery/open, hostile Origin, expired acknowledgements, cursor-unavailable fallback, URL/session clear, canonical fixture normalization preserving coordinates and evidence. Use isolated temporary databases/roots, never execute analyzed code during static analysis.

Run every original M1 check, including backend/plugin suites, coverage gates, full Ruff format/lint, default mypy, frontend tests/coverage/lint/build. Codex baseline: 149 backend pass/1 skip; 81 navigation/editor/plugin pass; 73 frontend pass; lint/mypy pass; full format fails. Passing existing tests does not fix uncovered defects. Run `docs/verification/M1_review_probes.py` against corrected behavior or port its cases into regression tests. Script retains task-owned `.codestruct/m1-review-*` fixtures; do not remove user directories.

Perform focused real local backend/browser/Thonny smoke for two roots with identical basenames, independent same-file sessions, session switch and exact cursor. The application has no game main scene; this is its real workflow. Preserve evidence if interrupted. If GUI control is unavailable, complete independent work, explicitly mark manual gate pending and state exact limitation.

Deliver corrected code/tests/brief/contracts/CI docs and `docs/verification/M1_CORRECTIONS.md` mapping R1–R6 to changes, exact test outputs, real smoke evidence and limitations. Preserve original report and review. Update PROCESS_TRACKER.md and audit to Ready for Codex review only when corrections are ready, keeping pending gates visible. **Stop; do not mark Accepted or begin M2.**

## Launch line

Read ANTIGRAVITY_TASK.md and resolve the Milestone 1 Codex review findings within its scope. Update PROCESS_TRACKER.md, run the required tests and real backend/browser/Thonny workflow, record correction evidence, then stop for Codex review. Do not begin Milestone 2.
