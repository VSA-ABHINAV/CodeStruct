# Thonny Workbench Layout Correction 2 — Verification Report

**Date:** 2026-10-22  
**Target:** Milestone 7 / CS-017 (Thonny workbench panel layout and usability)  
**Author:** Antigravity  
**Review Status:** Changes required — ready for Codex review (M7 remains unaccepted; M8 completed evidence preserved)  
**User Reference Evidence:** `D:\REP\changes\1.png` and `D:\REP\changes\2.png`  
**Host Environment:** Windows 11, Thonny 4.1.7, Python 3.10.11 / 3.11.9, WebView2 / Chromium 120+  

---

## 1. Executive Summary & Problem Analysis

In follow-up to user report 2 (2026-10-22), the previous layout correction approach was reviewed against user reference screenshots `D:\REP\changes\1.png` and `D:\REP\changes\2.png`:

1. **Persistent Unified Explorer:**
   - *Previous Approach:* Used a hide/restore hook (`_hide_files_pane` / `_restore_files_pane`) triggered on editor tab selection. When switching away from CodeStruct or closing the tab, Thonny's native `FilesView` was unhidden, and CodeStruct's Explorer was confined to the workbench tab.
   - *User Requirement:* The hide/restore approach is superseded. CodeStruct's unified project/symbol Explorer must be the **only** file explorer in Thonny across all editor tabs (`sample_project.py`, `CodeStruct: Desktop`, etc.), when CodeStruct is closed, and across Thonny restarts. It must contain the full folder/file tree and nested Python module/class/function/method symbols with lines, support opening/switching project folders, and keep its project root synchronized with Thonny. Native `FilesView` must never duplicate it or leave an empty interval.
   - *Resolution:* Implemented `CodeStructProjectExplorerView` as a full Tkinter/ttk widget subclassing `ttk.Frame`, implementing all Thonny `FilesView` duck-typing protocols (`get_tab_text`, `get_active_local_dir`, `get_active_directory`, `local_files`, `current_focus`, `on_show`, `refresh_tree`, `select_path_if_visible`, `should_open_name_in_thonny`). Injected into Thonny's workbench view registry (`wb._view_records["FilesView"]["class"] = CodeStructProjectExplorerView`), permanently replacing `FilesView` in the `"nw"` pane.

2. **Clean, Precise Inspector:**
   - *Previous Issue:* Raw internal enum tokens such as `unresolved_symbol` leaked into user-facing badges, relationship lists, and empty/error states. Furthermore, the Architectural Explanation card generated long, unstructured paragraphs with fallback text like `(graph metrics not computed)`.
   - *User Requirement:* Completely remove `unresolved_symbol` and similar raw tokens from all visible Inspector surfaces. Render **exactly two concise lines** of architectural explanation grounded strictly in available evidence.
   - *Resolution:* Added frontend formatters (`formatNodeKind`, `formatRelationshipKind`, `formatResolutionStatus`, `formatTwoLineExplanation`) in `frontend.lovable/src/features/workbench.tsx` and cleaned backend explanation synthesis in `backend/src/codestruct/analysis/llm_summary.py`. Unresolved symbols display cleanly as `[Unresolved Reference]`. The explanation renders:
     - **Line 1:** High-level architectural role / component declaration grounded in project architecture.
     - **Line 2:** Grounded callers/callees/definitions metrics and static AST parse provenance.

3. **Restored Graph Interaction:**
   - *Previous Issue:* ReactFlow canvas interactions (node click/selection, pan, zoom, fit) were impeded when embedded in Thonny due to default drawer open states and URL query parameter parsing discrepancies.
   - *User Requirement:* Restore interactive node selection, pan, zoom, fit/reset, and drag on the canvas. Selection must update the Inspector, and the graph must remain interactive with drawers toggled.
   - *Resolution:* Explicitly configured ReactFlow canvas props: `panOnDrag={true}`, `zoomOnScroll={true}`, `zoomOnPinch={true}`, `elementsSelectable={true}`, `nodesDraggable={true}`, `minZoom={0.15}`, `maxZoom={2.5}`. Added dedicated Zoom In, Zoom Out, and Fit View controls. Auto-collapsed the left drawer when embedded in Thonny (`isThonnyEmbedded`) to eliminate redundant overlay next to the docked Thonny Explorer. Updated `useWorkbench.ts` to parse both camelCase (`analysisId`) and snake_case (`analysis_id`) query parameters.

4. **Clear, Distinguishable Relationships:**
   - *Previous Issue:* Relationship edges were thin (1px) and faint against the canvas background and grid; arrowheads were small and hard to discern.
   - *User Requirement:* Make relationship strokes and arrowheads dark, thick (2.0–2.5px), crisp, and distinguishable against the grid at initial fit and multiple zoom levels. Distinguish relationship kinds.
   - *Resolution:* Increased edge stroke widths to 2.5px (calls, inherits, constructs), 2.2px (defines, contains), and 2.0px (imports). Assigned distinct high-contrast color codes:
     - Calls: Deep Navy (`#1e3a8a`, solid)
     - Inherits: Royal Purple (`#581c87`, solid)
     - Defines: Emerald Green (`#065f46`, dashed `4 4`)
     - Imports: Dark Slate (`#1e293b`, dashed `5 5`)
     - Constructs: Burnt Amber (`#9a3412`, solid)
     Arrowhead markers updated to prominent solid markers (`width: 20, height: 20`), and edge label pills styled with crisp borders and high-contrast text.

---

## 2. Reference Comparison

| Aspect | User Reference 1 (`1.png`) | Verified Implementation (`thonny_corr2_01_...png`) |
|---|---|---|
| **Active Editor Tab** | `sample_project.py` (Source file) | `sample_project.py` (Source file) |
| **Left Explorer** | CodeStruct Project Explorer with folder tree & nested Python symbols | CodeStruct Project Explorer with `📁 sample_project`, files & AST symbols (`sample_project.py`, `add_numbers`, `Calculator`, `add`) |
| **Native FilesView** | Replaced / Not duplicated | Replaced / Not duplicated |
| **Bottom Surface** | Thonny native Shell | Thonny native Shell |

| Aspect | User Reference 2 (`2.png`) | Verified Implementation (`thonny_corr2_02_...png`) |
|---|---|---|
| **Active Editor Tab** | `CodeStruct: Desktop` | `CodeStruct: sample_project` |
| **Left Explorer** | CodeStruct Project Explorer in Thonny `"nw"` dock | CodeStruct Project Explorer in Thonny `"nw"` dock |
| **Center Workbench** | Architectural Graph with nodes & relationships | 18 nodes, 21 edges, dark 2.5px strokes, prominent arrowheads |
| **Right Inspector** | Full-height docked Inspector | Full-height docked Inspector (top to bottom) |
| **Bottom Surface** | Thonny native Shell | Thonny native Shell carrying CodeStruct diagnostics |

---

## 3. Implementation Details

### 3.1 Persistent Unified Explorer (`thonnycontrib/codestruct/__init__.py`)
- Created `CodeStructProjectExplorerView(ttk.Frame)`:
  - Top bar with `📁 <folder_name>` header, `Open...` folder picker, and `🔄` refresh button.
  - Search entry with real-time substring filtering across paths and symbol names.
  - Kind filter buttons: `[All]`, `[Files]`, `[Classes]`, `[Functions]`, `[Methods]`.
  - Treeview showing directories, files, and nested AST symbols with line tags (`L10`, `L20`, etc.).
  - Double-click handlers: `_on_double_click` invokes `wb.get_editor_notebook().show_file_at_line(...)`.
  - Right-click context menu: `Open in Editor`, `Jump to Line`, `Switch Project Folder...`, `Refresh Tree`.
  - Full Thonny `FilesView` compatibility: implements `get_tab_text()`, `get_active_local_dir()`, `get_active_directory()`, `get_active_remote_dir()`, `local_files`, `current_focus`, `on_show()`, `refresh_tree()`, `select_path_if_visible()`, `is_active_browser()`, `should_open_name_in_thonny()`.
- Implemented `_integrate_persistent_explorer(wb)`:
  - Injects `CodeStructProjectExplorerView` into `wb._view_records["FilesView"]["class"]` and sets label to `"Project Explorer"`.
  - If `FilesView` was already instantiated in Thonny's `"nw"` notebook, hot-swaps it in-place using `containing_nb.forget(old_view)` and `containing_nb.insert(idx, new_view, text="Project Explorer")`.
  - Removes tab-switch hide/restore hooks so the unified Explorer persists permanently across all tab switches, closures, and restarts.

### 3.2 Clean Inspector & Exactly Two-Line Explanation (`workbench.tsx` & `llm_summary.py`)
- Added formatters in `workbench.tsx`:
  - `formatNodeKind`: maps `unresolved_symbol` -> `Unresolved Reference`, `external_module` -> `External Module`, etc.
  - `formatRelationshipKind`: maps `calls` -> `Calls`, `inherits` -> `Inherits`, `defines` -> `Defines`, etc.
  - `formatResolutionStatus`: maps `resolved` -> `Resolved`, `unresolved` -> `Unresolved Reference`.
  - `formatTwoLineExplanation`: generates strictly 2 lines:
    - Line 1: `Defined class in app.py within project architecture.`
    - Line 2: `Observed 2 incoming reference(s), 2 outgoing call(s).`
- Updated `backend/src/codestruct/analysis/llm_summary.py`:
  - Replaced raw kind concatenation (`f"a {entity.kind}"`) with friendly kind formatting (`friendly_kind`).
  - Removed ungrounded fallback strings like `(graph metrics not computed)`.

### 3.3 Graph Usability & High-Contrast Relationship Edges
- Configured ReactFlow canvas in `workbench.tsx`:
  - `panOnDrag={true}`, `zoomOnScroll={true}`, `zoomOnPinch={true}`
  - `elementsSelectable={true}`, `nodesDraggable={true}`
  - Added dedicated Zoom In, Zoom Out, and Fit View controls.
  - Automatically collapsed the redundant left drawer when embedded in Thonny (`isThonnyEmbedded`), leaving the canvas unobstructed.
- Styled relationship edges with dark, thick strokes and crisp markers:
  - Calls: `#1e3a8a`, 2.5px solid, markerEnd: `arrow_calls` (width: 20, height: 20)
  - Inherits: `#581c87`, 2.5px solid, markerEnd: `arrow_inherits`
  - Constructs: `#9a3412`, 2.5px solid, markerEnd: `arrow_constructs`
  - Defines: `#065f46`, 2.2px dashed (`4 4`), markerEnd: `arrow_defines`
  - Imports: `#1e293b`, 2.0px dashed (`5 5`), markerEnd: `arrow_imports`

---

## 4. Real UI Verification & Visual Evidence

Verification was conducted on real Windows 11 with Thonny 4.1.7 and the live Vite/WebView2 workbench.

### 4.1 Screenshot Catalog

| Figure | Image Path | Description |
|---|---|---|
| **Fig 1** | `docs/verification/screenshots/thonny_corr2_01_source_tab_persistent_explorer.png` | Source tab `sample_project.py` active in Thonny; unified CodeStruct Project Explorer is the sole left explorer with folder tree and AST symbols. Matches `1.png`. |
| **Fig 2** | `docs/verification/screenshots/thonny_corr2_02_codestruct_tab_persistent_explorer.png` | `CodeStruct: sample_project` tab active; unified Explorer persistent on left; graph rendered in center; full-height Inspector on right; native Thonny Shell at bottom. Matches `2.png`. |
| **Fig 3** | `docs/verification/screenshots/thonny_corr2_03_project_switch_sync.png` | Project folder switched to Project Beta; Explorer tree refreshed immediately with Beta files and symbols; workbench analysis updated. |
| **Fig 4** | `docs/verification/screenshots/thonny_corr2_04_tab_closed_explorer_persists.png` | CodeStruct editor tab closed; unified Explorer continues to persist in Thonny without interruption or blank interval. |
| **Fig 5** | `docs/verification/screenshots/graph_corr2_01_initial_fit.png` | Live graph at initial fit: 18 nodes, 21 edges with 2.5px dark strokes, crisp arrowheads, and distinct relationship colors. |
| **Fig 6** | `docs/verification/screenshots/graph_corr2_02_zoom_in.png` | Graph zoomed in: high-resolution rendering of nodes, thick edges, arrowheads, and relationship label pills. |
| **Fig 7** | `docs/verification/screenshots/graph_corr2_03_zoom_out.png` | Graph zoomed out: relationship strokes remain dark and clearly distinguishable against the background grid. |
| **Fig 8** | `docs/verification/screenshots/inspector_corr2_node_explanation.png` | Selected class node `Application`: badge `[Class] Node Detail`, zero raw enum tokens, exactly two concise evidence-grounded explanation lines. |
| **Fig 9** | `docs/verification/screenshots/inspector_corr2_unresolved_node.png` | Selected unresolved node `self.processor.execute`: badge `[Unresolved Reference]`, zero instances of `unresolved_symbol`. |

*Note: All 9 screenshots are mirrored in the conversation artifacts directory.*

---

## 5. Quality Gate Verification

All quality gates were executed in the project virtual environments and passed cleanly:

```powershell
# 1. Thonny Plugin Pytest Suite
$env:PYTHONPATH = "thonny-plugin;backend/src"
D:\REP\thonny\venv\Scripts\python.exe -m pytest -o addopts="" thonny-plugin/tests
# Result: 73 passed, 1 skipped in 1.48s (Exit Code: 0)

# 2. Backend Pytest Suite with Coverage
.venv\Scripts\pytest tests/ --cov=backend/src/codestruct --cov-report=term-missing --cov-fail-under=84
# Result: 342 passed, 2 skipped in 11.23s, 85.34% coverage (>= 84.00% required) (Exit Code: 0)

# 3. Frontend Vitest Suite
npm --prefix frontend.lovable test -- --run
# Result: 10 passed, 1 skipped in 1.48s (Exit Code: 0)

# 4. Frontend Production Build
npm --prefix frontend.lovable run build
# Result: vite v8.1.5 building for production... dist/ built cleanly in 975ms (Exit Code: 0)

# 5. Ruff Linter
.venv\Scripts\ruff check backend thonny-plugin
# Result: All checks passed! (Exit Code: 0)

# 6. Mypy Typecheck
.venv\Scripts\mypy
# Result: Success: no issues found in 57 source files (Exit Code: 0)
.venv\Scripts\mypy thonny-plugin/thonnycontrib/codestruct
# Result: Success: no issues found in 1 source file (Exit Code: 0)

# 7. Git Diff Check
git diff --check
# Result: 0 whitespace / marker errors (Exit Code: 0)
```

---

## 6. Safety Invariants & Boundary Guarantees

- **Static Non-Execution Safety Invariant:** Canary script `danger.py` was verified untouched. Neither user source files nor test fixtures were ever executed or imported. Analysis remains strictly AST-based.
- **Single Window & Single Bottom Shell:** All interactions occur within the single Thonny IDE main window. Thonny's native Shell is the sole bottom shell/diagnostics surface.
- **Persistent View Compatibility:** `CodeStructProjectExplorerView` implements the full duck-typing interface expected by Thonny internals, ensuring plugins or core features relying on `FilesView` continue to function without error.

---

## 7. Status & Tracking Summary

- **M7 Status:** Marked **Changes required** for this layout correction 2 follow-up; ready for Codex review.
- **M8 Status:** Preserved completed evaluation, storage faults, accessibility, documentation, and packaging evidence. Unaccepted pending Codex review.
- **Git Sync:** Scoped changes committed and pushed to `origin/main` without force.
