# Thonny Stitch Editor Tab Integration — Correction Report 1

Date: 2026-10-20  
Repository: `D:\REP\Codestruct\Codestruct`  
Branch: `main`  
Author: Antigravity  
Status: **Ready for Codex review** (Milestone 7 remains unaccepted; Milestone 8 not started; no push performed)  
Task reference: [`ANTIGRAVITY_TASK.md`](file:///d:/REP/Codestruct/Codestruct/ANTIGRAVITY_TASK.md) — *Current correction follow-up (2026-10-20)*  

---

## 1. Executive Summary & Problem Addressed

On 2026-10-20, the user reported that the prior 2026-10-19 result did not meet workspace requirements:
1. **Switchable Editor Tab:** CodeStruct must open as a native, switchable editor tab inside Thonny's existing main window, behaving like any other source document in Thonny's `EditorNotebook`. The user must be able to switch back and forth between existing open source code tabs (e.g. `main.py`, `analytics.py`) and the CodeStruct tab without errors, crashes, or unmanaged widgets.
2. **Whole-Folder Project Scope:** The CodeStruct tab must analyze and display the **whole project folder** currently open in Thonny's File view recursively (subpackages, modules, classes, methods, functions), not just a single active editor file or selected file.
3. **File-to-Folder Resolution:** If Thonny's File view is currently pointed at or has selected a specific file, the integration must determine the containing folder root using Thonny's supported API (`get_active_local_dir` / `get_active_directory`) and analyze the full containing project, never analyzing only that single file.
4. **Missing-Folder Guard:** If no folder is open in File view, show an in-IDE explanation dialog and do not fall back to active files, demo roots, fixtures, or folder choosers.
5. **Multi-Folder Switching:** Switching to a second project in Thonny's File view must smoothly update the single CodeStruct tab without tab duplication or stale data from the previous project.

All requirements have been reproduced, fixed, verified in real Thonny with realistic nested multi-file fixtures, and confirmed via automated end-to-end tests and quality gates.

---

## 2. Root Cause Analysis & Reproduction

### Root Cause 1: Editor Notebook Tab Switching Failures in Thonny Host
- **Observation:** When Thonny's `EditorNotebook` switched between open source file tabs and the `CodeStructEditorTab`, Thonny invoked internal editor callbacks:
  - `editor.update_appearance()` called `self._code_view.set_gutter_visibility(...)`.
  - `editor.get_long_description()` called `uri_to_long_title(self._uri)`.
  - `wb.start_or_restart_language_servers()` inspected editor targets and URIs.
- **Defects in prior code:**
  - `DummyCodeView` lacked `set_gutter_visibility(self, visible)`, `set_line_length_margin`, and text widget dummy attributes, causing `AttributeError: 'DummyCodeView' object has no attribute 'set_gutter_visibility'` upon tab switching.
  - `CodeStructEditorTab` lacked `self._uri = f"codestruct://{self.project_path}"`, causing `AttributeError: 'CodeStructEditorTab' object has no attribute '_uri'`.
  - `CodeStructEditorTab.is_local()` returned `True` (inherited default), causing Thonny's language server proxies and file-change monitors to treat the project root directory as a local Python source file buffer.
- **Fix:**
  - Implemented `DummyCodeViewText` and `DummyCodeView` with full mock method suites (`set_gutter_visibility`, `set_line_length_margin`, `grid_main_widgets`, `set_file_type`, `set_content`, `get_content`, `focus_set`, text widget attributes).
  - Explicitly defined `self._uri = f"codestruct://{self.project_path}"` on `CodeStructEditorTab`.
  - Overrode `is_local() -> False`, `is_remote() -> False`, `is_untitled() -> False`, `is_modified() -> False`, `save_file_enabled() -> False`, `check_for_external_changes() -> None`, `update_appearance() -> None`, and `update_file_type() -> None`.

### Root Cause 2: Single-File Scope vs Whole-Folder Scope
- **Observation:** In prior code, `get_file_view_folder` inspected `files_view.local_files.current_focus`. If the user clicked a file in Thonny's File view, `current_focus` was a file path. If `current_focus` was unset or a file, the system could fail to detect the containing folder. Furthermore, `load_plugin` was still registering `codestruct_analyze` ("Analyze with CodeStruct"), which specifically registered the active single editor file.
- **Fix:**
  - Updated `get_file_view_folder` to use Thonny's official supported API:
    1. Primary: `files_view.get_active_local_dir()`.
    2. Fallback: `files_view.local_files.get_active_directory()`.
    3. Final fallback: `files_view.local_files.current_focus`.
  - In all cases, if the detected path is a file (`p.is_file()`), it immediately resolves to its parent containing folder (`p = p.parent`).
  - Strict type checking ensures `MagicMock` instances in unit tests or non-string attributes are never treated as valid paths.
  - Removed `codestruct_analyze` from `load_plugin()`; only `Tools → CodeStruct` (`open_codestruct_workbench`) is registered.

### Root Cause 3: WebView2 User Data Directory Lock Contention
- **Observation:** When `tkwry.WebView` was initialized without a unique user data folder, Windows WebView2 collided on directory locks across sessions or processes, raising `0x800700AA (The requested resource is in use)` or `0x80070005 (Access is denied)`.
- **Fix:** Assigned a PID-isolated user data folder: `Path(tempfile.gettempdir()) / f"codestruct_thonny_webview_{os.getpid()}"`, preventing lock collisions while allowing clean sharing within the Thonny host process.

---

## 3. Real Thonny Workflow & Verification Results

Verification was performed on real Windows using [`scripts/verify_real_thonny_stitch_tab_workflow.py`](file:///d:/REP/Codestruct/Codestruct/scripts/verify_real_thonny_stitch_tab_workflow.py) exercising the installed Thonny IDE environment (`D:\REP\thonny\venv\Scripts\python.exe`):

### 1. Pre-Open Source Tabs in Thonny Editor Notebook
- Created disposable nested Project Alpha:
  - `services/analytics.py` (class `AnalyticsService`, methods `record_event`, `compute_metrics`)
  - `domain/models.py` (classes `UserSession`, `EventRecord`)
  - `utils/helpers.py` (functions `format_timestamp`, `sanitize_input`)
  - `main.py` (function `bootstrap`)
  - `danger.py` (hostile execution trap: `raise RuntimeError('SECURITY_BREACH_EXECUTED_DANGER_CODE')`)
- Initialized real Thonny Workbench with `FilesView` and `EditorNotebook`.
- Pre-opened source files `main.py` and `services/analytics.py` in `EditorNotebook`. Verified 2 active source tabs before launching CodeStruct.

### 2. File Selection to Containing Folder Resolution
- Pointed File view focus at `services/analytics.py` inside `disposable_alpha_project`.
- Verified `get_file_view_folder(wb)` resolved to `C:\Users\ABHINAV\AppData\Local\Temp\tmp...\disposable_alpha_project`, proving that selecting a single file correctly identifies the containing project root.

### 3. Tools → CodeStruct Tab Docking & Switching
- Invoked `Tools → CodeStruct` (`open_codestruct_workbench()`).
- Verified `CodeStructEditorTab` was created and docked in the same Thonny main window (`tab.winfo_toplevel() == wb`).
- Verified `EditorNotebook` now contains 3 switchable tabs:
  1. `main.py` (source tab)
  2. `analytics.py` (source tab)
  3. `CodeStruct: disposable_alpha_project` (workbench tab)
- Exercised seamless tab switching:
  - Selected tab 0 (`main.py`) -> active editor is `main.py`.
  - Selected tab 1 (`analytics.py`) -> active editor is `analytics.py`.
  - Selected CodeStruct tab -> active editor is CodeStruct tab.
  - Zero crashes, zero attribute errors, and full Thonny UI responsiveness.

### 4. Whole-Project Analysis Verification
- Queried backend analysis graph for Project Alpha.
- Confirmed indexing of 27 nodes spanning all nested subdirectories:
  - `AnalyticsService`, `compute_metrics`, `record_event` from `services/`
  - `UserSession`, `EventRecord` from `domain/`
  - `format_timestamp`, `sanitize_input` from `utils/`
  - `bootstrap` from `main.py`
- Proved whole-project analysis across nested packages, not a single file.

### 5. Multi-Folder Project Switching
- Created disposable nested Project Beta:
  - `core/pipeline.py` (class `DataPipeline`, methods `ingest`, `transform`, `execute`)
  - `storage/db.py` (class `DatabaseStore`, methods `save`, `query`)
  - `main.py` (function `start_pipeline`)
- Switched Thonny File view to `disposable_beta_pipeline`.
- Opened `core/pipeline.py` in editor notebook.
- Invoked `Tools → CodeStruct` again:
  - Verified single tab reuse: existing CodeStruct tab updated to `CodeStruct: disposable_beta_pipeline` without tab duplication.
  - Verified Beta analysis contains Beta symbols (`DataPipeline`, `DatabaseStore`) with zero stale symbols from Project Alpha.

### 6. In-IDE Source Navigation
- Dispatched navigation command for `core/pipeline.py` at line 4, column 1.
- Verified Thonny opened `core/pipeline.py` in `EditorNotebook` with cursor at line 4.

### 7. Missing-Folder Guard
- Set File view directory to `None`.
- Invoked `open_codestruct_workbench()`.
- Verified in-IDE information dialog was displayed: `"No Folder Open in File View: Please open your project folder in Thonny's File view (View → Files) before launching CodeStruct."`
- Verified no tab was created and no fallback root was used.

### 8. Static Non-Execution Safety Invariant
- Verified `danger` module was never imported into `sys.modules`.
- Verified no project code (`alpha` or `beta`) was executed during analysis or folder switching.

---

## 4. Visual Evidence & Screenshots

All screenshots captured from the real running Thonny IDE main window:

1. **Thonny Main Window with Switchable Source Tabs and CodeStruct Tab (Project Alpha):**
   - File: [`docs/verification/screenshots/thonny_tab_fixture_alpha.png`](file:///d:/REP/Codestruct/Codestruct/docs/verification/screenshots/thonny_tab_fixture_alpha.png)
   - Mirror: [`C:\Users\ABHINAV\.gemini\antigravity-ide\brain\4fda842f-5c51-411b-b338-e842886b640c\thonny_tab_fixture_alpha.png`](file:///C:/Users/ABHINAV/.gemini/antigravity-ide/brain/4fda842f-5c51-411b-b338-e842886b640c/thonny_tab_fixture_alpha.png)
   - Shows: Thonny menu bar, Files view on left with nested Project Alpha structure, `EditorNotebook` showing tabs `main.py`, `analytics.py`, and `CodeStruct: disposable_alpha_project` active, hosting the Stitch Architecture Workbench.

2. **Switched to Open Source File Tab (`main.py`):**
   - File: [`docs/verification/screenshots/thonny_window_source_tab_active.png`](file:///d:/REP/Codestruct/Codestruct/docs/verification/screenshots/thonny_window_source_tab_active.png)
   - Mirror: [`C:\Users\ABHINAV\.gemini\antigravity-ide\brain\4fda842f-5c51-411b-b338-e842886b640c\thonny_window_source_tab_active.png`](file:///C:/Users/ABHINAV/.gemini/antigravity-ide/brain/4fda842f-5c51-411b-b338-e842886b640c/thonny_window_source_tab_active.png)
   - Shows: Seamless switch back to `main.py` source code editor in Thonny's `EditorNotebook` with the `CodeStruct` tab sitting alongside as a switchable tab.

3. **Multi-Folder Switch to Project Beta:**
   - File: [`docs/verification/screenshots/thonny_tab_fixture_beta.png`](file:///d:/REP/Codestruct/Codestruct/docs/verification/screenshots/thonny_tab_fixture_beta.png)
   - Mirror: [`C:\Users\ABHINAV\.gemini\antigravity-ide\brain\4fda842f-5c51-411b-b338-e842886b640c\thonny_tab_fixture_beta.png`](file:///C:/Users/ABHINAV/.gemini/antigravity-ide/brain/4fda842f-5c51-411b-b338-e842886b640c/thonny_tab_fixture_beta.png)
   - Shows: Thonny's File view switched to Project Beta (`disposable_beta_pipeline`), single CodeStruct tab title updated to `CodeStruct: disposable_beta_pipeline`.

4. **In-IDE Source Code Navigation:**
   - File: [`docs/verification/screenshots/thonny_navigated_source_file.png`](file:///d:/REP/Codestruct/Codestruct/docs/verification/screenshots/thonny_navigated_source_file.png)
   - Mirror: [`C:\Users\ABHINAV\.gemini\antigravity-ide\brain\4fda842f-5c51-411b-b338-e842886b640c\thonny_navigated_source_file.png`](file:///C:/Users/ABHINAV/.gemini/antigravity-ide/brain/4fda842f-5c51-411b-b338-e842886b640c/thonny_navigated_source_file.png)
   - Shows: Navigation from CodeStruct symbol directly opening `core/pipeline.py` in Thonny at line 4.

---

## 5. Quality Gates Summary

All configured verification suites and quality gates executed and passed 100%:

| Gate | Command | Exit Code | Result Summary |
|---|---|:---:|---|
| **Real Thonny UI Workflow** | `D:\REP\thonny\venv\Scripts\python.exe scripts/verify_real_thonny_stitch_tab_workflow.py` | `0` | **10/10 steps passed** (Nested multi-file Alpha, tab switching, whole-folder symbols, Beta switch, in-IDE nav, missing-folder guard, non-execution) |
| **Backend Pytest + Coverage** | `.venv\Scripts\pytest tests/ --cov=backend/src --cov-fail-under=84` | `0` | **323 passed, 2 skipped** (84.49% coverage >= 84.00% threshold) |
| **Plugin Pytest** | `.venv\Scripts\pytest --no-cov thonny-plugin/tests` | `0` | **69 passed, 1 skipped** (70 total tests across 2 test files) |
| **Python Lint (Ruff)** | `.venv\Scripts\ruff check backend thonny-plugin` | `0` | **All checks passed** |
| **Python Typing (Mypy)** | `.venv\Scripts\mypy backend/src` | `0` | **Success: no issues found in 55 source files** |
| **Frontend Lovable Typing** | `npm --prefix frontend.lovable run typecheck` | `0` | **Clean, 0 errors** (`tsc -p tsconfig.integration.json`) |
| **Frontend Lovable Tests** | `npm --prefix frontend.lovable test` | `0` | **10 passed, 1 skipped** (`vitest run`) |
| **Frontend Lovable Build** | `npm --prefix frontend.lovable run build` | `0` | **Clean build** (built in 7.57s) |
| **Frontend ESLint** | `npm --prefix frontend run lint` | `0` | **Clean, 0 errors** (`eslint .`) |
| **Git Diff Check** | `git diff --check` | `0` | **Clean, 0 whitespace errors** |

---

## 6. Changed Files Inventory

- [`thonny-plugin/thonnycontrib/codestruct/__init__.py`](file:///d:/REP/Codestruct/Codestruct/thonny-plugin/thonnycontrib/codestruct/__init__.py):
  - Added complete `DummyCodeViewText` and `DummyCodeView` method suites to satisfy Thonny's tab switching and appearance updates.
  - Implemented `CodeStructEditorTab` with `self._uri = f"codestruct://{self.project_path}"`, `is_local() -> False`, `update_appearance()`, and PID-isolated WebView2 data directory.
  - Updated `get_file_view_folder` to use Thonny's supported `get_active_local_dir()` and `get_active_directory()`, with resolution of selected files to containing folder.
  - Removed single-file `codestruct_analyze` command from Tools menu in `load_plugin()`.
- [`thonny-plugin/tests/test_plugin.py`](file:///d:/REP/Codestruct/Codestruct/thonny-plugin/tests/test_plugin.py):
  - Updated `test_editor_tab_lifecycle_and_methods` to assert `self.assertFalse(tab.is_local())`.
  - Added `test_get_file_view_folder_resolves_file_to_containing_directory`.
  - Added `test_get_file_view_folder_uses_get_active_directory_fallback`.
  - Added `test_load_plugin_registers_only_codestruct_workbench_command`.
- [`thonny-plugin/tests/test_workbench_integration.py`](file:///d:/REP/Codestruct/Codestruct/thonny-plugin/tests/test_workbench_integration.py):
  - Updated expected `add_command` call count to 1 (`codestruct`).
- [`scripts/verify_real_thonny_stitch_tab_workflow.py`](file:///d:/REP/Codestruct/Codestruct/scripts/verify_real_thonny_stitch_tab_workflow.py):
  - Enhanced to generate realistic nested multi-file project fixtures (`domain/`, `services/`, `utils/`, `core/`, `storage/`).
  - Pre-opens source tabs in Thonny `EditorNotebook` and exercises bidirectional tab switching between source tabs and CodeStruct.
  - Verifies whole-project analysis symbols across all nested directories.
  - Captures screenshots of Thonny main window for Alpha tabs, active source tab, Beta switch, and navigation.

---

## 7. Status Declaration

Milestone 7 status: **Ready for Codex review**.  
Milestone 8 has **NOT** been started.  
Nothing has been marked Accepted.  
No Git push has been performed.
