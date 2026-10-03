# Codex M1 review — correction pass 2

Date: 2026-09-27. Decision: **Changes required; M1 is not Accepted.** Most previously omitted behavior is now implemented. This review does not reopen fixed security probes or request unrelated feature work.

## Verified progress and checks

- Backend: 155 passed, 1 skipped (no coverage in this rerun).
- Plugin: 49 passed, 1 skipped.
- Submitted frontend suite: 89 passed; fresh coverage 72.91% statements, 65.13% branches, 74.37% functions, 75.61% lines, meeting configured thresholds. This run began before adding the new startup regression described below.
- Ruff lint and bare mypy: pass (50 source files).
- Plugin now uses poll generations, discards stale callbacks and checks original path components/resolved identity. Cursor-unavailable fallback and exception reason are truthful/safe. Frontend now clears project-associated credentials and shows request feedback. CI includes plugin tests/lint. Renderer and explanation method/path in brief corrected.
- Formatter command failed on four plugin fixture files after tests ran. These were not newly introduced product defects, but demonstrate a non-repeatable gate.
- Real desktop cursor observation remains explicitly pending. No Codex real GUI smoke is claimed here.

## Blocking new regression: IDE startup stalls under actual StrictMode entry

`frontend/src/main.jsx` mounts App in React StrictMode. App's load effect reads URL, starts the real useAnalysisJob/AnalysisPoller, then scrubs analysis_id. StrictMode cleanup invokes hook's poller.stop(). On effect replay App rereads the already scrubbed URL, finds no analysis_id and does not restart the stopped poll. Analysis never loads in the normal development entry point.

Added `frontend/src/App.strictReview.test.jsx` using the real hook and poller, mocking only the visual Graph renderer and API transport. Non-StrictMode case passes; StrictMode case fails with rendered `waiting` instead of `loaded`. Focused command: `npm.cmd test -- --reporter=dot src/App.strictReview.test.jsx`; result 1 passed / 1 failed. This is a meaningful regression for CS-002/004/006, not a mocked hook-only test. Keep it and fix startup. Capture immutable initial handoff data independently of URL scrubbing, make effect replay safely restart polling, preserve session clearing on new user work, and do not remove StrictMode or credential scrubbing to hide the failure. Cover plain analysis_id with no token too.

## Contract handoff still needs precise corrections (CS-004/023)

Brief now uses correct renderer/endpoint, but still invents details:

- `limit` has no default 500 in the route; omitted limit means full graph subject to byte cap. Settings default `max_graph_page_size=1000`, not 2000. Explicit first bounded page is the recommended client behavior.
- Timeout code is `ANALYSIS_TIMEOUT` in executor, not `ANALYSIS_TIMED_OUT`.
- Cursors use SHA256 of a fixed public context plus body, not HMAC signing. Describe as result/filter-bound integrity-checked opaque cursors; not authentication credentials. Do not implement a cryptographic redesign in this milestone merely to match the brief.
- Viewport virtualization and Dagre adapter are not current implemented behavior; mark planned capabilities. Do not promise queue position/depth/modularity values absent in real responses.
- Provide actual create request, error response, cancellation/retry/expiry examples and supported/unavailable features. Current brief is not yet a complete copy-pastable contract.

Permanent fixture tests validate flexible DTOs and manually composed fields, not actual canonical nested response generation. JobResponse.result and diagnostic items are dictionaries; validating only the outer DTO does not validate their contents. Graph page assertions merely enshrine the fixture's fields. Generate/compare through `graph_to_dict`, `slice_graph`, route/service DTO mapping or isolated TestClient actual responses, and test source/evidence normalization. This is the remaining original M1 contract requirement, not scope expansion.

## Repeatable formatter gate (CS-003)

After test runs, full format check reported four fixture files: project_a/main.py, module_z.py, real_script.py and selected_active.py. Plugin tests overwrite checked-in fixture source with unformatted strings. Fix tests to use temporary copies/roots or restore original fixture contents in teardown; do not just format fixtures before tests and call the gate green. Run format before AND after tests and confirm unrelated user fixtures are unchanged. No gate exclusions/weakening.

## Exit gate

Fix the actual StrictMode startup regression, truthful contract generation/brief, and test fixture mutation. Run targeted startup and complete required regression/coverage checks, retain real GUI limitation explicitly. Add `M1_CORRECTIONS_3.md`, then stop for Codex review. M2 remains not started.
