# Verification Report: Thonny Workbench Layout Correction Pass 1

**Date:** 2026-10-22  
**Repository:** `D:\REP\Codestruct\Codestruct`  
**Milestone:** M7 (CS-015, CS-017) — Workbench Layout Correction Pass 1  
**User Evidence:** `D:\REP\changes.png`  
**Author:** Antigravity  
**Reviewer:** Codex  
**Status:** Ready for Codex review (M7 reopened as "Changes required — Thonny workbench layout"; Milestone 8 completed evidence preserved; M7/M8 not marked Accepted)

---

## 1. Executive Summary

In response to the layout defects captured in `D:\REP\changes.png` and specified in `ANTIGRAVITY_THONNY_LAYOUT_TASK.md`, this correction implements a unified, non-duplicated workbench layout entirely inside Thonny:

1. **One Unified Explorer on the Left:**
   - CodeStruct's rich Project Explorer serves as the sole left-hand Explorer, displaying the complete project directory tree and nested Python AST symbols (modules, classes, functions, and methods with 1-indexed line numbers).
   - Thonny's duplicate native `FilesView` pane is automatically hidden when the CodeStruct editor tab is active.
   - When the user switches to a normal source code tab, closes the CodeStruct tab, or exits Thonny, Thonny's native `FilesView` is automatically restored to its prior visibility.
   - Thonny's active directory tracking (`files_view.get_active_local_dir()`) is preserved even when `FilesView` is hidden.
   - Thonny's layout preferences are not permanently altered.
   - Both the top toolbar "Explorer" button and the in-drawer collapse chevron icon allow smoothly collapsing and reopening the Explorer.

2. **One Bottom Shell/Diagnostics Surface:**
   - Thonny's native `ShellView` serves as the sole bottom Shell and Diagnostics surface.
   - The redundant, cramped docked-bottom-panels (`<section data-purpose="docked-bottom-panels">`) and status bar (`<footer data-purpose="system-statusbar">`) have been removed from the embedded web tab content.
   - CodeStruct analysis status, structured symbol counts breakdown, and AST diagnostic messages are streamed directly to Thonny's native Shell using Thonny's `ShellText._insert_text_directly(text, ("io", stream))` API.
   - Diagnostic messages formatted with standard `File "...", line ..., col ...` syntax are recognized and highlighted by Thonny's native Shell as clickable stacktrace hyperlinks.
   - In-IDE source navigation events and error notices are similarly printed to Thonny's native Shell.

3. **Full-Height Inspector on the Right:**
   - The right Inspector drawer is open by default and fills the entire vertical height from the workbench header toolbar to the bottom of the editor tab.
   - The large blank strip below the inspector shown in `changes.png` has been completely eliminated.
   - When no node or edge is selected, the Inspector renders a rich **Architecture Overview** card featuring:
     - Real-time symbol count badges (Modules, Classes, Functions, Methods).
     - Project root canonical path.
     - Relationship and evidence metrics counts.
     - Explicit **Static Non-Execution Guarantee** confirmation notice.
     - **Integrated Thonny Shell** notice informing users that diagnostic and log messages are streamed to the native Shell below.
     - Interactive symbol inspection guide.
   - When any node or edge is selected, the Inspector continues to present comprehensive node details, qualified paths, line pointers, defined symbols, bidirectional relationships, evidence records, and the "Jump to Source in Editor" action.
   - Both the top toolbar "Inspector" button and the in-drawer collapse chevron icon smoothly toggle the Inspector drawer.

4. **All Behavior Inside Thonny Main Window:**
   - No external browser windows or detached dialogs are spawned.
   - Multi-project switching (Alpha to Beta) updates the active CodeStruct tab in place without duplicate tabs or stale data.
   - Non-execution safety invariant strictly verified: user and fixture code is parsed into ASTs, never imported or executed (`sys.modules` clean; hostile `danger.py` marker never invoked).

---

## 2. Screenshot-Based Failure and Root Cause Analysis

### A. Defect Evidence in `D:\REP\changes.png`
1. **Duplicate Explorers on the Left:**
   Thonny displayed its native `Files` pane on the left showing local files, while immediately adjacent inside the editor tab, CodeStruct rendered its own Project Explorer with duplicate directory structures.
2. **Duplicate Bottom Shell & Diagnostics:**
   Thonny displayed its native `Shell` pane at the bottom of the window, while the CodeStruct editor tab additionally included a collapsed/docked bottom drawer with "Terminal Shell" and "Diagnostics" tabs, duplicating surfaces and reducing the vertical height available for graph analysis.
3. **Truncated Inspector & Blank Strip on the Right:**
   The Inspector pane in the embedded workbench terminated abruptly, leaving a large, unused blank grey area beneath it and creating visual clutter. When no symbol was selected, the Inspector showed minimal or empty content.

### B. Root Causes
1. **Unsynchronized View Lifecycle:** The Thonny plugin previously initialized `FilesView` without hiding it when the CodeStruct editor tab gained focus or opened, nor did it listen for `<<NotebookTabChanged>>` events on Thonny's `EditorNotebook`.
2. **Redundant Web Panels:** The frontend workbench component (`workbench.tsx`) retained legacy `docked-bottom-panels` and `system-statusbar` markup ported from the standalone web application.
3. **Height Constraints and Empty State:** In `workbench.tsx`, flex containers were constrained by bottom dock structures, and the Inspector had no dedicated full-height default state when `!node && !edge`.

---

## 3. Scoped Modifications

### A. Frontend (`frontend.lovable/src/features/workbench.tsx`)
1. **Removed Redundant Panels:**
   - Deleted `<section data-purpose="docked-bottom-panels">` and `<footer data-purpose="system-statusbar">`.
   - Removed unneeded state variables (`dockOpen`, `dockTab`, `activeDiag`, `shownDiagnostics`) and corresponding action handlers.
2. **Implemented Full-Height Architecture Overview Card in Inspector:**
   - When no node or edge is selected, `Inspector` renders a full-height Architecture Overview component displaying:
     - Project root canonical path and total AST symbol badge.
     - Grid metrics: Module, Class, Function, and Method counts.
     - Relationship and evidence record tallies.
     - Static Non-Execution Guarantee badge.
     - Integrated Thonny Shell notice with real-time diagnostic count indicator.
     - Interactive symbol inspection guide.
3. **Preserved Node Details & Relationship Navigation:**
   - When a node is selected, full details (label, kind, qualified name, line pointer, "Jump to Source in Editor", defined symbols, relationships, observed evidence) occupy the full available height with custom smooth scrolling.
4. **Compiled Assets:**
   - Rebuilt frontend with `npm run build` and copied artifacts (`index.html`, `index-*.js`, `index-*.css`) into `backend/src/codestruct/web/`.

### B. Backend (`backend/src/codestruct/jobs/service.py` & `api/routes/navigate.py`)
1. **Shell Message Queueing in `service.py`:**
   - Added thread-safe shell message buffer `self._shell_messages: dict[str, list[dict[str, Any]]]`.
   - Added `queue_shell_message(session_token, text, stream)`.
   - Added `get_pending_shell_messages(session_token)` and `acknowledge_shell_messages(session_token, message_ids)`.
2. **Editor API Endpoints in `navigate.py`:**
   - Added `POST /api/v1/editor/shell-message`: allows queuing status and diagnostic messages for Thonny.
   - Added `GET /api/v1/editor/shell-messages/pending`: allows Thonny plugin to poll pending shell messages.
   - Added `POST /api/v1/editor/shell-messages/acknowledge`: consumes delivered messages.

### C. Thonny Plugin (`thonny-plugin/thonnycontrib/codestruct/__init__.py`)
1. **Native FilesView Hide & Restore Lifecycle:**
   - Implemented `is_files_view_visible(wb)`: inspects whether Thonny's `FilesView` has an active `containing_notebook`.
   - Implemented `_hide_files_pane(wb)`: uses `wb.hide_view("FilesView")` to detach Thonny's native Files pane while CodeStruct is active, recording prior user visibility state.
   - Implemented `_restore_files_pane(wb)`: uses `wb.show_view("FilesView", set_focus=False)` to re-attach the native Files pane whenever switching away from CodeStruct or closing the tab.
   - Implemented `_on_editor_tab_changed(wb)`: hooks into `<<NotebookTabChanged>>` to automatically hide `FilesView` when CodeStruct is active, and restore it when a standard Python source tab is active.
   - Added tab lifecycle bindings in `_bind_editor_notebook_events(wb)` called during `load_plugin()`, `WorkbenchOpen`, and `open_codestruct_workbench()`.
   - Guaranteed restoration on tab close, destroy, and workbench shutdown (`on_workbench_shutdown`).
2. **Native ShellView Diagnostics & Status Streaming:**
   - Implemented `print_to_thonny_shell(wb, text, stream)`: safely writes output to Thonny's native `ShellView.text` on the Tk main thread using `_insert_text_directly(text, ("io", stream))` and scrolls to end.
   - Implemented `_report_analysis_to_shell(wb, backend_url, analysis_id, folder_name)`: runs in a daemon thread, polls analysis completion, and streams formatted summary (symbol counts breakdown, zero execution guarantee) and AST diagnostics (`File "...", line ..., col ...: [SEV] CODE - MSG`).
   - Integrated shell message polling into the existing `_do_poll` loop to deliver real-time messages from the backend to Thonny's Shell.
3. **Navigation Feedback to Shell:**
   - Updated `_execute_navigate`: prints successful source file jumps (`[CodeStruct] Navigated to File "...", line ..., col ...`) or errors directly to Thonny's native Shell.

---

## 4. Real Windows Thonny Verification & Steps

The end-to-end verification was executed in the real Windows environment using the automated test suite `scripts/verify_real_thonny_layout_correction.py` and real browser verification.

### Test Execution Log Summary
```
[1/10] Starting CodeStruct backend on http://127.0.0.1:8000...
Backend is healthy and responding.
[2/10] Starting CodeStruct frontend preview on http://127.0.0.1:5173...
Frontend is healthy and responding.
[3/10] Creating disposable nested fixtures (Alpha & Beta)...
Fixtures created successfully.
[4/10] Initializing real Thonny Workbench with FilesView & ShellView...
Verified: FilesView is initially visible before CodeStruct launch.
Plugin loaded into real Thonny workbench.
[5/10] Launching CodeStruct workbench for Project Alpha & verifying pane lifecycle...
PASS: Exactly ONE Explorer on the left: Thonny native FilesView is hidden, CodeStruct Explorer active.
PASS: Exactly ONE bottom Shell/Diagnostics surface: Native Thonny Shell received CodeStruct diagnostics.
[6/10] Testing Tab Switching: Switch to normal source tab...
PASS: Switching to normal source tab automatically RESTORED Thonny's native FilesView.
Switching back to CodeStruct tab...
PASS: Switching back to CodeStruct tab automatically RE-HID Thonny's native FilesView.
[7/10] Testing Multi-Project Switching to Project Beta...
PASS: Project Beta opened cleanly without duplicate tabs, FilesView remains hidden.
[8/10] Testing Responsive Resize: Narrow viewport (1024x700)...
PASS: Window resized to 1024x700 and rendered cleanly.
[9/10] Testing Tab Close Lifecycle...
PASS: Closing CodeStruct tab cleanly removed tab and RESTORED native FilesView.
[10/10] Verifying Static Non-Execution Safety Invariant...
PASS: Static non-execution safety invariant strictly maintained.
PASS: Thonny Workbench cleanly destroyed.
ALL REAL THONNY WORKBENCH LAYOUT VERIFICATIONS PASSED 100%!
```

### Visual Verification Evidence (Screenshots)

1. **Initial Thonny Window with Source Files & Native FilesView (1400x825):**  
   `docs/verification/screenshots/thonny_layout_01_initial_source_files.png`  
   *Verified: Thonny starts with native `Files` view on the left and open source tabs.*

2. **Unified CodeStruct Workbench Active for Project Alpha (1400x825):**  
   `docs/verification/screenshots/thonny_layout_02_unified_workbench_alpha.png`  
   *Verified: Exactly ONE left Explorer (CodeStruct Explorer active; native FilesView hidden); exactly ONE bottom Shell (native Thonny Shell received CodeStruct status and diagnostics).*

3. **Switching to Source Tab Restores Native FilesView (1400x825):**  
   `docs/verification/screenshots/thonny_layout_03_source_tab_restores_files.png`  
   *Verified: Clicking `main.py` tab immediately restores Thonny's native `Files` pane with full project folder tree.*

4. **Switching Back to CodeStruct Tab Re-Hides Native FilesView (1400x825):**  
   `docs/verification/screenshots/thonny_layout_04_tab_switched_back_hides_files.png`  
   *Verified: Switching back to `CodeStruct` editor tab automatically re-hides the native `Files` pane.*

5. **Multi-Project Switching to Project Beta (1400x825):**  
   `docs/verification/screenshots/thonny_layout_05_project_beta_switch.png`  
   *Verified: Switching File view to Project Beta smoothly updates the existing CodeStruct tab to `disposable_beta_pipeline` without duplicate tabs. Native Thonny Shell streams updated analysis for Project Beta.*

6. **Responsive Resize to Narrow Viewport (1024x700):**  
   `docs/verification/screenshots/thonny_layout_06_narrow_viewport.png`  
   *Verified: Workbench adapts smoothly at 1024x700 without overflow.*

7. **Closing CodeStruct Tab Restores Native FilesView (1400x825):**  
   `docs/verification/screenshots/thonny_layout_07_tab_closed_restores_files.png`  
   *Verified: Closing the CodeStruct tab immediately restores Thonny's native `Files` pane for regular editing.*

8. **Full-Height Inspector & Architecture Overview Card (1366x768 Web UI):**  
   `docs/verification/screenshots/workbench_initial_overview.png`  
   *Verified: Left Explorer shows full folder/file tree with AST symbols and line numbers; right Inspector spans complete vertical height from toolbar to bottom with Architecture Overview cards, zero-execution guarantee, and Thonny Shell routing notice; zero blank strip; zero bottom panels.*

9. **Inspected Node Details (1366x768 Web UI):**  
   `docs/verification/screenshots/workbench_symbol_inspected.png`  
   *Verified: Selecting a symbol (Calculator class) presents qualified name, source pointer, jump to source, defined symbols, bidirectional relationships, and evidence records filling the entire height.*

10. **Drawer Toggle Collapse States:**  
    `docs/verification/screenshots/workbench_explorer_collapsed.png`  
    `docs/verification/screenshots/workbench_inspector_collapsed.png`  
    *Verified: Left Explorer and right Inspector drawers collapse and reopen cleanly using both top toolbar buttons and in-drawer chevron icons.*

---

## 5. Quality Gates & Regression Verification

All quality gates passed cleanly with zero regressions:

| Gate | Command | Result | Metrics / Notes |
|------|---------|--------|-----------------|
| **Thonny Plugin Tests** | `pytest thonny-plugin/tests --no-cov -q` | **PASS** | 73 passed, 1 skipped (Windows symlink) in 7.63s |
| **Backend Tests & Coverage** | `pytest --cov=backend/src/codestruct --cov-fail-under=84 -q` | **PASS** | 342 passed, 2 skipped; **84.32%** coverage (exceeds 84% floor) |
| **Frontend Unit Tests** | `npm --prefix frontend.lovable run test` | **PASS** | 10 passed, 1 skipped in 2.37s |
| **Frontend Typecheck** | `npm --prefix frontend.lovable run typecheck` | **PASS** | `tsc -p tsconfig.integration.json` clean (0 errors) |
| **Frontend Build** | `npm --prefix frontend.lovable run build` | **PASS** | Built in 6.63s; copied to `backend/src/codestruct/web/` |
| **Python Linting** | `ruff check backend tests thonny-plugin` | **PASS** | All checks passed (0 errors) |
| **Python Formatting** | `ruff format --check backend tests thonny-plugin` | **PASS** | 102 files already formatted |
| **Python Typecheck** | `mypy --config-file pyproject.toml` | **PASS** | Success: 0 issues in 57 source files |
| **Git Diff Cleanliness** | `git diff --check` | **PASS** | 0 whitespace errors, 0 conflict markers |

---

## 6. Limitations & Preserved Invariants

1. **Static Non-Execution Invariant:** Source code in user and fixture projects is strictly parsed via AST and never imported, executed, or evaluated. Verified via `danger.py` marker module check across all test phases.
2. **Thonny View Configuration Integrity:** `wb.hide_view("FilesView")` and `wb.show_view("FilesView", set_focus=False)` manipulate live notebook pages without modifying `layout.notebook_*.views` options, ensuring Thonny preferences remain intact.
3. **Single Window Invariant:** Thonny IDE remains the sole user-facing window.
4. **Milestone Boundaries:** Milestone M7 is updated to "Changes required — Thonny workbench layout" in tracking documents; M8 completed evidence is preserved; neither M7 nor M8 is marked Accepted. No packages published, no releases created.
