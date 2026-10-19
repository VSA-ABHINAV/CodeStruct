# Thonny Stitch Editor Tab Integration Verification Report

**Date:** 2026-10-19  
**Status:** Ready for Codex Review (Thonny Editor-Tab Integration)  
**Authority Reference:** `ANTIGRAVITY_TASK.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`  
**Prior Review Reference:** `docs/verification/STITCH_FRONTEND_INTEGRATION_CODEX_REVIEW_1.md`  
**Visual Design Reference:** Stitch.ai Project `projects/3997374805666523009`, Screen `94361047d60944b0ab44bfb463329efb` ("Thonny IDE - Docked CodeStruct Architecture Workbench", Desktop 2560x2048)  
**Safety Invariant:** Static non-execution invariant strictly maintained (analyzed source code is NEVER imported or executed).

---

## 1. Executive Summary & Objective

In accordance with `ANTIGRAVITY_TASK.md` and the findings from `docs/verification/STITCH_FRONTEND_INTEGRATION_CODEX_REVIEW_1.md`, CodeStruct has been corrected from a standalone Edge/Chrome window into a **real Thonny editor tab** docked inside the main Thonny IDE window:

1. **Native Thonny Extension Point:** Implemented `CodeStructEditorTab(Editor)` hosted inside Thonny's `EditorNotebook` (`get_workbench().get_editor_notebook()`), embedding a WebView2 child control via `tkwry.WebView` inside a dedicated child container frame.
2. **Tools Menu Launch:** Accessible directly from Thonny's menu via `Tools → CodeStruct` (`command_id="codestruct"`).
3. **Active Directory Root Binding:** The project root is queried directly from Thonny's File view (`FilesView.local_files.current_focus`). Zero separate folder picker dialogs (`FolderBrowserDialog`, Tk file dialogs) are ever displayed.
4. **Missing-Folder In-IDE Guard:** If no folder is open in File view, an in-IDE info dialog (`showinfo("No Folder Open in File View", ...)`) alerts the user without launching or falling back to arbitrary folders.
5. **Multi-Folder Switching Without Tab Duplication:** When the user changes folders in File view and invokes `Tools → CodeStruct`, the existing `CodeStructEditorTab` is smoothly re-anchored to the new project via `update_url()`, updating the tab title and registering the new root with the backend without creating duplicate tabs.
6. **Elimination of Fake Outer Desktop Chrome:** In the web workbench, the simulated OS window titlebar, desktop menubar, outer toolbar, and outer tab strip were completely stripped. The workbench content is housed in a docked header containing CodeStruct branding, project path badge, symbol search, Refresh, View Mode toggle, Drawer controls, and status indicator.
7. **Two-Way In-IDE Navigation:** Selecting nodes or members in the workbench navigates back to Thonny, opening the target source file at the exact line via `wb.get_editor_notebook().show_file_at_line(...)` after verifying canonical containment within `_nav_registered_root`.
8. **Static Non-Execution Invariant:** Source code is analyzed exclusively using static AST parsing. A hostile canary sentinel script with execution traps was included in test fixtures and verified untouched.
9. **Full Automated Workflow & Gates:** All 10 verification steps in `scripts/verify_real_thonny_stitch_tab_workflow.py` executed and passed on real Windows with 100% success. All backend, plugin, and frontend quality gates pass with zero regressions.

---

## 2. Architecture & Implementation Details

### 2.1 Backend Folder Registration (`backend/src/codestruct/api/routes/host.py`)

A new non-interactive API endpoint was introduced for IDE-driven root registration:
- **Route:** `POST /api/v1/host/register-folder`
- **Request Body:** `RegisterFolderRequest(path: str)`
- **Behavior:**
  - Validates that `path` is an existing, canonical directory on the local host.
  - Registers the directory in `authorized_roots` and obtains its deterministic `root_id`.
  - Spawns an initial asynchronous background analysis job (`create_analysis_job_for_root`).
  - Returns `RegisterFolderResponse(status="ok", root_id=..., folder_path=..., analysis_id=...)` immediately without blocking or prompting the user.
- **Unit Regressions:** Added 6 tests in `tests/test_host.py` covering successful registration, repeat registration reuse, path disambiguation, invalid path rejection (400), authentication rejection (401), and non-execution safety.

### 2.2 Thonny Plugin Docked Tab (`thonny-plugin/thonnycontrib/codestruct/__init__.py`)

- **Class `CodeStructEditorTab(Editor)`:**
  - Inherits from Thonny's `Editor` widget (`thonny.editors.Editor`), allowing it to be managed seamlessly by Thonny's `EditorNotebook`.
  - Hosts a child `tk.Frame` which encapsulates `tkwry.WebView`, preventing geometry manager conflicts (`pack` inside grid-managed notebook).
  - Uses an isolated data directory (`Path(tempfile.gettempdir()) / "codestruct_thonny_webview"`).
  - Implements Thonny's editor interface methods: `get_title()`, `get_uri()`, `get_target_path()`, `is_local()`, `is_modified()`, `save_file_enabled()`, `focus_set()`, `close()`, `destroy()`, and `update_url()`.
  - Provides `DummyCodeView` and dummy text widget to satisfy Thonny's internal focus and view queries without instantiating an unneeded source text editor.
- **File View Discovery (`get_file_view_folder`):**
  - Queries `wb.get_view("FilesView", create=False)`.
  - Inspects `files_view.local_files.current_focus` to obtain the directory currently open in the tree.
  - If unset or invalid, cleanly returns `None`.
- **Workbench Tab Opener (`open_codestruct_workbench`):**
  - Resolves active folder from `get_file_view_folder(wb)`.
  - If `None`, calls `messagebox.showinfo("No Folder Open in File View", ...)` and aborts.
  - Calls `POST /api/v1/host/register-folder` to register the folder with CodeStruct backend.
  - Generates handoff URL with `embed=thonny` and `projectId=<root_id>`.
  - Inspects `editor_notebook.winfo_children()`:
    - If a `CodeStructEditorTab` already exists, invokes `existing_tab.update_url(viewer_url, canonical_folder_str)` and selects the tab.
    - Otherwise, creates a new `CodeStructEditorTab`, adds it via `editor_notebook.add(...)`, and selects it.
  - Registers the folder with `_nav_registered_root` and starts navigation polling.
- **Tools Menu Registration:**
  - Registered `Tools → CodeStruct` (`command_id="codestruct"`, label="CodeStruct", handler=`open_codestruct_workbench`).
  - Preserved `Tools → Analyze Project with CodeStruct` (`command_id="codestruct_analyze"`) for active file analysis.

### 2.3 Docked Frontend Workbench (`frontend.lovable/src/features/workbench.tsx` & `useWorkbench.ts`)

- **Handoff Query Parsing (`useWorkbench.ts`):**
  - `captureHandoff()` captures `projectId` and `embed` parameters from the viewer URL.
  - Automatically initializes active project state and strips parameters from URL cleanly.
- **Docked Header & Clean Workbench Canvas (`workbench.tsx`):**
  - Removed simulated OS titlebar (`.window-titlebar`), fake menu bar (`.window-menubar`), fake desktop toolbar, and fake outer tab strip.
  - Implemented `.workbench-header`:
    - CodeStruct brand icon and title badge.
    - Active project root path badge (`activeProject.path` or active folder name).
    - Quick symbol/file search input.
    - Refresh button connected to `load(true)` for re-analysis.
    - View mode switcher (Graph / Accessible table).
    - Left drawer toggle (Project Explorer) and right drawer toggle (Inspector).
    - Connection status indicator.
  - Main body contains the blueprint dot grid canvas with interactive graph, left explorer drawer, and right inspector drawer.

---

## 3. Automated Workflow Verification Evidence

The end-to-end integration was exercised on the live Windows environment using `scripts/verify_real_thonny_stitch_tab_workflow.py`. The script tests 10 distinct verification steps:

```
2026-10-19 22:36:18,188 [INFO] =================================================================
2026-10-19 22:36:18,188 [INFO] STARTING REAL THONNY STITCH WORKBENCH TAB INTEGRATION TEST
2026-10-19 22:36:18,188 [INFO] =================================================================
2026-10-19 22:36:18,188 [INFO] [1/10] Starting CodeStruct backend on http://127.0.0.1:8000...
2026-10-19 22:36:20,237 [INFO] Backend is healthy and responding.
2026-10-19 22:36:20,237 [INFO] [2/10] Starting CodeStruct frontend preview on http://127.0.0.1:5173...
2026-10-19 22:36:22,189 [INFO] Frontend is healthy and responding.
2026-10-19 22:36:22,189 [INFO] [3/10] Creating disposable fixtures (Alpha & Beta)...
2026-10-19 22:36:22,209 [INFO] Fixtures created:
  Alpha: C:\Users\ABHINAV\AppData\Local\Temp\tmpf0zt0rht\disposable_alpha_project
  Beta: C:\Users\ABHINAV\AppData\Local\Temp\tmpf0zt0rht\disposable_beta_pipeline
2026-10-19 22:36:22,209 [INFO] [4/10] Initializing real Thonny Workbench with FilesView & EditorNotebook...
2026-10-19 22:36:24,961 [INFO] CodeStruct Thonny plugin loaded successfully
2026-10-19 22:36:24,961 [INFO] Plugin loaded into real Thonny workbench.
2026-10-19 22:36:24,961 [INFO] [5/10] Testing Phase 1: Launch CodeStruct workbench for Fixture Alpha...
2026-10-19 22:36:24,962 [INFO] focus_into 'C:\Users\ABHINAV\AppData\Local\Temp\tmpf0zt0rht\disposable_alpha_project'
2026-10-19 22:36:25,888 [INFO] PASS: Tab docked in Thonny main window, rooted in disposable_alpha_project
2026-10-19 22:36:25,888 [INFO] Allowing WebView2 4 seconds to render Alpha workbench...
2026-10-19 22:36:30,322 [INFO] Screenshot saved via PrintWindow: D:\REP\Codestruct\Codestruct\docs\verification\screenshots\thonny_tab_fixture_alpha.png (1400x825)
2026-10-19 22:36:30,323 [INFO] [6/10] Testing Multi-Folder Switching: Switch File view to Fixture Beta...
2026-10-19 22:36:30,324 [INFO] focus_into 'C:\Users\ABHINAV\AppData\Local\Temp\tmpf0zt0rht\disposable_beta_pipeline'
2026-10-19 22:36:30,487 [INFO] PASS: Existing tab smoothly updated to Fixture Beta without creating a duplicate tab.
2026-10-19 22:36:30,487 [INFO] Allowing WebView2 4 seconds to render Beta workbench...
2026-10-19 22:36:34,856 [INFO] Screenshot saved via PrintWindow: D:\REP\Codestruct\Codestruct\docs\verification\screenshots\thonny_tab_fixture_beta.png (1400x825)
2026-10-19 22:36:34,857 [INFO] [7/10] Testing In-IDE Source Navigation back to Thonny...
2026-10-19 22:36:35,022 [INFO] PASS: Navigation correctly opened beta_pipeline.py in Thonny at line 4.
2026-10-19 22:36:35,834 [INFO] Screenshot saved via PrintWindow: D:\REP\Codestruct\Codestruct\docs\verification\screenshots\thonny_navigated_source_file.png (1400x825)
2026-10-19 22:36:35,835 [INFO] [8/10] Testing Missing-Folder Guard...
2026-10-19 22:36:35,837 [INFO] Verified in-IDE info dialog: 'No Folder Open in File View': No project folder is currently open in Thonny's File view.
2026-10-19 22:36:35,837 [INFO] PASS: Missing folder alert displayed, no fallback root used.
2026-10-19 22:36:35,837 [INFO] [9/10] Verifying Static Non-Execution Safety Invariant...
2026-10-19 22:36:35,837 [INFO] PASS: Source code was NEVER executed during analysis or folder switching.
2026-10-19 22:36:35,837 [INFO] [10/10] Testing Tab Close & Shutdown...
2026-10-19 22:36:35,971 [INFO] PASS: CodeStruct tab closed cleanly without errors.
2026-10-19 22:36:36,167 [INFO] PASS: Thonny Workbench cleanly destroyed.
2026-10-19 22:36:36,167 [INFO] =================================================================
2026-10-19 22:36:36,167 [INFO] ALL REAL THONNY WORKBENCH TAB INTEGRATION TESTS PASSED 100%!
2026-10-19 22:36:36,168 [INFO] =================================================================
2026-10-19 22:36:36,170 [INFO] Backend process terminated.
2026-10-19 22:36:36,431 [INFO] Frontend process terminated.
```

---

## 4. Visual Evidence & Screenshots

The verification workflow automatically captured high-resolution window screenshots directly from the live Thonny IDE session:

### 4.1 Thonny Editor Tab Docked with Fixture Alpha
The CodeStruct tab is docked inside Thonny's `EditorNotebook`, rooted in `disposable_alpha_project`.
![Thonny Docked Tab - Fixture Alpha](file:///D:/REP/Codestruct/Codestruct/docs/verification/screenshots/thonny_tab_fixture_alpha.png)

### 4.2 Smooth Multi-Folder Switch to Fixture Beta
File view navigated to `disposable_beta_pipeline`. Invoking `Tools → CodeStruct` smoothly refreshed the existing tab without tab duplication.
![Thonny Docked Tab - Fixture Beta Switch](file:///D:/REP/Codestruct/Codestruct/docs/verification/screenshots/thonny_tab_fixture_beta.png)

### 4.3 In-IDE Navigation Opening Source in Thonny Editor
Selecting an architectural node navigated back to Thonny, opening `beta_pipeline.py` at line 4 inside Thonny's code view.
![Thonny In-IDE Source Navigation](file:///D:/REP/Codestruct/Codestruct/docs/verification/screenshots/thonny_navigated_source_file.png)

---

## 5. Quality Gates Summary

All regression and quality gates were executed across backend, plugin, and frontend codebases:

| Quality Gate | Command | Result | Details |
|---|---|---|---|
| **Backend Unit & API Tests** | `.venv\Scripts\pytest tests/ --cov=backend/src --cov-fail-under=84` | **PASSED** | 323 passed, 2 skipped, 0 failed. Total coverage: **84.49%** (>= 84.00% requirement). |
| **Thonny Plugin Tests** | `.venv\Scripts\pytest --no-cov thonny-plugin/tests` | **PASSED** | 66 passed, 1 skipped, 0 failed. |
| **Backend Lint** | `.venv\Scripts\ruff check backend thonny-plugin` | **PASSED** | All checks passed cleanly with 0 warnings/errors. |
| **Backend Type Check** | `.venv\Scripts\mypy backend/src` | **PASSED** | Success: 0 issues found in 55 source files. |
| **Frontend Type Check** | `npm --prefix frontend.lovable run typecheck` | **PASSED** | Exit code 0, 0 TypeScript diagnostic errors. |
| **Frontend Unit Tests** | `npm --prefix frontend.lovable test` | **PASSED** | 10 passed, 1 skipped (11 total across 2 test files). |
| **Frontend Production Build** | `npm --prefix frontend.lovable run build` | **PASSED** | Built in 771ms, 0 errors. |
| **Frontend ESLint** | `npm --prefix frontend run lint` | **PASSED** | Exit code 0, 0 lint errors/warnings. |
| **Real Thonny Tab Workflow** | `thonny\venv\Scripts\python.exe scripts/verify_real_thonny_stitch_tab_workflow.py` | **PASSED** | All 10 integration stages passed 100%. |

---

## 6. Commitments & Status

- **Milestone 7 Status:** READY FOR CODEX REVIEW.
- **Milestone 8 Status:** Not started.
- **Safety Invariant:** Maintained.
- **Git State:** Local commits prepared; remote push omitted.
