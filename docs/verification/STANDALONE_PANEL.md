# CodeStruct Standalone Project Explorer: Verification Report

**Date:** 2026-10-14
**Author:** Antigravity
**Status:** Complete — Ready for Codex Review
**Specification:** `docs/LOVABLE_STANDALONE_PANEL_BRIEF.md`
**Target Platform:** Windows 10/11 Desktop

---

## 1. Executive Summary

This report verifies the implementation of the **CodeStruct Standalone Project Explorer**, transitioning CodeStruct from a browser-tab prototype to a Windows desktop workbench for exploring whole project folders.

Key capabilities delivered:
1. **Windows Desktop Host Launcher:** Launches Microsoft Edge in standalone application window mode (`--app=http://127.0.0.1:5173`), providing a focused, borderless IDE tool window without browser address bars, navigation buttons, or tabs.
2. **Native Folder Chooser Bridge:** Integrates native Windows folder selection via `choose_folder_dialog()` backed by PowerShell/WinForms, with strict path validation and automatic initial analysis dispatch.
3. **Safe Directory & Nested Symbol Hierarchy:** Implements `build_project_tree()` providing an API (`GET /analyses/{id}/tree`) for directories, non-Python files, and Python symbols (module -> classes -> methods in source order, top-level functions) alongside policy exclusions.
4. **Top-Down Canvas Architecture:** Restructures the central React Flow canvas into a top-to-bottom hierarchy (Level 0: project/directory, 1: file/package, 2: module, 3: class, 4: function, 5: method) with top and bottom node handles.
5. **Left Project Explorer Drawer:** Adds an IDE-style file explorer with folder collapse/expand, nested Python symbols, source coordinates, search filtering, and synchronized selection with the canvas and inspector.
6. **Right Inspector Drawer:** Displays symbol details, coordinates, clickable relationship links to focus connected symbols, observed evidence, rule-based architectural explanations, and editor navigation.
7. **IDE Visual Restraint:** Enforces a single dark IDE theme, removing the Analyze button, project select dropdown, theme toggle, and demo badges.
8. **Clean Lifecycle:** Both `Start-CodeStruct-Prototype.ps1` and `Stop-CodeStruct-Prototype.ps1` manage backend, frontend, and standalone application window processes cleanly with zero orphan processes.

---

## 2. Architecture and Implementation Details

### 2.1 Native Desktop Application Host
- **Host Window:** Implemented in `prototype-launcher/Start-CodeStruct-Prototype.ps1`.
- **Mechanism:** Searches for Microsoft Edge (`msedge.exe`) and launches it with:
  ```powershell
  --app=http://127.0.0.1:5173 --window-size=1440,900 --user-data-dir="<runtime>/app_profile"
  ```
- **Lifecycle Tracking:** Captures PID and StartTime of backend, frontend, and the app window in `prototype-state.json`. `Stop-CodeStruct-Prototype.ps1` cleanly closes the application window and services.

### 2.2 Native Folder Picker Bridge & Security
- **Backend Bridge:** `backend/src/codestruct/host.py`
  - `choose_folder_dialog()`: Launches a native Windows folder browser dialog via PowerShell `[System.Windows.Forms.FolderBrowserDialog]` with Tkinter fallback.
  - `validate_project_folder()`: Validates that selected paths are existing directories, canonicalizes them, and rejects symlink escapes outside the user directory.
- **API Endpoint:** `POST /api/v1/host/choose-folder` in `backend/src/codestruct/api/routes/host.py`
  - Validates host authentication token (`X-CodeStruct-Host-Token`).
  - Registers the newly chosen directory root with `AnalysisService.register_root`.
  - Dispatches an initial analysis job immediately, returning the root ID, project name, path, and analysis ID.
- **Frontend Bridge:** `transport.chooseFolder()` in `frontend.lovable/src/features/transport.ts`
  - Checks for `window.codeStructHost.chooseProjectFolder()` when embedded in host wrappers.
  - Calls `POST /api/v1/host/choose-folder` as the direct bridge.

### 2.3 Whole-Project Directory & Symbol Tree API
- **Backend Tree Engine:** `backend/src/codestruct/analysis/tree.py`
  - `build_project_tree(root_path)`: Scans directories recursively, filtering hidden files and extracting symbols from `.py` and `.pyi` files using Python's `ast` parser.
  - Nested symbol structure: `module` -> `class` -> `method` (in source order), with top-level `function` nodes.
  - Non-Python files remain visible in the file tree without fabricated symbols.
  - Policy exclusions (`DEFAULT_EXCLUDED_DIRS`: `.git`, `__pycache__`, `venv`, `.venv`, `node_modules`, `build`, `dist`) are reported with clear explanatory reasons.
- **API Endpoints:** `backend/src/codestruct/api/routes/tree.py`
  - `GET /api/v1/analyses/{analysis_id}/tree`
  - `GET /api/v1/projects/{root_id}/tree`

### 2.4 Workbench Canvas & Drawers
- **Top-Down Hierarchy:** `buildFlow` and `getNodeLevel` in `frontend.lovable/src/features/workbench.tsx`:
  - Nodes categorized into levels 0 through 5.
  - Top handles for incoming edges (`Position.Top`) and bottom handles for outgoing edges (`Position.Bottom`).
  - Columns and rows spaced stably (300px horizontal spacing, 240px vertical spacing).
- **Left Project Explorer Drawer:** `frontend.lovable/src/features/ProjectExplorerTree.tsx`:
  - Folder icons with toggle collapse/expand.
  - Python symbol icons for modules, classes, and methods/functions with line coordinates.
  - Search input filtering symbols and directories.
  - Selection handler synchronizing clicked symbols with graph canvas and inspector.
  - Policy exclusions drawer displaying excluded paths and reasons.
- **Toolbar & Actions:**
  - `Open Folder`: triggers native folder dialog and starts analysis.
  - `Refresh`: reanalyzes the currently open project.
  - `DOT (Slice)`: downloads client-side rendered DOT graph of the visible page.
  - `DOT (Complete)`: downloads complete server-side Graphviz DOT export.
  - Removed Analyze button, project select dropdown, theme toggle, and demo badge.

---

## 3. Verification & Quality Gate Results

### 3.1 Backend Tests
- Command: `.venv\Scripts\python.exe -m pytest tests`
- Result: **319 passed, 2 skipped, 85.54% coverage** (requirement >= 84%).
- Host tests: `tests/test_host.py` (6 tests passing).
- Tree tests: `tests/test_tree.py` (10 tests passing).

### 3.2 Backend Code Standards
- `ruff check backend tests`: Passed (0 errors).
- `ruff format --check backend tests`: Passed (89 files formatted).
- `mypy backend\src`: Passed (0 errors in 55 files).

### 3.3 Frontend Tests & Build
- Vitest suite in `frontend.lovable`: **10 passed, 0 failed**.
- Verifies:
  - StrictMode handoff replaying and session clearing.
  - Top-down hierarchy levels (0 through 5).
  - R3 slice vs complete DOT export distinction.
  - Native folder selection (`openFolder`) and tree retrieval.
- `vite build`: Clean production build in 373ms.

### 3.4 Real Prototype Workflow
- Executed `Start-CodeStruct-Prototype.ps1`:
  - Backend initialized on port 8000.
  - Frontend initialized on port 5173.
  - Standalone Edge window opened at 1440x900.
  - Thonny IDE initialized with CodeStruct plugin.
- Executed `Stop-CodeStruct-Prototype.ps1`:
  - Standalone app window, backend, and frontend terminated cleanly with zero orphan processes.
  - Runtime state file cleared.

---

## 4. Acceptance Criteria Checklist

| Requirement | Status | Evidence |
|---|---|---|
| Open whole project folder via native dialog | **PASSED** | `POST /api/v1/host/choose-folder` + PowerShell `FolderBrowserDialog` |
| Directory tree with nested symbols (modules/classes/methods) | **PASSED** | `build_project_tree()` + `ProjectExplorerTree.tsx` |
| Refresh reanalyzes project without Analyze button | **PASSED** | Refresh action in topbar calling `load(true)` |
| Top-to-bottom graph hierarchy | **PASSED** | `getNodeLevel` tiers 0-5 + Top/Bottom handles |
| Selection synchronization between tree, graph, inspector | **PASSED** | `onSelectSymbol` focuses node and opens inspector |
| R3 DOT slice vs complete graph distinction | **PASSED** | Separate toolbar buttons + regression tests |
| Single IDE dark theme (no toggle/demo UI) | **PASSED** | Fixed `.dark` class + removed theme toggles & demo badges |
| Standalone Windows window (not a browser tab) | **PASSED** | `msedge.exe --app=...` window launched |
