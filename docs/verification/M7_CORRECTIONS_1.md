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

### 3.1 Backend Test Suite (Pytest)
```
================= 319 passed, 2 skipped, 2 warnings in 34.33s =================
Required test coverage of 84% reached. Total coverage: 85.54%
```
- Total tests: 319 passed, 2 skipped (Windows sandbox directory link / symlink tests).
- Code coverage: **85.54%** (exceeds repository gate of 84.00%).

### 3.2 Static Linters and Type Checking
- **Ruff Lint:** `All checks passed!`
- **Ruff Format:** `89 files already formatted`
- **Mypy:** `Success: no issues found in 55 source files`

### 3.3 End-to-End M7 Verification Script
`scripts/verify_m7_cache_export.py` executed cleanly:
```
[M7 Verify] Scenario 1: Cold Analysis on Mutable Project...
  -> Cold run completed: 3 files cached in file_parse_cache table.
[M7 Verify] Scenario 2A: Whole-Result Cache Hit...
  -> Whole-result whole-graph cache hit returned 200 with cache_hit=True.
[M7 Verify] Scenario 2B: Warm Analysis via Worker with Per-File Cache Reuse...
  -> Warm worker run completed in 1.108s with identical graph (15 nodes).
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
OVERALL STATUS: SUCCESS (Total time: 4.73s)
```

### 3.4 Frontend Verification Suite (Vitest)
```
Test Files  1 passed | 1 skipped (2)
     Tests  10 passed | 1 skipped (11)
  Duration  2.41s
```
- 10 unit and integration tests passing in `frontend.lovable/src/features/integration.test.tsx`.

### 3.5 Frontend Build
`vite build` executed cleanly with 0 warnings or errors, generating production bundles in `dist/`.

### 3.6 Whitespace and Diff Check
`git diff --check` executed with code 0 across the entire repository.

---

## 4. Commits Included in Corrections
- `e51cb6c`: `fix(m7): enforce streaming bounds on graphviz export and byte capacity on parse cache`
- `4453ed9`: `feat(explorer): add standalone windows host, whole-folder explorer, and nested python symbols`
- `40f894d`: `feat(ui): integrate standalone workbench, remove redundant frontend assets, and record verification`
