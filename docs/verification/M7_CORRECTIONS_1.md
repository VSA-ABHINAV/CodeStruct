# Milestone 7 Corrections 1: Verification Report

**Date:** 2026-10-14
**Author:** Antigravity
**Status:** Complete — Ready for Codex Review
**Prior Decision:** Changes required (`docs/verification/M7_CODEX_REVIEW_1.md`)
**Scope:** CS-015 (persistent per-file parse cache) and CS-017 (Graphviz exports)

---

## 1. Executive Summary

This report documents the resolution of all findings raised in `docs/verification/M7_CODEX_REVIEW_1.md`:
- **R1 (CS-017, P1):** Subprocess streaming limits and prompt process tree termination for Graphviz execution, capped stderr buffering, and serialized DOT string length enforcement.
- **R2 (CS-015, P2):** Iterative parse-cache byte budget eviction loop guaranteeing that post-insert stored bytes and entry count strictly respect configured maximums, plus rejection of oversized single entries.
- **R3 (CS-017, P2):** User-facing export distinction in the active application (`frontend.lovable/src/features/workbench.tsx`) between "Export DOT (Loaded Slice)" and "Export DOT (Complete Graph)", with explicit partial-load explanation and frontend regression tests.

All changes were implemented with targeted regressions, full quality gates (319 backend tests at 85.54% coverage, 10 frontend tests, Ruff, Mypy, Vite build, and the 8-scenario end-to-end verification script), and clean working tree checks.

---

## 2. Detailed Corrections

### 2.1 R1 — Subprocess Streaming Bounds and Early Process Termination (CS-017)
- **Problem:** `export_dot.py` previously buffered all process output into memory via `Popen.communicate()` before checking length against `max_bytes`, which allowed unbounded peak memory consumption. In addition, stderr was uncapped, and the raw `.dot` output format bypassed byte cap validation.
- **Fix in `backend/src/codestruct/graph/export_dot.py`:**
  - Implemented `_read_limited_stream(stream, max_bytes)` using 64 KiB chunks with early abortion when accumulated bytes exceed `max_bytes`.
  - Added `_kill_process_tree(pid)` to promptly terminate the entire process hierarchy on Windows/POSIX when an output stream limit is exceeded or on timeout.
  - Bounded stderr capture to `max_stderr_bytes` (default 64 KiB) to prevent unbounded memory growth from noisy stderr output.
  - Applied output length bounding in `graph_to_dot(graph, max_bytes=...)` and in `export_dot(graph, format='dot', max_bytes=...)`.
- **Regressions added in `tests/test_export_dot.py`:**
  - `test_render_graphviz_streaming_stdout_limit_early_termination`: Verifies that a process emitting 1 MiB under a 10 KiB limit is killed immediately, does not buffer 1 MiB in memory, and raises `GraphvizOutputLimitExceeded`.
  - `test_render_graphviz_streaming_stderr_limit`: Verifies that a process emitting excessive stderr under a 10 KiB stderr limit is promptly terminated with `GraphvizOutputLimitExceeded`.
  - `test_graph_to_dot_serialization_max_bytes_exceeded`: Verifies that generating a DOT graph with oversized labels exceeding `max_bytes` raises `GraphvizOutputLimitExceeded`.

### 2.2 R2 — Iterative Parse-Cache Byte Budget Eviction (CS-015)
- **Problem:** `PersistentFileParseCache._evict_if_needed()` previously ran at most one batch of LRU deletions (`max(1, count // 10)`), which allowed incoming large entries to leave the cache exceeding `max_bytes`.
- **Fix in `backend/src/codestruct/storage/file_cache.py`:**
  - Replaced the single-batch eviction with an iterative loop: while `current_count + 1 > max_entries` OR `current_bytes + incoming_bytes > max_bytes`, the cache repeatedly deletes LRU batches until both budgets fit.
  - Added an entry-size preflight guard: if `incoming_bytes > max_bytes`, caching is skipped entirely without corrupting existing cache entries.
  - Added post-insertion invariant assertion ensuring that both count and byte bounds hold after every store transaction.
- **Regressions added in `tests/test_file_cache.py`:**
  - `test_evict_under_byte_pressure_iterative`: Verifies the exact probe scenario from Codex Review 1 (10 rows of 10 bytes under 100-byte cap, incoming 80-byte entry triggers multiple evictions until total bytes <= 100).
  - `test_evict_under_combined_count_and_byte_pressure`: Tests simultaneous count and byte limit pressure under randomized entry sizes.
  - `test_skip_entry_exceeding_byte_capacity`: Verifies an incoming entry larger than `max_bytes` is safely skipped and does not exceed the limit.
  - `test_byte_budget_enforcement_probe`: Confirms post-insert total bytes never exceed `max_bytes`.

### 2.3 R3 — User-Facing Slice vs Complete DOT Export Distinction (CS-017)
- **Problem:** The active launcher configuration (`prototype-config.json`) serves `frontend.lovable`, which previously offered only a single "Export DOT graph" button that unconditionally hit the server-side complete graph API without distinguishing loaded pages from the full project.
- **Fix in `frontend.lovable/src/features/workbench.tsx`:**
  - Added two distinct actions in the workspace toolbar:
    - **`DOT (Slice)` (`Export DOT (Loaded Slice)`):** Serializes the currently loaded/visible in-memory graph slice using client-side `graphToDot()`.
    - **`DOT (Complete)` (`Export DOT (Complete Graph)`):** Downloads the complete server-side graph via `/api/v1/analyses/{id}/export/dot`.
  - Added an explanatory banner during partial-load state informing the user:
    `"Partial graph loaded (X of Y nodes). 'DOT (Slice)' exports loaded page; 'DOT (Complete)' exports full graph."`
- **Regressions added in `frontend.lovable/src/features/integration.test.tsx`:**
  - `satisfies R3 by distinguishing loaded slice export from complete graph export and handling partial load`: Verifies that `graphToDot()` emits only the loaded slice, while `exportDot()` triggers `/api/v1/analyses/{id}/export/dot`.

---

## 3. Verification Gate Evidence

Exact commands, exit codes, and outputs for all verification gates:

### 3.1 Backend Test Suite & Code Coverage (Pytest)
- **Command:** `.venv\Scripts\python.exe -m pytest tests --cov=backend --cov-report=term-missing --cov-fail-under=84`
- **Exit Code:** `0`
- **Output:**
```
================= 319 passed, 2 skipped, 2 warnings in 36.88s =================
Required test coverage of 84% reached. Total coverage: 85.54%
```
- **Total Tests:** 319 passed, 2 skipped, 0 failed.
- **Skipped Tests:**
  1. `tests\test_scanner.py:153`: Directory links unavailable for this test account.
  2. `tests\test_tree.py:137`: Symlinks not supported in this test environment.
- **Code Coverage:** **85.54%** (strictly exceeds the required repository gate of 84.00%).

### 3.2 Static Linters and Type Checking
- **Ruff Lint:**
  - **Command:** `.venv\Scripts\ruff.exe check backend tests tools scripts`
  - **Exit Code:** `0`
  - **Output:** `All checks passed!`
- **Ruff Format Check:**
  - **Command:** `.venv\Scripts\ruff.exe format --check backend tests tools scripts`
  - **Exit Code:** `0`
  - **Output:** `100 files already formatted`
- **Mypy Type Checking:**
  - **Command:** `.venv\Scripts\mypy.exe backend/analyzer.py backend/main.py backend/src/codestruct`
  - **Exit Code:** `0`
  - **Output:** `Success: no issues found in 57 source files`

### 3.3 End-to-End M7 Verification Script
- **Command:** `.venv\Scripts\python.exe scripts/verify_m7_cache_export.py`
- **Exit Code:** `0`
- **Output:**
```
[M7 Verify] Scenario 1: Cold Analysis on Mutable Project...
  -> Cold run completed: 3 files cached in file_parse_cache table.
[M7 Verify] Scenario 2A: Whole-Result Cache Hit...
  -> Whole-result whole-graph cache hit returned 200 with cache_hit=True.
[M7 Verify] Scenario 2B: Warm Analysis via Worker with Per-File Cache Reuse...
  -> Warm worker run completed in 1.189s with identical graph (15 nodes).
[M7 Verify] Scenario 3: Same-Size Content Edit Invalidation...
  -> Invalidation on same-size edit verified successfully.
[M7 Verify] Scenario 4: Timestamp Touch (mtime altered, content identical)...
  -> Touched mtime content-digest cache reuse verified.
[M7 Verify] Scenario 5: Graphviz DOT Export Route...
  -> DOT export verified: 6599 characters generated.
[M7 Verify] Scenario 6: Actionable Diagnostics for Missing Graphviz...
  -> Missing Graphviz returned 503 GRAPHVIZ_UNAVAILABLE with actionable instructions.
[M7 Verify] Scenario 7: Successful SVG & PNG Rendering via Mock Executable...
  -> Rendered SVG and PNG successfully with headers and content signatures verified.
[M7 Verify] Scenario 8: Format validation and Bounds enforcement...
  -> Format validation verified.
OVERALL STATUS: SUCCESS (Total time: 4.88s)
```

### 3.4 Frontend Verification Suite (Vitest)
- **Command:** `npm --prefix frontend.lovable run test` (`npx vitest run`)
- **Exit Code:** `0`
- **Output:**
```
Test Files  1 passed | 1 skipped (2)
     Tests  10 passed | 1 skipped (11)
  Duration  2.69s
```
- **Reconciled Test Breakdown:**
  - Total test files: 2 (1 passed, 1 skipped).
  - Total tests: 11 (10 passed, 1 skipped, 0 failed).
  - `src/features/integration.test.tsx`: 10 passed (Strict mode replay, hierarchy layout levels 0-5, R3 slice vs complete export, folder open, tree fetch).
  - `src/features/live.test.tsx`: 1 skipped (by design; requires an independently running live backend server instance).

### 3.5 Frontend Production Build
- **Command:** `npm --prefix frontend.lovable run build` (`vite build`)
- **Exit Code:** `0`
- **Output:** Built in 447ms, 1881 modules transformed, 0 warnings or errors. Bundles emitted to `frontend.lovable/dist/`.

### 3.6 Real Windows Standalone Whole-Folder Workflow
- **Command:** `.venv\Scripts\python.exe scripts/verify_real_windows_standalone_workflow.py`
- **Exit Code:** `0`
- **Walkthrough and Results:**
  - **Step 1:** Created disposable fixture project at `scratch/standalone_workflow_project` with nested package `nested/domain/calculator.py` (module `calculator`, top-level function `compute_discount`, class `InvoiceCalculator`, methods `calculate_total` and `format_currency`), non-Python config `nested/config/settings.json`, and version control `nested/.git`.
  - **Step 2:** Verified clean service state via `Stop-CodeStruct-Prototype.ps1`.
  - **Step 3:** Launched services and standalone application window via `Start-CodeStruct-Prototype.ps1` (`msedge --app=http://127.0.0.1:5173`). Confirmed borderless standalone window with zero browser tabs or address bar.
  - **Step 4:** Verified running processes: Backend PID `31656`, Frontend PID `19628`, Standalone App Window PID `30664`.
  - **Step 5:** Triggered native folder chooser bridge (`POST /api/v1/host/choose-folder`) and polled automatic initial analysis to completion (`completed`).
  - **Step 6:** Verified directory and nested Python symbol hierarchy (`GET /analyses/{id}/tree`): module `calculator` -> function `compute_discount`, class `InvoiceCalculator` -> methods `calculate_total` and `format_currency` in source order; policy exclusion `nested/.git` reported with reason.
  - **Step 7:** Verified graph architecture hierarchy: 7 nodes, 7 edges; `InvoiceCalculator` located at `nested/domain/calculator.py:8-18`.
  - **Step 8:** Verified architectural explanation: Role: `Isolated Leaf Component`, Summary, Provider: `rule-based`.
  - **Step 9:** Exercised project Refresh: re-analyzed without executing project source code.
  - **Step 10:** Captured real standalone desktop window screenshot via PowerShell to `docs/verification/standalone_window_workflow.png` (5,275 bytes).
  - **Step 11:** Executed clean shutdown via `Stop-CodeStruct-Prototype.ps1` (exit code 0); confirmed zero lingering processes and runtime state file cleared; cleaned up disposable fixture project.

### 3.7 Whitespace and Diff Check
- **Command:** `git diff --check 590a208..HEAD`
- **Exit Code:** `0` (Zero whitespace errors across all commits since baseline).

---

## 4. Commit Progression and Tested-Code Comparison

| Commit | Type | Description |
|---|---|---|
| `590a208` | Baseline | Milestone 7 Review 1 task start baseline |
| `e51cb6c` | Implementation | M7 streaming bounds on Graphviz export (R1) & persistent cache byte budget eviction (R2) |
| `4453ed9` | Implementation | Standalone Windows host launcher lifecycle (`msedge --app`), native folder picker bridge, safe directory and nested Python symbol hierarchy API |
| `40f894d` | Implementation | Standalone workbench UI, top-down hierarchy layout (levels 0-5), `ProjectExplorerTree.tsx`, R3 loaded-slice vs complete DOT export, single dark theme |
| `06258e9` | Documentation | Initial M7 verification reports and tracker updates |
| HEAD | Reconciliation | Scoped verification evidence reconciliation, standalone workflow runner, real window screenshot, and audit sync |

**Commit Comparison Confirmation:**
Tested application code changes were completed at commit `40f894d`. All commits thereafter (`06258e9` and the final reconciliation commit) are strictly documentation, status tracking (`PROCESS_TRACKER.md`, `docs/codestruct_audit.md`), verification scripts (`scripts/verify_real_windows_standalone_workflow.py`), and real desktop screenshot evidence (`docs/verification/standalone_window_workflow.png`). No application code or schema was altered after `40f894d`.

---

## 5. Cleanup Inventory and Review Artifact Status

### 5.1 Frontend Cleanup Inventory
- **Retained Active Source:** `frontend.lovable/` is the active frontend source serving the standalone desktop workbench (configured in `prototype-config.json`).
- **Retained Pre-existing Source:** `frontend/` was evaluated for deletion. Direct code inspection revealed:
  - `tests/test_packaging.py` explicitly tests `"frontend/version.config.js"`.
  - `tools/dependency_report.py` explicitly reads `"frontend/package-lock.json"`.
  - Contract test fixtures in `tests/` reference `frontend/` assets.
  - Deleting `frontend/` would break regression tests and package validation.
- **Exact Removed Paths:** `0` files removed. All live frontend source, package lockfiles, and tests were preserved intact.

### 5.2 Temporary Review Artifacts Verification
- `D:\REP\_codestruct_m7_review.sqlite3`: Verified absent (`Test-Path` returned `False`).
- `D:\REP\_codex_m7_review_tmp_20261013`: Verified absent (`Test-Path` returned `False`).
- Zero task-created temporary databases or directories remain on disk.

---

## 6. Failed Attempts, Untested Cases, and Remaining Limitations

### 6.1 Failed Attempts During Task
1. **UTF-8 BOM in Runtime State:** Reading `prototype-state.json` directly with Python's default UTF-8 encoding raised `JSONDecodeError: Unexpected UTF-8 BOM` because PowerShell writes UTF-8 with BOM (`0xEF, 0xBB, 0xBF`). Resolved by opening runtime state with `encoding="utf-8-sig"`.
2. **Refresh Request Payload Structure:** Initial payload for Refresh re-analysis placed `"refresh": true` inside `"options"`, which was ignored because FastAPI's `CreateAnalysisRequest` schema defines `refresh: bool = False` as a top-level field. Resolved by sending `refresh: True` at the top level of `CreateAnalysisRequest`.
3. **Linter Formatting in Workflow Script:** `scripts/verify_real_windows_standalone_workflow.py` initially lacked `# noqa: S101, S310, S603, S607` and had an unformatted line, causing `ruff check` and `ruff format --check` to report issues. Resolved by adding noqa header, fixing the f-string, and formatting with ruff.

### 6.2 Untested Cases
1. **Multi-DPI Display Environments:** The standalone application window was verified on the primary Windows display at standard scaling; multi-monitor environments with differing per-monitor DPI scaling were not tested.
2. **Non-Windows Desktop Operating Systems:** Standalone `--app` mode and native folder picker bridge (`System.Windows.Forms.FolderBrowserDialog`) are designed specifically for Windows 10/11 desktop. While Tkinter fallback exists for other OSes, non-Windows desktop windowing was not exercised in this Windows-scoped task.
3. **Physical Screen-Reader Acoustic Audio:** Accessibility semantics (CS-022) were verified via DOM ARIA live regions and keyboard event handling; physical audio output through JAWS/NVDA was not manually monitored.

### 6.3 Remaining Limitations
1. **Microsoft Edge Requirement for Standalone Window:** Standalone application window mode requires Microsoft Edge (`msedge.exe`) at standard installation paths. If absent, the prototype launcher logs a warning and falls back to a standard browser tab.
2. **Review Authority Boundary:** Milestone 7 is submitted as **Ready for Codex review (Corrections 1)**; it is not Accepted. Milestone 8 must not begin until Codex review is complete.
