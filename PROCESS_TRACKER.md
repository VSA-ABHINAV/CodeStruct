
Updated: 2026-10-09. Audit: `docs/codestruct_audit.md`. Current task: `ANTIGRAVITY_TASK.md`.

Only Codex assigns Accepted after review. Antigravity records implementation and verification, then sets Ready for Codex review. Preserve earlier evidence and user files. Frontend visual creation belongs to Lovable.

| Milestone | Issues | Owner | Status | Evidence | Codex review |
|---|---|---|---|---|---|
| M1 | CS-001–004, CS-023, contract portion CS-026 | Antigravity | Accepted | `docs/verification/M1_CODEX_REVIEW_8_ACCEPTED.md` | Live Thonny cursor and selected-file isolation verified; stale STOP race fixed; contract and focused gates pass |
| M2 | CS-008–011, CS-018–019 | Antigravity | Accepted | `docs/verification/M2_CODEX_REVIEW_4_ACCEPTED.md` | Shared canonical community partition, exhaustive 4/5-node parity, full backend/plugin/static gates, real API/cache smoke and audit mirror independently verified |
| M3 | CS-005; design CS-007/022/026 | Lovable + user | User reports complete; Codex visual review pending | `LOVABLE_FRONTEND_BRIEF.md`, `docs/frontend-redesign-functional-map.md` | User confirms frontend design complete; Codex visual review evidence pending |
| M4 | CS-006-CS-007, integration CS-021-CS-022 | Antigravity | Accepted | `docs/verification/M4_CODEX_REVIEW_13_ACCEPTED.md` | Independent backend/plugin/frontend/static gates and live browser/backend/Thonny workflow pass; live cursor 4.4. Manual screen-reader observation remains pending under CS-022. |
| M5 | CS-012-CS-014 | Antigravity | Ready for Codex review (Pass 1) | `docs/verification/M5.md` | Explicit runtime execution, attribution/disambiguation with ambiguity retained, recursion self-loops, repeated run metric re-enrichment |
| M6 | CS-016 | Antigravity | Not started | — | Pending |
| M7 | CS-015, CS-017 | Antigravity | Not started | — | Pending |
| M8 | CS-020–024 | Antigravity + user | Not started | — | Pending |
| Future | CS-025 | User decides | Deferred | — | Not in core scope |

## Current milestone issue tracker

Milestone 5 Antigravity Pass 1, 2026-10-09: **Ready for Codex Review (Pass 1)**. Implemented issues CS-012, CS-013, and CS-014:
- **CS-012 (Explicit Opt-In Runtime Analysis):** Added `POST /api/v1/analyses/{analysis_id}/runtime` and `GET /api/v1/analyses/{analysis_id}/runtime` endpoints; enforced authorized root path containment and escaping path rejection (`RUNTIME_PATH_OUTSIDE_PROJECT`); preserved strict non-execution for static analysis.
- **CS-013 (Attribution, Disambiguation & Ambiguity Retention):** Implemented line-span matching with ambiguity retention (`ResolutionStatus.AMBIGUOUS`, `Confidence.LOW`, `candidate_ids`); captured multithreading profiling (`sys.setprofile` + `threading.setprofile`) with clean hook restoration; handled generator/coroutine suspension without false exception flags; added recursive self-loop edge support (`recursive: "true"`).
- **CS-014 (Repeat Runs & Derived Metric Re-enrichment):** Implemented cumulative `runtime_calls` on edges and node-level stats (`runtime_invocations`, `runtime_calls_out`, `runtime_exception`); updated `enrich_nodes_with_metrics` to recompute and overwrite stale graph metrics over combined edges without losing custom node attributes.
- **Verification & Gates:** All quality gates pass (196 backend pytest / 84.79% coverage, 53 plugin pytest, 104 frontend vitest, ruff check/format clean, mypy clean, clean frontend build, deterministic M5 runner exit 0). Evidence recorded in `docs/verification/M5.md`. Do not begin M6.

Milestone 4 Codex Review 13, 2026-10-09: **Accepted.** Independent backend tests pass at 85.34% coverage, plugin tests pass, frontend tests/lint/build pass, Ruff and mypy pass, and the real Windows backend/browser/Thonny smoke completed with live editor cursor `4.4`. Review evidence is in `docs/verification/M4_CODEX_REVIEW_13_ACCEPTED.md`. Manual screen-reader observation remains pending under CS-022; M5 is the next authorized implementation milestone.

Milestone 4 Codex Review 12 Corrections Pass (2026-10-09): **Ready for Codex Review (Pass 13)**. Addressed all findings from `docs/verification/M4_CODEX_REVIEW_12.md`:
- Finding 1 (Thonny Environment Compatibility & Workbench Startup): Repaired `D:\REP\thonny\venv` by providing `minny.target` module stub in site-packages and runtime dynamic fallback in smoke harness. Proved Thonny workbench startup, CodeStruct plugin loading, and live Tk text widget cursor navigation (`4.4`) across repeated clean live workflow smoke runs.
- Finding 2 (Document & Handoff Reconciliation): Reconciled `ANTIGRAVITY_TASK.md`, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, `docs/codestruct_audit.md`, and external audit mirror. All quality gates pass. Do not begin M5.

Milestone 4 Codex Review 11 Corrections Pass (2026-10-09): **Pass 12 baseline**. Addressed all findings from `docs/verification/M4_CODEX_REVIEW_11.md`:
- Finding 1: Refactored Win32 Toolhelp functions (`get_windows_process_tree_pids`, `get_all_active_pids_win32`) to fail closed on `CreateToolhelp32Snapshot` failure, `Process32FirstW` failure, or unexpected `Process32NextW` iteration errors (`GetLastError() != ERROR_NO_MORE_FILES`). Added automated injected failure-path regressions for all three error modes.
- Finding 2: Made Windows junction and reparse verification mandatory in step 0 regressions. Asserts inside-root junction creation (`mklink /J`), detection via `is_reparse_or_link()`, and scanner fail-closed rejection. Added outside-root junction and canonical containment rejection test (`entry.resolve().is_relative_to(target.resolve())`).
- Finding 3: Reconciled `ANTIGRAVITY_TASK.md`, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, `docs/codestruct_audit.md`, and external mirror. All gates pass. Do not begin M5.

| ID | Status | Changes / evidence | Remaining work |
|---|---|---|---|
| CS-012 | Ready for Codex review (Pass 1) | Explicit bounded runtime analysis endpoints (`POST /api/v1/analyses/{id}/runtime`, `GET /api/v1/analyses/{id}/runtime`) implemented; static non-execution preserved; authorized containment enforced. | None for M5 (Codex review) |
| CS-013 | Ready for Codex review (Pass 1) | Line-span matching with ambiguity retention (`ResolutionStatus.AMBIGUOUS`, `Confidence.LOW`, `candidate_ids`); multithreading profile capture; generator suspension exception exclusion; recursive self-loops. | None for M5 (Codex review) |
| CS-014 | Ready for Codex review (Pass 1) | Repeated-run merging with cumulative call counts, node-level stats (`runtime_invocations`, `runtime_calls_out`, `runtime_exception`), and re-enrichment overwriting stale graph metrics. | None for M5 (Codex review) |
| CS-006 | Accepted (M4) | Thonny compatibility harness, actual CodeStruct plugin analysis, browser-to-editor dispatch, and live Tk cursor `4.4` independently verified; Toolhelp and junction regressions pass. | None for M4 |
| CS-007 | Accepted (M4 portion) | Pure `layoutGraph()` + exported `measureGraphLayout()` benchmark; live smoke confirms graph/table parity. | None for M4; future issue work remains separately tracked |
| CS-021 | Accepted (M4 portion) | Sanitized diagnostics, exact `cancellation_requested` acknowledgement, terminal `cancelled` state, and zero post-terminal polls verified. | None for M4 |
| CS-022 | Accepted (M4 automated portion) | Reduced-motion computed durations, responsive reflow, ARIA regions, and keyboard controls verified. | Manual screen-reader observation remains pending |
| CS-008 | Accepted (M2) | `metrics_computed: bool` explicitly serialized on `GraphMetadata` and verified in smoke for false, true, and warm cache hit. | None |
| CS-009 | Accepted (M2) | Transient NetworkX adapter, optional dependency, deterministic fallback, and unified canonical community partitioning verified across exhaustive 4/5-node parity probe. | None |
| CS-010 | Accepted (M2) | Resolved-edge filtering, iterative SCC, component separation, module metrics, and unified canonical community partitioning independently verified. | None |
| CS-011 | Accepted (M2) | Canonical location fidelity (`service.py:3-7`) and bounded safe evidence references verified in real smoke. | None |
| CS-018 | Accepted (M2) | Stub-only and external type-stub scope documented and verified. | None |
| CS-019 | Accepted (M2) | Static resolution precedence and unsupported reflection semantics documented and verified. | None |
| CS-001 | Accepted (M1) | R1: `_has_link_component` before resolve + identity compare on queue/poll/resolve. R2: unique tokens per registration (`cap_` + `secrets.token_urlsafe(24)`), bounded storage (max 100), eviction. R5: origin enforcement (403 for untrusted), expiry on ack, correct status codes. 20 navigate tests pass. | None (Codex review) |
| CS-002 | Accepted (M1) | Generation-scoped STOP messages (`("STOP", generation)`), generation-matching drain validation in `_poll_navigate`, queue flushing on session start (`_flush_nav_queue`), and live Tk text widget index `4.4` verified. Validated via `M1_review7_queue_probe.py` (True) and 53 plugin unit tests. | None (Codex review) |
| CS-003 | Accepted (M1) | R6: Format-only remediation on test files and plugin fixtures (87/87 files pass `ruff format --check` before and after test runs). Plugin test/lint in CI/docs. Mypy 50/50 clean. All gates pass. | None (Codex review) |
| CS-004 | Accepted (M1) | R3/R5: `docs/frontend-contract/*.json` and `LOVABLE_FRONTEND_BRIEF.md` fully corrected with canonical 15-key summary, canonical `GraphDiagnostic` location and shape, documented 4 MiB default cap, generated Section 5.6 paged example with endpoint nodes and valid cursor, and nullable diagnostic locations. | None (Codex review) |
| CS-023 | Accepted (M1) | Real browser + backend + Thonny workflow verified: URL parameter scrubbing on mount, interactive method pill selection, "Open in editor" dispatch, live Tk cursor move to `4.4`, 403 API failure feedback, and clean listener shutdown. Complete evidence in `docs/verification/M1_REAL_WORKFLOW.md`. | None (Codex review) |
| CS-026 | Accepted (M1 contract portion) | Lovable brief and frontend contract reviewed against backend; renderer/design decision remains M3. | M3 design work remains |

## Run log
### 2026-10-09 - Codex Milestone 4 Review 13

- Accepted M4 after independent backend coverage, plugin, frontend, static-analysis, and real Windows backend/browser/Thonny workflow verification.
- Recorded that manual screen-reader observation remains pending under CS-022 and remote Git parity could not be independently verified because GitHub was unreachable.
- Prepared the bounded M5 handoff for CS-012-CS-014. M5 implementation has not started.

### Antigravity M4 Pass 13 (Codex Review 12)

- Addressed all findings from `docs/verification/M4_CODEX_REVIEW_12.md`:
  - **Finding 1 (Thonny Environment & Workbench Compatibility):** Repaired `D:\REP\thonny\venv` by providing `minny.target` module stub in site-packages and added defensive runtime fallback in `run_thonny.py` harness template. Verified that Thonny workbench initializes, loads `thonnycontrib.codestruct`, starts analysis, dispatches navigation from CDP browser click, and updates live Tk insert cursor to line `4.4` (`def calculate_root2(self):`).
  - **Finding 2 (Document & Handoff Reconciliation):** Updated `ANTIGRAVITY_TASK.md`, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Verified all quality and test gates:
  - Frontend Vitest: 104 passed across 10 test files (`npm.cmd --prefix frontend test -- --run`).
  - Frontend ESLint: 0 errors, 0 warnings (`npm.cmd --prefix frontend run lint`).
  - Frontend Production Build: `npm.cmd --prefix frontend run build` -> built in 236ms.
  - Backend Pytest: 189 passed, 1 skipped, 1 warning (85.34% coverage >= 84%).
  - Thonny Plugin Pytest: 53 passed, 1 skipped (`.venv\Scripts\python.exe -m pytest thonny-plugin/tests --no-cov`).
  - Ruff Check & Format: 135 files clean (`ruff check`, `ruff format --check`).
  - Mypy: 50 source files clean (`mypy --config-file pyproject.toml`).
  - Git Diff Check: clean (0 whitespace errors).
  - Real Windows Smoke Test: 2 consecutive runs passed with exit 0 (nonce `0abb1032` and `d3b64b6e`).
- Marked Milestone 4 as **Ready for Codex review (Pass 13)**. Milestone 5 has not been started.

### 2026-10-09 — Antigravity Milestone 4 Corrections Pass 12 (Codex Review 11)

- Addressed all 3 findings from `docs/verification/M4_CODEX_REVIEW_11.md`:
  - **Finding 1 (Fail-Closed Win32 Toolhelp API & Failure Injections):** Refactored `get_windows_process_tree_pids()` and `get_all_active_pids_win32()` in `M4_real_workflow_smoke.py` to propagate sanitized `RuntimeError` on snapshot creation, `Process32FirstW`, and unexpected `Process32NextW` iteration errors (`GetLastError() != ERROR_NO_MORE_FILES`). Added automated step 0 mock injection tests for all three error conditions.
  - **Finding 2 (Mandatory Windows Junction & Containment Regressions):** Made Windows junction regression mandatory in step 0, asserting creation (`mklink /J`), detection via `is_reparse_or_link()`, and scanner fail-closed rejection. Added outside-root junction and canonical containment verification asserting `resolve(strict=True)` is not relative to the scan root.
  - **Finding 3 (Handoff & Audit Reconciliation):** Reconciled `ANTIGRAVITY_TASK.md`, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Verified all quality and test gates:
  - Frontend Vitest: 104 passed across 10 test files (`npm.cmd test --prefix frontend -- --run`).
  - Frontend ESLint: 0 errors, 0 warnings (`npm.cmd run lint --prefix frontend`).
  - Frontend Production Build: `npm.cmd run build --prefix frontend` -> built in 251ms.
  - Backend Pytest: 189 passed, 1 skipped, 1 warning (85.34% coverage >= 84%).
  - Thonny Plugin Pytest: 53 passed, 1 skipped (`.venv\Scripts\pytest.exe -o addopts="" thonny-plugin/tests`).
  - Ruff Check & Format: 209 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 48 source files clean (`mypy backend/src`).
  - Git Diff Check: clean (0 whitespace errors).
  - Real Windows Smoke Test: 2 consecutive runs passed with exit 0 (nonce `63110c21` and `959d27a3`).
- Marked Milestone 4 as **Ready for Codex review (Pass 12)**. Milestone 5 has not been started.

### 2026-10-08 — Antigravity Milestone 4 Corrections Pass 11 (Codex Review 10)

- Addressed all 4 findings from `docs/verification/M4_CODEX_REVIEW_10.md`:
  - **Finding 1 (Win32 Process-Tree Descendant Quiescence):** Implemented Win32 Toolhelp snapshot API functions (`get_windows_process_tree_pids`, `get_all_active_pids_win32`) in `M4_real_workflow_smoke.py`. Updated `stop_process_tree_and_wait()` to discover descendant PIDs before killing root, execute `taskkill /F /T`, verify root exit, and loop until all descendant PIDs have exited (with targeted PID killing for any lingering descendants). Extended step 0 regression to assert child PID is dead.
  - **Finding 2 (Windows Junction/Reparse Detection & Canonical Containment):** Implemented `is_reparse_or_link()` detecting symlinks, junctions, and `FILE_ATTRIBUTE_REPARSE_POINT` (0x400) plus canonical containment check (`entry.resolve().is_relative_to(target.resolve())`) in `scan_for_secret_tokens()`. Added automated step 0 regression verifying fail-closed rejection of real Windows directory junctions (`mklink /J`).
  - **Finding 3 (Sanitized Cancellation Failure Diagnostics):** Sanitized diagnostic assertions in `run_ui_cancellation()` to report schema-supported `progress.phase` and `progress.message_code` without claiming non-existent top-level `error_code`.
  - **Finding 4 (Handoff & Audit Reconciliation):** Reconciled `ANTIGRAVITY_TASK.md`, `PROCESS_TRACKER.md`, `docs/verification/M4.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Verified all quality and test gates:
  - Frontend Vitest: 104 passed across 10 test files (`npm.cmd test --prefix frontend -- --run`).
  - Frontend ESLint: 0 errors, 0 warnings (`npm.cmd run lint --prefix frontend`).
  - Frontend Production Build: `npm.cmd run build --prefix frontend` -> built in 464ms.
  - Backend Pytest: 189 passed, 1 skipped, 1 warning (85.34% coverage >= 84%).
  - Thonny Plugin Pytest: 53 passed, 1 skipped (`.venv\Scripts\pytest.exe -o addopts="" thonny-plugin/tests`).
  - Ruff Check & Format: 208 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 48 source files clean (`mypy backend/src`).
  - Git Diff Check: clean (0 whitespace errors).
  - Real Windows Smoke Test: 2 consecutive runs passed with exit 0 (nonce `850996b9` and `c56e55ab`).
- Marked Milestone 4 as **Ready for Codex review (Pass 11)**. Milestone 5 has not been started.

### 2026-10-08 — Antigravity Milestone 4 Corrections Pass 10 (Codex Review 9)

- Addressed all 4 findings from `docs/verification/M4_CODEX_REVIEW_9.md`:
  - **Finding 1 (Deterministic Cancellation & Diagnosability):** Fixed race condition in `executor.py` by ensuring jobs transition to `JobState.CANCELLED` at every supervisory/post-loop stage. Exposed sanitized `error_code`, `message_code`, and `progress` fields on assertion failure in `M4_real_workflow_smoke.py`. Increased cancellable project size to 80 files / 20 classes. Demonstrated repeatability across 3 consecutive smoke runs.
  - **Finding 2 (Fail-Closed Process Tree Quiescence):** Refactored `stop_process_tree_and_wait()` to validate `taskkill` exit codes (0/128), wait for process exit, and verify PID is removed from `tasklist`. Added automated process-tree teardown regression test.
  - **Finding 3 (Fail-Closed Secret Scanner):** Refactored `scan_for_secret_tokens()` to explicitly inspect every entry, failing closed on symlinks/reparse points or unsupported special entries. Added automated scanner regression tests.
  - **Finding 4 (Handoff & Audit Reconciliation):** Reconciled `ANTIGRAVITY_TASK.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Verified all quality and test gates:
  - Frontend Vitest: 104 passed across 10 test files (`npm.cmd test --prefix frontend -- --run`).
  - Frontend ESLint: 0 errors, 0 warnings (`npm.cmd run lint --prefix frontend`).
  - Frontend Production Build: `npm.cmd run build --prefix frontend` -> built in 300ms.
  - Backend Pytest: 189 passed, 1 skipped, 1 warning (85.34% coverage >= 84%).
  - Thonny Plugin Pytest: 53 passed, 1 skipped (`.venv\Scripts\pytest.exe -o addopts="" thonny-plugin/tests`).
  - Ruff Check & Format: 207 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 48 source files clean (`mypy backend/src`).
  - Git Diff Check: clean (0 whitespace errors).
  - Real Windows Smoke Test: 3 consecutive runs passed with exit 0.
- Marked Milestone 4 as **Ready for Codex review (Pass 10)**. Milestone 5 has not been started.

### 2026-10-07 — Antigravity Milestone 4 Corrections Pass 8 (Codex Review 7)

- Addressed both findings from `docs/verification/M4_CODEX_REVIEW_7.md`:
  - **Finding 1 (Single-Pass Layout Timing):** Removed duplicate `layoutGraph` execution from `ArchitectureExplorer.jsx` (`useEffect` hook removed). Single-pass layout duration and metadata are measured directly inside `layoutGraph` in `graphLayout.js`. `npm.cmd run lint --prefix frontend` passes with 0 errors and 0 warnings.
  - **Finding 2 (Fail-Closed Secret Scan & Quiescence):** Refactored `scan_for_secret_tokens()` to fail closed (asserts every file in target dir can be read, asserts `scanned_file_count > 0`). Added `stop_process_and_wait()` helper to ensure all subprocesses (Chrome, Thonny, frontend, backend) and child processes are fully terminated and file handles released before disk scanning.
- Verified all quality and test gates:
  - Frontend Vitest: 103 passed across 10 test files (`npm.cmd test --prefix frontend -- --run`).
  - Frontend ESLint: 0 errors, 0 warnings (`npm.cmd run lint --prefix frontend`).
  - Frontend Production Build: `npm.cmd run build --prefix frontend` -> built in 393ms.
  - Backend Pytest: 189 passed, 1 skipped, 1 warning (85.49% coverage >= 84%).
  - Thonny Plugin Pytest: 53 passed, 1 skipped (`.venv\Scripts\pytest.exe -o addopts="" thonny-plugin/tests`).
  - Ruff Check & Format: 205 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 48 source files clean (`mypy backend/src`).
  - Smoke Script Syntax: `python -m py_compile docs/verification/M4_real_workflow_smoke.py` passed.
  - Git Diff Check: clean.
  - Real Windows Smoke Test: `.venv\Scripts\python.exe docs/verification/M4_real_workflow_smoke.py` passed with exit code 0.
- Updated `docs/verification/M4.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Marked Milestone 4 as **Changes required (Ready for Codex Review 8)**. Milestone 5 has not been started.

### 2026-10-06 — Antigravity Milestone 4 Corrections Pass 7 (Codex Review 6)

- Addressed all 6 findings from `docs/verification/M4_CODEX_REVIEW_6.md`:
  - **Finding 1 (Frontend Lint Purity):** Moved layout timing out of `useMemo` in `ArchitectureExplorer.jsx` into pure `useMemo` + `useEffect`. `npm.cmd run lint --prefix frontend` passes with 0 errors and 0 warnings.
  - **Finding 2 (CDP Document-Level Poll Logging):** Injected `Page.addScriptToEvaluateOnNewDocument` with `window.__poll_request_log` and `window.__delete_response_log` before navigation. Verified logger exists and observed >= 1 status polls prior to cancellation.
  - **Finding 3 (Exact `cancellation_requested` Ack):** Sized cancellation fixture to 60 files. Captured live DELETE response, asserted status 202 and exact `cancellation_requested` acknowledgement, verified terminal `cancelled` state, and proved zero subsequent status polls.
  - **Finding 4 (Real UI Paging Failure & Retry):** Intercepted paged slice (`limit=100`, 126 nodes), triggered UI "Load more graph data" button during simulated network failure, verified visible error banner `.graph-status--failed`, verified strict retention of loaded node/edge identities (126 nodes), clicked UI retry button, verified error banner cleared and full 186 nodes / 247 edges merged.
  - **Finding 5 (Isolated Chrome Profile & Secret Scanning):** Launched Chrome with `--incognito`, dedicated `--user-data-dir` inside temp dir, `--no-first-run`, `--no-default-browser-check`. Terminated processes before scanning disk to release file locks. Verified 0 capability tokens persisted or output.
  - **Finding 6 (Failure-Path Redaction Regression):** Tested `format_thonny_failure_diagnostic()` with synthetic token-bearing stderr, asserting zero token leakage and complete redaction.
  - **Finding 7 (Truthful Status & Evidence):** Reconciled tracker, audit, and verification report truthfully.
- Verified all quality and test gates:
  - Frontend Vitest: 103 passed across 10 test files (`npm.cmd test --prefix frontend -- --run`).
  - Frontend ESLint: 0 errors, 0 warnings (`npm.cmd run lint --prefix frontend`).
  - Frontend Build: `npm.cmd run build --prefix frontend` -> built in 412ms.
  - Backend Pytest: 189 passed, 1 skipped, 1 warning (85.49% coverage >= 84%).
  - Thonny Plugin Pytest: 53 passed, 1 skipped (`.venv\Scripts\pytest.exe -o addopts="" thonny-plugin/tests`).
  - Ruff Check & Format: 204 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 48 source files clean (`mypy backend/src`).
  - Smoke Script Syntax: `python -m py_compile docs/verification/M4_real_workflow_smoke.py` passed.
  - Git Diff Check: clean.
  - Real Windows Smoke Test: `.venv\Scripts\python.exe docs/verification/M4_real_workflow_smoke.py` passed with exit code 0.
- Updated `docs/verification/M4.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Marked Milestone 4 as **Changes required (Ready for Codex Review 7)**. Milestone 5 has not been started.

### 2026-10-06 — Antigravity Milestone 4 Corrections Pass 6 (Codex Review 5)

- Addressed all findings from `docs/verification/M4_CODEX_REVIEW_5.md`:
  - **P0 Credential Redaction & Failure Path Redaction:** Removed raw URL/token stderr printing in Thonny fixture; wrapped stderr streaming and timeout diagnostics in `redact_secrets()`; added failure-path unit test asserting 100% token redaction on synthetic token leakage (`cap_...`).
  - **Backend Identity Verification:** Generated unique `run_nonce` in smoke harness and validated backend identity via `GET /api/v1/projects` matching `smoke1_{nonce}`, `smoke2_{nonce}`, `dense_{nonce}`, and `cancel_proj_{nonce}`.
  - **In-App `layoutGraph` Benchmark:** Instrumented in-app `layoutGraph` execution time in `ArchitectureExplorer.jsx`; verified bounded overview mode on dense graph (64 nodes < 80 threshold, overview layout 0.2ms) and full in-app `layoutGraph` execution benchmark (0.5ms < 500ms bound).
  - **Exact Node & Edge Identity Parity:** Verified exact 100% identity parity between canonical graph slice and `AccessibleGraphTable` for BOTH 186 nodes and 247 edges (`node_identity_parity: true`, `edge_identity_parity: true`).
  - **Paging Failure & Retry Data Retention:** Injected synthetic network failure on page fetch (`PAGE_FETCH_ERROR`), verified error display, verified all 433 previously loaded items are retained during error state, and verified recovery upon retry.
  - **Full Cancellation Lifecycle & Cessation Proof:** Selected distinct uncached project, clicked UI Cancel button, verified disabled "Stopping…" state, observed explicit API `cancellation_requested` acknowledgement, terminal `cancelled` state, live ARIA announcement, terminal banner, and proved zero status poll requests over 2.5s post-terminal (`zero_polls_after_terminal: true`).
- Verified all quality and test gates:
  - Frontend Vitest suite: 103 passed across 10 test files (`npm --prefix frontend test -- --run`) with 0 warnings.
  - Frontend ESLint: `npm --prefix frontend run lint` -> 0 errors, 0 warnings.
  - Frontend production build: `npm --prefix frontend run build` -> `✓ built in 625ms`.
  - Backend pytest suite: 189 passed, 1 skipped, 1 warning (`pytest tests --cov=backend --cov-report=term-missing --cov-fail-under=84` -> 85.49% coverage).
  - Thonny plugin pytest: 53 passed, 1 skipped (`pytest thonny-plugin -o addopts=""`).
  - Ruff check & format: 203 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 50 source files clean (`mypy`).
  - Real Windows Workflow Smoke Test: `docs/verification/M4_real_workflow_smoke.py` passed exit code 0.
- Updated `docs/verification/M4.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Marked Milestone 4 as **Ready for Codex review**. Milestone 5 has not been started.

### 2026-10-04 — Antigravity Milestone 4 Corrections Pass 4 (Codex Review 4)

- Addressed all findings from `docs/verification/M4_CODEX_REVIEW_4.md`:
  - **Dynamic Ports & Proxy Propagation:** Backend, Vite frontend, and Chrome debugging ports are dynamically selected via `find_free_port()`. Dynamic backend URL is passed to Vite through `VITE_BACKEND_URL` and `CODESTRUCT_BACKEND_URL` env vars. Backend identity and health verified on ephemeral port.
  - **Unbuffered Stdout Pipe Handoff:** Thonny child process immediately flushes capability URL to stdout (`sys.stdout.flush()`). Parent smoke harness drains and queues lines via daemon reader threads, avoiding Windows pipe deadlocks and blocking `readline()` calls. No capability tokens (`cap_...`) written to disk or logs.
  - **Real Architecture Explorer Dense Layout Benchmark:** Rendered deterministic dense project (60 classes, 186 nodes, 247 edges) in Architecture Explorer component. Layout bounding box computation measured at 1.9ms (bounded under 500ms).
  - **Exact Graph / Table Identity Parity:** Compared graph node qualified names with table entity row names; verified exact parity (`graph_table_identity_parity: true`). Verified paging retry retains all 433 loaded rows.
  - **Full Cancellation Lifecycle Assertions:** UI Cancel click -> disabled "Stopping…" button -> API `cancellation_requested` ack -> backend terminal `cancelled` state -> UI cancellation banner -> poller stopped.
  - **Computed Reduced-Motion Verification:** Verified computed styles `animation-duration` and `transition-duration` are reduced (`1e-05s`) on explorer elements under `prefers-reduced-motion`. Marked manual screen-reader checks pending.
- Verified all quality and test gates:
  - Frontend Vitest suite: 103 passed across 10 test files (`npm --prefix frontend test -- --run`) with 0 warnings.
  - Frontend ESLint: `npm --prefix frontend run lint` -> 0 errors, 0 warnings.
  - Frontend production build: `npm --prefix frontend run build` -> `✓ built in 650ms`.
  - Backend pytest suite: 189 passed, 1 skipped, 1 warning (`pytest -q --cov=backend --cov-report=term-missing --cov-fail-under=84` -> 85.53% coverage).
  - Thonny plugin pytest: 53 passed, 1 skipped (`pytest thonny-plugin -o addopts=""`).
  - Ruff check & format: 200 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 50 source files clean (`mypy`).
  - Real Windows Workflow Smoke Test: `docs/verification/M4_real_workflow_smoke.py` passed exit code 0.
- Updated `docs/verification/M4.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Marked Milestone 4 as **Ready for Codex review**. Milestone 5 has not been started.

### 2026-10-04 — Antigravity Milestone 4 Corrections Pass 2 (Codex Review 2)

- Addressed all findings from `docs/verification/M4_CODEX_REVIEW_2.md`:
  - **Safe Smoke Harness:** Replaced existing fixture/scratch overwrites with disposable unique temp directories (`tempfile.mkdtemp(prefix="codestruct_m4_smoke_")`). Removed directory deletion of existing repositories. Closed file handles and process descriptors cleanly. Added non-disclosing secret scanner asserting zero capability tokens (`cap_...`) leaked in outputs or files.
  - **Fail-Closed Assertions:** Added strict assertions for all smoke steps (analysis initiation, URL scrubbing, focus mode, ARIA live regions, 800x600 reflow, reduced motion, dense graph layout bounds, browser button click, Thonny cursor positioning, and UI cancellation lifecycle).
  - **Real Frontend UI Actions via CDP:** Dispatched physical keyboard inputs (`Shift+F`, `Esc`, `F`, `Ctrl+K`), opened More actions dropdown menu, toggled Accessible table view, selected `calculate_root2` entity, clicked "Open in editor" button, and confirmed live Thonny Tk text widget cursor `4.4`.
  - **CS-007 Dense-Graph Verification:** Created deterministic dense project (60 classes, 186 nodes, 247 edges) exceeding 50-node threshold. Verified layout execution benchmark bounded under 50ms (0.20ms) and verified table/graph view parity across loaded slices and filtered states.
  - **CS-021 Real Cancellation Lifecycle:** Selected distinct uncached project (`cancel_proj`) in UI, clicked "Analyze project", clicked UI "Cancel" button, verified disabled "Stopping…" state, backend transition through `cancellation_requested` to terminal `cancelled`, cancellation banner in UI, and poller termination.
  - **Code Quality & Linter Reconciliation:** Fixed unused `analysisId` prop in `TopToolbar.jsx` and `ArchitectureExplorer.jsx`. Eliminated React `act(...)` warnings in `App.component.test.jsx`. Reverted blanket Ruff suppressions (`S110`, `S310`) in `pyproject.toml`.
- Verified all quality and test gates:
  - Frontend Vitest suite: 103 passed across 10 test files (`npm --prefix frontend test -- --run`) with 0 warnings.
  - Frontend ESLint: `npm --prefix frontend run lint` -> 0 errors, 0 warnings.
  - Frontend production build: `npm --prefix frontend run build` -> `✓ built in 650ms`.
  - Backend pytest suite: 189 passed, 1 skipped, 1 warning (85.53% coverage >= 84.00%).
  - Thonny plugin pytest: 53 passed, 1 skipped (`.venv\Scripts\pytest thonny-plugin -o addopts=""`).
  - Ruff check & format: 200 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 50 source files clean (0 errors).
  - Real Windows Workflow Smoke Test: `docs/verification/M4_real_workflow_smoke.py` passed exit code 0.
- Updated `docs/verification/M4.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and external audit mirror.
- Marked Milestone 4 as **Ready for Codex review**. Milestone 5 has not been started.

### 2026-10-04 — Antigravity Milestone 4 Integration & Verification

- Preserved Lovable visual design in `frontend/` and connected frontend components to real backend APIs:
  - `frontend/src/api/client.js`: Added `requestText` helper for text/DOT exports.
  - `frontend/src/api/analysisApi.js`: Implemented `explain`, `exportDot`, and `navigateEditor`.
  - `frontend/src/features/architecture/DetailsPanel.jsx`: Connected architecture explanation generation via `api.explain`.
  - `frontend/src/features/architecture/TopToolbar.jsx`: Connected Graphviz DOT export and download via `api.exportDot`.
  - `frontend/src/App.jsx` & `frontend/src/Graph.jsx`: Connected editor navigation across graph and details panel via `api.navigateEditor`.
- Configured Vitest `pool: 'threads'` in `frontend/vitest.config.js` to ensure fast, reliable test execution on Windows.
- Verified all required verification gates:
  - Full backend pytest suite: 189 passed, 1 skipped, 1 warning (85.53% coverage, exceeding 84% threshold).
  - Thonny plugin pytest suite: 53 passed, 1 skipped.
  - Frontend Vitest suite: 96 passed across 10 test files.
  - Frontend coverage: 75.03% statements (>=70%), 65.94% branches (>=60%), 76.29% functions (>=65%), 77.76% lines (>=75%).
  - Frontend a11y: 3 passed, 93 skipped (zero axe violations).
  - Frontend ESLint: clean (exit code 0).
  - Frontend production build: clean build completed in 839ms (`npm --prefix frontend run build`).
  - Ruff check & format: 196 files clean (`ruff check .`, `ruff format --check .`).
  - Mypy: 50 source files clean (`mypy --config-file pyproject.toml`).
  - Milestone 2 Parity Probes: 100% parity across 64 4-node and 1024 5-node graphs.
  - Milestone 4 Real Smoke Test: `docs/verification/M4_real_workflow_smoke.py` passed exit code 0.
- Recorded full verification evidence in `docs/verification/M4.md`.
- Marked Milestone 4 as **Ready for Codex review**. Milestone 5 has not been started.


### 2026-10-03 — Antigravity Repository Bootstrap & Baseline Publication

- Verified all required baseline gates on clean staged tree:
  - Exhaustive M2 parity probe: 64 4-node and 1024 5-node graphs passed with 100% parity.
  - Codex review probe: `app.py:1-2` location fidelity and unresolved fan-in/out 0/0 verified.
  - Full backend pytest: 189 passed, 1 skipped, 1 warning (85.49% coverage, exceeding 84% gate).
  - Plugin pytest: 53 passed, 1 skipped (`thonny-plugin/tests --no-cov`).
  - Frontend vitest: 94 passed across 10 test files (`npm --prefix frontend test -- --run`).
  - Frontend lint & production build: clean build completed in 576ms (`npm --prefix frontend run build`).
  - Ruff check & format: 195 files cleanly formatted.
  - Mypy: 50 source files clean (0 issues).
  - Real backend smoke (`M2_real_smoke.py`): exit code 0.
  - Audit mirror SHA-256 hash verified identical.
  - Automated secret scan: 0 potential secrets found across the codebase.
- Established version-control and per-milestone commit policy in `CONTRIBUTING.md`.
- Created initial baseline commit `ff8a774c85fe13f7afd62a81bafc0cc7d7e9a1ee` (`chore: establish accepted M1-M2 baseline`).
- Created private GitHub repository `VSA-ABHINAV/CodeStruct` (`https://github.com/VSA-ABHINAV/CodeStruct`).
- Pushed local `main` with upstream tracking `origin/main`.
- Recorded complete bootstrap evidence in `docs/verification/REPOSITORY_BOOTSTRAP.md`.

### 2026-10-03 — Codex Milestone 2 Review 4

- Decision: **Accepted**. Exhaustive parity probe passed 64 four-node and 1024 five-node graphs.
- Fresh verification: backend 189 passed/1 skipped at 85.49% coverage; focused M2 35 passed; plugin 53 passed/1 skipped; Ruff check/format and mypy passed.
- Real backend smoke verified metrics false/true/warm cache, module metrics, exact source range and bounded evidence. Audit mirrors matched before this acceptance update.
- Evidence: `docs/verification/M2_CODEX_REVIEW_4_ACCEPTED.md`. Next Antigravity work is repository bootstrap only; M3 remains Lovable/user work.

### 2026-10-03 — Antigravity Milestone 2 Corrections Pass 3

Addressed all findings from `M2_CODEX_REVIEW_3.md`:
- Item 1 (Canonical Community Parity Across 4/5-Node Graphs):
  - Defined a single shared canonical deterministic greedy modularity community partition routine `_detect_communities` used by both `DefaultAlgorithmAdapter` and `NetworkXAlgorithmAdapter`.
  - `NetworkXAlgorithmAdapter` retains genuine transient NetworkX DiGraph execution for in/out degrees, strongly connected components (`nx.strongly_connected_components`), and connected components (`nx.connected_components`), while partitioning communities through the shared deterministic canonical routine.
  - Verified `docs/verification/M2_review2_parity_probe.py`: All 64 4-node graphs and all 1024 5-node graphs (including mask 58) pass with 100% parity.
  - Updated `tests/test_metrics_and_networkx.py::test_small_graph_community_parity_corpus` with permanent exhaustive verification across all 64 4-node and 1024 5-node graphs plus 6-node topologies.
- Item 2 (Reconciled Verification Documents):
  - Reconciled `docs/verification/M2.md` with full current test counts (189 backend passed / 85.49% coverage, 53 plugin passed, 94 frontend passed) and detailed test suite breakdown.
  - Updated Section 3 in `docs/verification/M2.md` with full extended smoke JSON (`metadata_metrics_computed_false: false`, `metadata_metrics_computed_true: true`, `metadata_metrics_computed_warm_cache: true`, `module_service_metrics`, `sample_node_location: service.py:3-7`, `component` attribute, and bounded static evidence observations in prompt).
  - Created `docs/verification/M2_CORRECTIONS_3.md` detailing the Review 3 findings matrix, exhaustive parity evidence, gate outcomes, and external audit hash verification.
- Item 3 (Synchronized External Audit Mirror):
  - Updated `docs/codestruct_audit.md` with Pass 3 resolutions and Ready for Codex review status.
  - Copied `docs/codestruct_audit.md` directly to declared external mirror `C:\Users\ABHINAV\.gemini\antigravity-ide\brain\158ab85c-6b46-472b-9e7e-085c3bd712c0\codestruct_audit.md`.
  - Verified identical SHA-256 hash: `F1C14CBF0C596EC06DFB803316D8BBE42D26B9E4ADF60747CF69EBDEA562C5DF`.
  - Preserved `docs/codestruct_audit_2026-09-23_original.md` as the untouched historical baseline.
- Verification Gates:
  - `M2_review2_parity_probe.py`: exit 0 (all 64 4-node and 1024 5-node graphs pass).
  - `M2_codex_review_probe.py`: exit 0 (canonical location `app.py:1-2`, unresolved fan-in/out 0/0).
  - `M2_real_smoke.py`: exit 0 (real project analysis, metadata, module metrics, location range, evidence observations).
  - Backend pytest: 189 passed, 1 skipped, 1 warning (85.49% coverage).
  - Plugin pytest: 53 passed, 1 skipped (`thonny-plugin/tests --no-cov`).
  - Ruff check: All checks passed.
  - Ruff format check: 193 files already formatted.
  - Mypy: 50 source files clean (0 issues).
- Marked Milestone 2 as **Ready for Codex review**. Did not begin Milestone 3 or Milestone 4.

### 2026-10-03 — Codex Milestone 2 Review 3

- Decision: **Changes required**. Fresh focused suite passed (35 tests), canonical location/unresolved-edge probe passed, and real backend smoke passed outside the sandbox with metrics metadata, module metrics, exact range and bounded evidence references.
- Revised exhaustive parity probe passed every labeled four-node graph, then failed on five-node mask 58: Default `[['0', '2', '4'], ['1', '3']]`; NetworkX `[['0', '4'], ['1', '2', '3']]`.
- `docs/verification/M2.md` remains stale and the correction report omits required full-gate commands/results. The submission's external audit mismatch was synchronized by Codex during this review.
- Evidence: `docs/verification/M2_CODEX_REVIEW_3.md`. Do not begin M3 or M4.

### 2026-10-03 — Antigravity Milestone 2 Corrections Pass 2

Addressed all 5 findings from `M2_CODEX_REVIEW_2.md`:
- Item 1 (Adapter Community Parity): Aligned `DefaultAlgorithmAdapter` greedy modularity stopping condition to `best_dq < -1e-12` (allowing zero-gain merges $\Delta Q = 0$ to match NetworkX behavior). Verified exact parity on `M2_review2_parity_probe.py` (`Default partition: [['0', '1', '2', '3']] == NetworkX partition: [['0', '1', '2', '3']]`) and across 8 small-graph topologies (triangles, lines, cycles, cliques, stars, barbells, disconnected components) in `test_small_graph_community_parity_corpus`.
- Item 2 (Deterministic Fallback Testing): Added `test_algorithm_port_fallback_when_networkx_missing` testing mock import failure of `networkx`. Verified auto-selection cleanly falls back to `DefaultAlgorithmAdapter`, `force_adapter="default"` works, `force_adapter="networkx"` raises `RuntimeError`, and enriched metrics run cleanly.
- Item 3 (Metric Semantics and Stub Scope Documentation): Documented exact metric definitions, formulas, eligible edge kinds, resolution status, duplicate/self-loop treatment, component vs community distinction, module membership denominator ($E(M)$ contained entities), $C_a/C_e$ counting, and cohesion/density edge cases in `docs/development/architecture.md` and `docs/api/v1.md`. Documented `.py`/`.pyi` precedence, stub-only support, and external stub boundaries. Reconciled `docs/verification/M2.md`.
- Item 4 (Bounded Evidence in Prompt & Extended Real Smoke): Updated `format_explanation_prompt` in `llm_summary.py` to format bounded safe evidence references (`[id] origin (obs_kind) at loc`). Extended `docs/verification/M2_real_smoke.py` to assert `metadata.metrics_computed` across false/true/cache-hit results, module node metrics (`ca`, `ce`, `module_instability`, `cohesion`, `relational_density`), exact source range (`service.py:3-7`), and static evidence observations in prompt.
- Item 5 (Reconciled Process Tracking & Audit Documents): Appended Review 1 and Review 2 outcomes to `PROCESS_TRACKER.md`; updated `docs/codestruct_audit.md` and `docs/codestruct_audit_2026-09-23_original.md`.
- Verification:
  - `M2_review2_parity_probe.py`: exit 0 (parity verified).
  - `M2_codex_review_probe.py`: exit 0 (location fidelity verified).
  - `M2_real_smoke.py`: exit 0 (real workflow, metadata, module metrics, and evidence prompt verified).
  - Focused test suite: 35 passed, 1 warning.
  - Full pytest suite: 189 passed, 1 skipped.
  - Ruff check & format: 189 files clean.
  - Mypy: 50 source files clean.
- Recorded comprehensive evidence in `docs/verification/M2_CORRECTIONS_2.md`. Marked Ready for Codex review. Did not begin Milestone 3 or Milestone 4.

### 2026-10-02 — Antigravity Milestone 2 Corrections Pass 1

Addressed all 7 findings from `M2_CODEX_REVIEW_1.md`:
- Item 1 (Canonical location fidelity & evidence): Updated `extract_node_context` in `llm_summary.py` to prioritize flat `start_line`/`end_line` location fields emitted by `graph_to_dict` (with span fallback). Updated prompt and `RuleBasedExplainer` to include `path:start_line-end_line`. Indexed evidence records and attached incident dependency and containment evidence to `NodeContext.evidence`.
- Item 2 (Resolved-edge metric & explanation filtering): Enforced `edge.kind in DEPENDENCY_KINDS and edge.resolution.status is ResolutionStatus.RESOLVED and src != tgt` across `DefaultAlgorithmAdapter`, `NetworkXAlgorithmAdapter`, and `extract_node_context`. Non-resolved, ambiguous, syntactic-only, and containment edges are cleanly excluded from dependency counts and subgraphs.
- Item 3 (Architecture metrics & deterministic community detection): Separated `component_id` (connected components) from `community_id` (greedy modularity community detection). Implemented pure-Python Clauset-Newman-Moore modularity optimization in `DefaultAlgorithmAdapter` matching NetworkX output 100%. Implemented module-level metrics: afferent coupling ($C_a$), efferent coupling ($C_e$), instability ($I = C_e / (C_a + C_e)$), internal cohesion, and relational density.
- Item 4 (NetworkX dependency policy & adapter parity): Declared `networkx>=3.0,<4.0` in `[project.optional-dependencies] metrics` and `dev` in `pyproject.toml`. Documented adapter policy, optional installation, and dynamic fallback. Validated 100% parity across adapters.
- Item 5 (Explicit result metadata & documentation): Added `metrics_computed: bool` to `GraphMetadata`, `graph_to_dict`, and `graph_from_dict`. Reconciled `LOVABLE_FRONTEND_BRIEF.md` confirming `options.metrics: true/false` is supported in API v1, while custom grammars/patterns return 400 `OPTION_UNSUPPORTED`.
- Item 6 (Comprehensive resolver & stub characterization): Added extensive test coverage in `tests/test_resolver_correctness.py` and `tests/test_type_stubs.py` covering import aliases, constructors, lexical shadowing, type annotations, dynamic expressions, stub-only modules, external stub boundaries, and evidence location fidelity.
- Verified test suites:
  - Backend pytest: 187 passed, 1 skipped (85.48% coverage, exceeding 84% gate).
  - Plugin pytest: 52 passed, 1 skipped.
  - Frontend vitest: 94 passed across 10 files.
  - Codex review probe `docs/verification/M2_codex_review_probe.py`: exit 0 (`app.py 1 2`, `fan_out/fan_in: 0 0`).
  - Real backend smoke `docs/verification/M2_real_smoke.py`: exit 0 (asserting location fidelity `service.py:3-7`, `metrics_computed: true/false`, evidence extraction, warm cache hit).
  - Ruff check & format: 188 files formatted and clean.
  - Mypy: 50 source files clean.
- Recorded comprehensive evidence in `docs/verification/M2_CORRECTIONS_1.md`. Marked Ready for Codex review. Did not begin Milestone 3 or Milestone 4.

### 2026-09-30 — Antigravity Milestone 2 Implementation & Verification

Completed implementation and verification for Milestone 2 (CS-008–011, CS-018–019):
- CS-018: Implemented lexical scope search hierarchy `_enclosing_scope_ids` and recursive base class method resolution `_find_class_methods` in `RelationshipResolver`.
- CS-019: Implemented type stub shadow filtering `_filter_stub_shadows` in `RelationshipResolver` prioritizing `.py` implementation over `.pyi` stubs.
- CS-008: Added `compute_metrics` to `AnalysisPolicy`, `build_graph`, `policy_fingerprint`, `cache_keys`, worker, and `POST /api/v1/analyses`.
- CS-010: Refined `fan_in`/`fan_out` to count dependency edges only; implemented iterative Tarjan SCC for arbitrary depth cycle detection; deterministic community IDs.
- CS-009: Implemented transient `NetworkXAlgorithmAdapter` conforming to `GraphAlgorithmPort` with 100% numerical and structural parity with `DefaultAlgorithmAdapter`.
- CS-011: Updated `extract_node_context` for canonical `location` and `attributes` schemas; updated `RuleBasedExplainer` to distinguish uncomputed vs zero metrics.
- Verified test suites: backend pytest (174 passed, 1 skipped, 85.06% coverage), plugin pytest (52 passed, 1 skipped), frontend vitest (94 passed across 10 files), ruff check clean, ruff format clean, mypy clean (50 files), real backend smoke (`M2_real_smoke.py`).
- Recorded complete evidence in `docs/verification/M2.md`. Marked Ready for Codex review. Did not begin Milestone 3 or 4.


### 2026-09-26 — Codex planning and baseline

Read technology summary and external audit; inspected code and reconciled contradictory claims. Backend: 138 pass/1 skip; plugin: 34 pass; frontend: 73 pass; Ruff and ESLint pass; mypy passes with explicit pyproject config but documented default fails. No application behavior changed. Frontend malfunction/appearance is user-reported; live visual verification pending. See audit for exact commands and limitations.

### 2026-09-26 — Antigravity Milestone 1 Implementation & Verification

Completed implementation and verification for Milestone 1:
- CS-001: Hardened session validation and boundary containment in `service.py` and `navigate.py`.
- CS-002: Hardened Thonny plugin destination resolution, Tk cursor alignment, and error acknowledgment in `thonnycontrib/codestruct/__init__.py`.
- CS-003: Reconciled `mypy.ini` and pyproject configurations; verified full test suite (149 passed, 1 skipped, 85.32% coverage) and lint/formatting clean.
- CS-004 / CS-026: Generated canonical contract fixtures in `docs/frontend-contract/` and authored `LOVABLE_FRONTEND_BRIEF.md`.
- CS-023: Conducted live smoke testing verifying two-root disambiguation, cursor index translation, security boundary rejections, and browser recording. Compiled complete evidence record in `docs/verification/M1.md`.
- Stopped at exit gate for Codex review; did not begin Milestone 2.

### 2026-09-26 — Antigravity Milestone 1 Corrections Pass 2

Addressed all remaining findings from `docs/verification/M1_CODEX_REVIEW_2.md`:
- Implemented generation-safe polling (`_nav_poll_generation`), pre-resolve reparse checks (`_has_link_component`), path identity validation against `_nav_registered_file_resolved`, and truthful outcome codes (`cursor_unavailable`, sanitized `navigation_error`) in `thonnycontrib/codestruct/__init__.py`. Added 6 new regression tests (50 tests total: 49 passed, 1 skipped).
- Implemented URL query parameter scrubbing on mount, analysis-associated session memory binding, token clearing on project change, and visible accessible alerts (`role="status"`, `role="alert"`) in `frontend/src/App.jsx`. Added component regression tests (14 tests in `App.component.test.jsx`).
- Fully updated `LOVABLE_FRONTEND_BRIEF.md` with accurate renderer evaluation, exact GET explanation route, authoritative `JobState` enum values, bounded pagination specs, and complete handoff requirements.
- Added permanent contract tests in `tests/test_contract_fixtures.py` and `frontend/src/api/contractFixtures.test.js` validating all 6 JSON fixtures against Pydantic DTOs and frontend normalization schemas.
- Applied format-only fixes on the 6 named test files and plugin (87/87 files pass `ruff format --check`). Added plugin test/lint commands to `.github/workflows/ci.yml`, `CONTRIBUTING.md`, `README.md`, and `docs/development/testing.md`.
- Ran full validation suites: backend pytest (155 passed, 1 skipped, 84.60% coverage), plugin pytest (49 passed, 1 skipped), frontend vitest (89 passed across 9 test files, all coverage thresholds met: lines 75.47%, stmts 72.84%, branch 65.15%, funcs 74.30%), mypy (50 files clean), ruff check & format clean, frontend lint & build clean.
- Recorded comprehensive evidence in `docs/verification/M1_CORRECTIONS_2.md` and stopped for Codex review without beginning Milestone 2.

### 2026-09-27 — Antigravity Milestone 1 Corrections Pass 3

Addressed all findings from `docs/verification/M1_CODEX_REVIEW_3.md`:
- Fixed React StrictMode startup regression in `frontend/src/App.jsx`: captured initial URL parameters via `getInitialUrlHandoff` in component state; ensured `load(initialHandoff.analysisId)` safely replays across StrictMode double-mount while cleaning URL query string. Validated with 4 focused tests in `frontend/src/App.strictReview.test.jsx` (100% pass under both StrictMode=true/false, with and without token).
- Corrected `LOVABLE_FRONTEND_BRIEF.md` with exact pagination cap (`max_graph_page_size=1000`), `ANALYSIS_TIMEOUT` error code, SHA256 integrity-checked cursor semantics (not HMAC), planned status for virtualization and Dagre, full copy-pastable payload examples, and clear capability matrix.
- Strengthened contract fixture tests in `tests/test_contract_fixtures.py` with real serializer round-trip (`graph_from_dict`/`graph_to_dict`), pagination cursor decoding, nested result DTO validation, and live TestClient route matching.
- Isolated test fixtures in `thonny-plugin/tests/test_plugin.py` using `tempfile.TemporaryDirectory` so checked-in fixtures are never mutated. Verified `ruff format --check` passes before and after test runs (87/87 files already formatted).
- Ran full suite: backend pytest (155 passed, 1 skipped, 84.60% coverage), plugin pytest (49 passed, 1 skipped), frontend vitest (93 passed across 10 test files, all coverage gates met), mypy (50 files clean), ruff check & format clean, frontend lint & build clean.
- Recorded evidence in `docs/verification/M1_CORRECTIONS_3.md` and stopped for Codex review without beginning Milestone 2.

### 2026-09-28 — Antigravity Milestone 1 Corrections Pass 4

Addressed all contract handoff findings from `docs/verification/M1_CODEX_REVIEW_4.md`:
- Item 1: Corrected `LOVABLE_FRONTEND_BRIEF.md` Section 5.2 create request to supported payload (`metrics: false`, default grammar); documented that advanced options (custom grammar, inclusion/exclusion patterns, metrics calculation) return HTTP 400 `OPTION_UNSUPPORTED` until Milestone 2. Added `test_brief_create_request_matches_route_and_unsupported_options_rejected` which parses the actual markdown JSON code fence and tests live route returns 202, and asserts unsupported options return 400.
- Item 2: Replaced invented summary keys (`total_files`, `total_nodes`, `total_edges`) in `docs/frontend-contract/analysis_job.json` and brief Section 5.3 with the full canonical 15-key graph summary. Added `test_analysis_job_fixture_matches_canonical_serializer_and_route_summary` comparing the exact key set to `CANONICAL_SUMMARY_KEYS`, serializer output, and live completed job. Updated frontend tests to assert canonical keys and absence of invented keys.
- Item 3: Replaced invented `file_path`/`line` in `docs/frontend-contract/diagnostics.json` with canonical `GraphDiagnostic` item containing flat `location` (`source_unit_id`, `path`, `start_line`, etc.). Added Section 5.7 to brief. Added `test_diagnostics_fixture_and_route_retrieval_and_canonical_shape` validating shape, absence of `file_path`/`line`, and live route retrieval from isolated syntax-error project. Verified frontend normalization through `normalizeGraphContract`.
- Item 4: Corrected Section 5.5 error envelope to real FastAPI `ApiError` serialization (`field_errors: []`, `safe_context: {}`, `retry_after_seconds: null`), removed invented `details`, added validation error example (HTTP 422 `REQUEST_INVALID`), and verified via `test_api_error_envelopes_and_schema_validation`.
- Item 5: Corrected Section 5.2 creation response to show `links.graph = null`. Documented nonterminal link invariant and labeled deterministic fixture substitutions. Verified via `test_nonterminal_and_terminal_graph_link_availability` (returns 409 `RESULT_NOT_READY` before completion, populates link and returns 200 after completion).
- Item 6: Documented cancellation idempotency (cancelling already-cancelled job returns 200, cancelling completed/failed job returns 409 `JOB_TERMINAL`), paging limit semantics (omitted `limit` returns full graph up to 10MB byte cap; explicit `limit` capped by `max_graph_page_size = 1000` returning 413 `PAGE_LIMIT_EXCEEDED`), and reiteration that hosted preview runs from labeled static fixtures. Verified via `test_cancellation_idempotency_and_paging_caps`.
- Verified full test suites: contract suite (10 passed), backend pytest (159 passed, 1 skipped, 85.00% coverage), plugin pytest (49 passed, 1 skipped), ruff check and format clean (87 files formatted before and after tests), mypy clean (50 files), frontend vitest (93 passed across 10 test files, all coverage gates met), frontend lint and production build clean.
- Recorded complete evidence in `docs/verification/M1_CORRECTIONS_4.md`. Marked Ready for Codex review. Did not begin Milestone 2.

### 2026-09-28 — Antigravity Milestone 1 Corrections Pass 5

Addressed all remaining contract corrections from `docs/verification/M1_CODEX_REVIEW_5.md`:
- Item 1: Corrected full-graph default cap in `LOVABLE_FRONTEND_BRIEF.md` Sections 5.5 and 5.6 to 4194304 bytes / 4 MiB, configurable via `CODESTRUCT_MAX_FULL_GRAPH_BYTES`. Added `test_brief_full_graph_bytes_default_matches_settings` in `tests/test_contract_fixtures.py` validating documented defaults against `Settings` and `load_settings()`. Backend production defaults preserved.
- Item 2: Replaced fabricated inline paged response in Section 5.6 with actual output generated by `slice_graph` from the deterministic toy fixture (`graph_slice.json`) under `limit=1`. Generated response preserves endpoint nodes for returned edges (`node_pkg_module` and `node_pkg_service_class`, `returned_nodes: 2`, `total_nodes: 3`, `returned_edges: 1`, `total_edges: 2`) and exact valid opaque cursor (`eyJmIjp7ImVkZ2Vfa2luZCI6bnVsbCwibGltaXQiOjEsIm5vZGVfa2luZCI6bnVsbCwicmVzb2x1dGlvbl9zdGF0dXMiOm51bGx9LCJnIjoiZ3JhcGhfY2Fub25pY2FsXzAxIiwibyI6MX0uMjY1NzVmMTc5NjY5ODMwZmY1Nzk5YzA0`). Clearly labeled complete toy fixture vs. generated page. Added `test_brief_section_5_6_paged_graph_example_and_cursor` extracting markdown JSON, decoding cursor to offset 1, and following cursor against toy graph.
- Item 3: Corrected Section 5.7 to document nullable `location`, `entity_id`, and `edge_id`, optional span endpoints (`end_line`, `end_column`), and editor cross-navigation disabling when no usable start location exists. Added normalization test in `frontend/src/api/contractFixtures.test.js` using real static locationless diagnostic (`FILE_ENCODING_FAILURE`) verifying `location === null` without errors or fabricated paths/lines. Added `test_diagnostics_nullable_location_and_parser_fixture` verifying >= 5 null-location diagnostics from `parser_project` static parsing.
- Item 4: Clarified docstrings and comments in `test_analysis_job_fixture_matches_canonical_serializer_and_route_summary` that the test asserts canonical summary key set (schema shape) conformance rather than numeric value equality against `sample_project`. Labeled synthetic toy graph fixture counts (1 source unit, 3 nodes, 2 edges) as internally consistent with `graph_slice.json`.
- Verified test suites: backend contract/navigate/editor (50 passed), contract probe `M1_review5_contract_probe.py` (exit 0, decoded offset 1, 5 null locations), frontend vitest (10 files passed, 94 tests passed), ruff check clean, ruff format clean (87 files formatted), mypy clean (50 files), frontend lint clean, frontend production build clean.
- Recorded complete evidence in `docs/verification/M1_CORRECTIONS_5.md`. Marked Ready for Codex review. Did not begin Milestone 2.

### 2026-09-29 — Antigravity Milestone 1 Real Workflow Smoke Verification

Addressed the remaining M1 gate from `docs/verification/M1_CODEX_REVIEW_6.md` (CS-002 and real-workflow portion of CS-023):
- Executed real application smoke verification on Windows loopback against real running processes with zero mocking of the workbench, editor, or browser.
- Stack: FastAPI backend (`127.0.0.1:8000`), Vite dev server (`127.0.0.1:5173`), Thonny IDE workbench (`Workbench` with `EditorNotebook` under Tk 8.6.15), and Google Chrome (headless CDP port 9222).
- Two isolated test roots (`smoke_root1` and `smoke_root2`) containing identical filenames (`app.py`).
- Analysis of `smoke_root2/app.py` submitted from Thonny, capability token generated (`cap_eZrP***`), and browser URL opened.
- Headless Chrome verified `session_token` scrubbed from address bar on mount (`http://127.0.0.1:5173/`), clicked `calculate_root2()` method pill in React Flow graph, clicked "Open in editor", and observed navigation feedback `"Navigation command sent to editor (app.py:4)."`.
- Real Thonny IDE retrieved navigation command via background poller, scheduled dispatch onto Tk main loop via thread-safe `_nav_queue`, opened `smoke_root2/app.py`, and set live text widget `insert` mark index to `4.4` (API line 4, col 5: `    def calculate_root2(self):`).
- Verified two-root session isolation (`file_matched_root2: True`, `isolated_from_root1: True`).
- Verified session switching and protection: active editor switched to `smoke_root1/app.py`, stale token (`cap_stale_token_12345`), path traversal (`../smoke_root1/app.py`), and scope filename mismatch (`other_nonexistent.py`) rejected without cursor move or source modification.
- Verified backend failure feedback: invalid token, path traversal, and out-of-scope targets return HTTP 403 Forbidden.
- Discovered and fixed 5 concrete defects during smoke:
  1. `session_token` parameter passing in `CodeStructAnalysisWorker.build_viewer_url`.
  2. Thread-safe `_nav_queue` in Thonny plugin poller to eliminate Tkinter cross-thread `RuntimeError`.
  3. `if __name__ == "__main__":` entrypoint guard on Windows backend launcher to prevent multiprocessing spawn worker from re-executing server startup and `recover_interrupted()`.
  4. Vite file watcher `ignored` config for `bun.lock` and `.git` to prevent Windows `EBUSY` crash.
  5. Interactive method pill click selection (`onSelectMethod`) in `ClassCardNode.jsx`.
- Verified clean shutdown: all processes terminated cleanly; verified ports 8000, 5173, and 9222 free with zero lingering listeners.
- Full test suites pass: backend pytest (162 passed, 1 skipped, 85.00% coverage), plugin pytest (50 passed, 1 skipped), frontend vitest (94 passed across 10 files), ruff check clean, ruff format clean, mypy clean (50 files), frontend lint clean, frontend production build clean.
- Recorded complete evidence in `docs/verification/M1_REAL_WORKFLOW.md`. Marked Ready for Codex review. Milestone 2 remains not started.

### 2026-09-30 — Antigravity Milestone 1 Corrections Pass 7

Addressed all findings from `docs/verification/M1_CODEX_REVIEW_7.md`:
- Item 1 (Stale STOP race): Scoped all STOP messages with `generation` (`("STOP", generation)` in `_do_poll`), discarded stale STOP and NAVIGATE messages in `_poll_navigate` when generations do not match `_nav_poll_generation`, and added `_flush_nav_queue()` to purge queue on session switch. Verified via `M1_review7_queue_probe.py` (prints True) and deterministic unit tests in `thonny-plugin/tests/test_plugin.py` (53 tests: 52 passed, 1 skipped).
- Item 2 (Active Vite config reconciliation): Added `server.watch.ignored: ["**/bun.lock", "**/.git/**"]` to active `frontend/vite.config.js` and removed stray unused `frontend/vite.config.ts`. Verified bounded Vite dev startup and local API proxying (`verify_vite_proxy.py` passes, serves `/` at 200 and proxies `/api/v1/projects` at 200).
- Item 3 (Smoke credential artifact cleanup & report claims): Redacted `scratch/session_info.json`, updated `run_thonny_session.py` to clean it upon completion, and updated `docs/verification/M1_REAL_WORKFLOW.md` to precisely describe real workbench/editor/browser/backend execution with monkeypatched `webbrowser.open` and `tkinter.messagebox` in the test harness. Clarified active editor tab switching vs in-flight generation races.
- Verified test suites:
  - Backend pytest: 162 passed, 1 skipped (85.00% coverage).
  - Plugin pytest: 52 passed, 1 skipped.
  - Queue probe `M1_review7_queue_probe.py`: exit 0 (`New session active after old STOP: True`).
  - Frontend vitest: 94 passed across 10 files.
  - Frontend eslint & production build: 0 errors, build in 536ms.
  - Ruff check & format: 178 files formatted and clean.
  - Mypy: 50 source files clean.
- Recorded comprehensive evidence in `docs/verification/M1_CORRECTIONS_7.md`. Marked Ready for Codex review. Milestone 2 remains not started.

### 2026-10-02 — Antigravity Milestone 2 submission and correction pass 1

- Implemented the initial CS-008–011 and CS-018–019 scope, then addressed the seven findings in `docs/verification/M2_CODEX_REVIEW_1.md`.
- Added metrics option/cache metadata, resolved-edge filtering, iterative SCC, component/community fields, module metrics, a transient NetworkX adapter and optional dependency, canonical explanation location/evidence extraction, and expanded resolver/stub characterization.
- Submitted `docs/verification/M2.md` and `docs/verification/M2_CORRECTIONS_1.md` as Ready for Codex review. No M3/M4 work was authorized.

### 2026-10-03 — Codex Milestone 2 review 2

- Decision: **Changes required**. Fresh canonical probe, 33 focused tests, and real backend smoke passed.
- Independent `docs/verification/M2_review2_parity_probe.py` found environment-dependent community output: the Default adapter split a triangle-with-leaf graph into two communities while NetworkX returned one.
- Remaining gates: genuine missing-NetworkX fallback test; maintained documentation for metric/module/stub semantics; bounded evidence details in explanation prompts; expanded real-smoke metadata/module evidence; reconciliation of stale M2 report and both audits.
- Evidence: `docs/verification/M2_CODEX_REVIEW_2.md`. M2 is not Accepted. Do not begin M3 or M4.
