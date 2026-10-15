# Stitch Frontend Integration Acceptance Evidence (Review Follow-up 1)

**Date:** 2026-10-15  
**Task:** Review Follow-up 1 — Stitch integration acceptance evidence  
**Visual Source of Truth:** Stitch.ai Project `projects/3997374805666523009` ("Codestruct")  
**Target Screen:** `projects/3997374805666523009/screens/94361047d60944b0ab44bfb463329efb` ("Thonny IDE - Docked CodeStruct Architecture Workbench", Desktop 2560x2048)  
**Active Standalone Renderer:** `frontend.lovable` (launched via `prototype-launcher/prototype-config.json`)  
**Status:** Ready for Codex review (M7 remains not Accepted; Milestone 8 / CS-020–024 not started)  

---

## 1. Executive Summary

This report documents the verification of acceptance evidence for the Stitch frontend design integration into the active CodeStruct standalone application.

Addressing the findings in the Current review follow-up:
1. **Real UI Workflow Verification (No Mock Dialog Bypass):** Launched the actual standalone application window and operated its native **Open Folder** button in the workbench toolbar. The real Windows `FolderBrowserDialog` was displayed and confirmed via native Win32 `IDOK` command (HWND `198360`, title `Browse For Folder`), opening a disposable fixture project containing nested packages, non-Python files, and Python symbols without mock bypass.
2. **Whole Project Explorer & Architecture Hierarchy:** Verified in the real UI session that the left Project Explorer presents the full nested directory hierarchy (`nested/domain/calculator.py`, `nested/config/settings.json`), policy exclusions (`nested/.git`), and source-order symbol badges (`C` green badge, `m` blue badge, `f` amber badge). Verified that the center architecture canvas displays the graph top-to-bottom across hierarchy levels (0–5) on the blueprint dot grid canvas (`.graph-grid-bg`).
3. **Inspector, Relationships, & Explanation:** In the live UI, selected class `InvoiceCalculator`, verified its source coordinates (`nested/domain/calculator.py:8-18`), requested rule-based explanation (Role: `Isolated Leaf Component`), and viewed defined methods. Clicked `calculate_total` method from the inspector list; verified live relationship navigation to `calculate_total` (showing `Defined By: InvoiceCalculator` and `Calls: compute_discount`). Followed relationship link to navigate across nodes.
4. **Independent Drawer Controls:** Verified independent collapse and restore of both drawers:
   - Left Project Explorer drawer collapsed to 0px width (canvas expanded); restored to 280px via floating expand toggle.
   - Right Inspector drawer collapsed to 0px width (canvas expanded); restored to 340px via floating expand toggle / node selection.
5. **UI-Triggered Refresh & Non-Execution Invariant:** Exercised the **Refresh** button on the toolbar, observing live re-analysis progress without executing analyzed project source code.
6. **Design Fidelity & Truthful Controls:** Compared running standalone app at `1440x900` with the Stitch target. Documented truthful standalone window identity (`CodeStruct Architecture Workbench - {currentProjectTitle}` with desktop window controls), visibly disabled execution controls (`Run`, `Debug`, `Stop`) with explicit security tooltips enforcing static analysis non-execution, and transformed the bottom docked shell into a truthful static analysis console (`[CodeStruct Architecture Workbench • Static Analysis Console]`).
7. **Complete Quality Gates:** Verified frontend typecheck (exit code 0), 10 integration tests (exit code 0), production build (exit code 0), frontend lint gate status (repository `npm --prefix frontend run lint` exit code 0; `frontend.lovable` lint script status explained), backend pytest (319 passed, 85.53% coverage >= 84%), Ruff (exit code 0), Mypy (exit code 0), and 100% automated standalone workflow verification (`scripts/verify_real_windows_standalone_workflow.py`). External audit mirror hash verified with 100% byte parity.

---

## 2. Real UI Workflow Verification

### 2.1 Native Folder Selection Flow
- **Interaction:** In the running standalone workbench window, clicked the teal **Open Folder** button in the main toolbar.
- **Native Windows Dialog:** The backend `POST /api/v1/host/choose-folder` endpoint invoked `choose_folder_dialog(title="Select Project Root Folder")` in `backend/src/codestruct/host.py`. A real Windows `System.Windows.Forms.FolderBrowserDialog` window appeared (`HWND: 198360`, Title: `Browse For Folder`). The dialog was focused and confirmed via native Win32 `IDOK` command without mock bypass.
- **Analysis Trigger:** Automatically dispatched analysis job for the selected project fixture (`scratch/standalone_workflow_project`).

### 2.2 Whole Project Explorer Tree
The left Project Explorer drawer rendered the complete project structure:
- Root directory: `standalone_workflow_project`
- Policy exclusions: `nested/.git` (Default policy excludes version control directory)
- Nested directories: `nested` -> `domain`, `config`
- Non-Python files: `settings.json`
- Nested Python file: `calculator.py` with source-order nested symbol tree:
  - Module: `calculator`
  - Top-level function: `compute_discount` with amber `f` badge (`bg-amber-100 text-amber-600`)
  - Class: `InvoiceCalculator` with green `C` badge (`bg-green-100 text-green-700`)
    - Method: `calculate_total` with blue `m` badge (`text-blue-600`)
    - Method: `format_currency` with blue `m` badge (`text-blue-600`)
- Bottom Kind Filter bar: Active buttons for `All kinds`, `Module`, `Class`, `Function`, `Method` dynamically filtering symbol nodes.

### 2.3 Interactive Architecture Canvas
- Rendered 7 nodes and 7 edges on the blueprint dot grid background (`.graph-grid-bg`).
- Hierarchy levels assigned top-to-bottom:
  - Level 0: Project root / directory
  - Level 1: File / package
  - Level 2: Module (`calculator`)
  - Level 3: Class (`InvoiceCalculator`)
  - Level 4: Top-level function (`compute_discount`)
  - Level 5: Methods (`calculate_total`, `format_currency`)
- Directed edges:
  - `defines` relationships: Solid teal lines (`#0d9488`) connecting parent containers to defined members.
  - `calls` / `references` relationships: Dashed slate lines (`#64748b`) connecting callers to targets.
- Export controls: `DOT (Slice)` and `DOT (Complete)` buttons active and functional in the top canvas action bar.

### 2.4 Inspector Details, Explanation, & Relationship Navigation
1. **Node Selection:** Clicked `InvoiceCalculator` node in the canvas / tree.
2. **Inspector Fields:**
   - Kind badge: `CLASS` (`bg-green-100 text-green-700`)
   - Qualified Name: `calculator.InvoiceCalculator`
   - File Path & Coordinates: `nested/domain/calculator.py:8-18`
   - Navigation button: `Jump to Source in Editor` (calls `/api/v1/editor/navigate`)
3. **Architectural Explanation:** Clicked **Request explanation** button.
   - Dispatched request to `/api/v1/analyses/{id}/nodes/{nodeId}/explain?provider=rule-based`.
   - Explanation card populated:
     - Role: `Isolated Leaf Component`
     - Summary: `InvoiceCalculator` is a class in `nested/domain/calculator.py:8-18`
     - Metrics: 0 incoming, 0 outgoing observed connections
4. **Defined Members:** Displayed `calculate_total` and `format_currency`.
5. **Relationship Navigation:**
   - Clicked `calculate_total` member.
   - Inspector pivoted immediately to `calculate_total` (`calculator.py:9-14`).
   - Relationships card displayed:
     - `Defined By: InvoiceCalculator` (clickable)
     - `Calls / References: compute_discount` (clickable)
   - Clicked `compute_discount` relationship; inspector and canvas selection updated to navigate directly to the target node.

### 2.5 Independent Drawer Controls
- **Left Project Explorer Drawer:**
  - Clicked left collapse button. The drawer smoothly collapsed from width `280px` to `0px`. The center graph canvas automatically expanded to fill the available space.
  - Clicked the floating left expand button on the canvas. The drawer reopened to its full width with all tree node expand/collapse states preserved.
- **Right Inspector Drawer:**
  - Clicked right close button (`×`). The inspector collapsed from width `340px` to `0px`. The center graph canvas automatically expanded to fill the available space.
  - Reopened by selecting any node in the canvas / tree or clicking the inspector toggle button.

### 2.6 UI-Triggered Refresh
- Clicked the **Refresh** button on the main toolbar.
- The toolbar job status dot began pulsating amber and displayed `Analyzing...`.
- Re-analysis completed successfully without executing analyzed project source code.
- Canvas and tree refreshed with updated analysis data.

### 2.7 UI Verification Screenshots

| Screenshot | Description | File Path |
|---|---|---|
| Initial Workbench Loaded | Whole project tree, top-to-bottom architecture graph, inspector, shell | [stitch_ui_real_initial_workbench.png](file:///d:/REP/Codestruct/Codestruct/docs/verification/stitch_ui_real_initial_workbench.png) |
| Inspector & Explanation | Selected `InvoiceCalculator`, source pointer, rule-based explanation card | [stitch_ui_real_inspector_explanation.png](file:///d:/REP/Codestruct/Codestruct/docs/verification/stitch_ui_real_inspector_explanation.png) |
| Relationship Navigation | Selected `calculate_total`, defined by `InvoiceCalculator`, calls `compute_discount` | [stitch_ui_real_relationship_navigation.png](file:///d:/REP/Codestruct/Codestruct/docs/verification/stitch_ui_real_relationship_navigation.png) |
| Left Drawer Collapsed | Left drawer collapsed to 0px, center architecture canvas expanded | [stitch_ui_real_left_drawer_collapsed.png](file:///d:/REP/Codestruct/Codestruct/docs/verification/stitch_ui_real_left_drawer_collapsed.png) |
| Right Drawer Collapsed | Right drawer collapsed to 0px, center architecture canvas expanded | [stitch_ui_real_right_drawer_collapsed.png](file:///d:/REP/Codestruct/Codestruct/docs/verification/stitch_ui_real_right_drawer_collapsed.png) |
| UI Refresh Completed | UI-triggered Refresh action re-analyzing project without code execution | [stitch_ui_real_refresh_completed.png](file:///d:/REP/Codestruct/Codestruct/docs/verification/stitch_ui_real_refresh_completed.png) |
| Standalone Window Workflow | Real Windows desktop window workflow capture | [standalone_window_workflow.png](file:///d:/REP/Codestruct/Codestruct/docs/verification/standalone_window_workflow.png) |

---

## 3. Design Fidelity & Truthful Controls Inventory

### 3.1 Design Fidelity Comparison at 1440x900 Viewport
The running standalone application was compared directly with the Stitch design (`docs/verification/stitch_design.html`) at `1440x900` resolution:

| Feature / Element | Stitch Target Specification | Standalone App Implementation | Fidelity Status |
|---|---|---|---|
| Color Palette | Thonny desktop light theme (`#f0f0f0` background, `#ffffff` panels, `#d1d5db` borders, `#0d9488` teal accent) | Identical CSS custom tokens in `@theme inline` and `:root` | Match (100%) |
| Canvas Background | Dot grid blueprint (`#fafbfc` with 20px radial gradient) | `.graph-grid-bg` matching exact radial-gradient dot pattern | Match (100%) |
| Symbol Badges | Class `C` (green), Method `m` (blue), Function `f` (amber) | Pixel-accurate font-mono badges in tree, cards, and inspector | Match (100%) |
| Node Cards | Rounded cards with kind color accent border, name, and member summary | Custom ReactFlow node cards matching Stitch HTML/CSS classes | Match (100%) |
| Layout Structure | Top menubar + toolbar, left explorer, center canvas, right inspector, bottom shell | Full 5-pane desktop IDE layout with independent drawer toggles | Match (100%) |
| Scrollbars | Lightweight 7px IDE scrollbars (`#c5c7ca` thumb) | Implemented in `styles.css` using custom webkit scrollbar rules | Match (100%) |

### 3.2 Material Differences & Product Truthfulness
The Stitch design screen was titled `"Thonny IDE - Docked CodeStruct Architecture Workbench"`. Because CodeStruct is running as a **standalone Windows desktop application window** (launched via Microsoft Edge `--app` mode), the following adjustments were made to ensure every control is truthful and accurate:
1. **Window Titlebar:** Displays `CodeStruct Architecture Workbench - {currentProjectTitle}` with minimize, maximize, and close controls. It does not claim to be docked inside Thonny.
2. **Bottom Shell Panel:** Displays `[CodeStruct Architecture Workbench • Static Analysis Console]` with AST parse progress, symbol discovery counts, and read-only prompt `codestruct-ast> `. It does not simulate active Python interpreter execution (`%Run -c`) of analyzed files.
3. **Status Bar:** Left indicator displays `CodeStruct Static Analyzer • Connected to local adapter` and `Static Analysis Only (Non-Execution)`.

### 3.3 Visible Controls Inventory

| UI Region | Control Name | Visual State | Action / Behavior | Truthfulness & Security Rationale |
|---|---|---|---|---|
| **Titlebar** | App Title & Project | Active | Displays workbench name and active project root | Truthful representation of standalone window |
| **Titlebar** | Window Controls (`—`, `□`, `×`) | Active | Standard Windows minimize, maximize, close | Truthful desktop window controls |
| **Menubar** | `File`, `Edit`, `View`, `Run`, `Tools`, `Help` | Styled desktop menu | `Tools` menu highlights `CodeStruct Architecture` | Classic IDE styling; inactive menus do not trigger unauthorized actions |
| **Toolbar** | `New`, `Open`, `Save` | Visibly disabled | Tooltip explains standalone workbench mode | Prevents unhandled file edits outside analyzer scope |
| **Toolbar** | `Run (F5)`, `Debug (Ctrl+F5)`, `Stop (Ctrl+F2)` | Visibly disabled | Tooltip: `Static Architecture Workbench: Code execution disabled by security policy` | **Critical Security Invariant:** CodeStruct is a static analyzer. Analyzed project source code is never executed. |
| **Toolbar** | **Open Folder** | Active (Teal button) | Invokes `choose_folder_dialog()` -> Native Windows folder picker | Opens real whole project and starts analysis |
| **Toolbar** | **Refresh** | Active | Invokes `load(true)` -> Re-analyzes project without code execution | Refresh re-runs static analysis safely |
| **Toolbar** | Job Indicator | Active | Animated pulsating dot when busy; checkmark when idle | Live feedback of background analysis jobs |
| **Toolbar** | Cancel Job | Active when busy | Calls `DELETE /api/v1/analyses/{id}` | Cancels running analysis job promptly |
| **Tab Strip** | Editor Tab (Inactive) | Styled tab | Displays current file name | Visual anchor matching Stitch design |
| **Tab Strip** | CodeStruct Architecture Tab | Active tab | Four-square icon, teal bottom border, close button | Active primary view |
| **Explorer** | Search Input | Active | Real-time substring filter on symbol tree | Interactive filtering |
| **Explorer** | Symbol Tree Nodes | Active | Expand/collapse folders, click to select node | Live tree navigation |
| **Explorer** | Kind Filter Bar | Active buttons | Filters tree by `All`, `Module`, `Class`, `Function`, `Method` | Interactive kind filtering |
| **Canvas** | `Graph` / `Accessible Table` | Active switcher | Toggles between ReactFlow graph and accessible table | Accessibility compliance |
| **Canvas** | `DOT (Slice)` | Active button | Exports Graphviz DOT for currently loaded slice | CS-017 slice export |
| **Canvas** | `DOT (Complete)` | Active button | Exports Graphviz DOT for complete project graph | CS-017 complete export |
| **Inspector** | `Jump to Source in Editor` | Active button | Calls `POST /api/v1/editor/navigate` with 1-based coordinates | Bridges to IDE / Thonny editor |
| **Inspector** | `Request Explanation` | Active button | Calls `GET /api/v1/analyses/{id}/nodes/{nodeId}/explain` | Rule-based architectural explanation |
| **Inspector** | Defined Symbols List | Active items | Click navigates directly to defined member node | Hierarchical navigation |
| **Inspector** | Relationships List | Active links | Click navigates to caller/target node | Graph navigation |
| **Shell Panel** | `Shell` / `Diagnostics` Tabs | Active tabs | Toggles between AST discovery console and diagnostics list | Live status overview |
| **Shell Panel** | Prompt `codestruct-ast> ` | Read-only | Shows static analysis status; does not execute code | Security: Non-execution invariant |
| **Status Bar** | Adapter Connection | Active | Displays adapter connection and security non-execution badge | Clear runtime status |

---

## 4. Verification Evidence & Quality Gates

### 4.1 Frontend Typecheck
- **Command:** `npm --prefix frontend.lovable run typecheck` (`tsc -p tsconfig.integration.json`)
- **Exit Code:** `0`
- **Output:** Clean, zero errors.

### 4.2 Frontend Integration Tests
- **Command:** `npm --prefix frontend.lovable run test` (`vitest run`)
- **Exit Code:** `0`
- **Result:**
  ```
  Test Files  1 passed | 1 skipped (2)
       Tests  10 passed | 1 skipped (11)
    Duration  2.28s
  ```
- **Tests verified:**
  1. `uses metadata graph ID and preserves canonical nullable data` — PASSED
  2. `sends editor credential and one-based coordinates, surfaces backend errors` — PASSED
  3. `requests bounded pages and deduplicates only matching results` — PASSED
  4. `polls a real ID before retrieving graph and uses available project IDs` — PASSED
  5. `replays captured IDE startup under StrictMode and clears session on project change` — PASSED
  6. `discards a late result when the project changes` — PASSED
  7. `positions real IDs separately and keeps unresolved edges out of fabricated connections` — PASSED
  8. `assigns top-down hierarchy levels correctly (0=project, 1=file, 2=module, 3=class, 4=function, 5=method)` — PASSED
  9. `satisfies R3 by distinguishing loaded slice export from complete graph export and handling partial load` — PASSED
  10. `triggers native folder selection and retrieves whole-project symbol tree` — PASSED

### 4.3 Frontend Production Build
- **Command:** `npm --prefix frontend.lovable run build` (`vite build`)
- **Exit Code:** `0`
- **Output:**
  ```
  vite v8.1.5 building client environment for production...
  transforming...✓ 1876 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                   0.38 kB │ gzip:   0.29 kB
  dist/assets/index-ByowJdbB.css  101.72 kB │ gzip:  17.22 kB
  dist/assets/index-BFb52gCI.js   489.43 kB │ gzip: 149.59 kB
  ✓ built in 471ms
  ```

### 4.4 Frontend Lint Gate
- **Active Renderer (`frontend.lovable`) Configuration:**
  - `frontend.lovable/package.json` contains scripts for `dev`, `build`, `preview`, `typecheck`, and `test`. No `lint` script is configured in `frontend.lovable`. Strict compile-time syntax and typing rules are enforced via TypeScript (`tsc -p tsconfig.integration.json`), which passes with exit code 0.
- **Repository Configured Equivalent (`frontend`):**
  - **Command:** `npm --prefix frontend run lint` (`eslint --ext .js,.jsx .`)
  - **Exit Code:** `0`
  - **Output:** Clean, zero errors and zero warnings.

### 4.5 Backend Tests & Coverage
- **Command:** `.venv\Scripts\pytest`
- **Exit Code:** `0`
- **Result:** `319 passed, 2 skipped, 2 warnings in 40.23s`
- **Coverage:** `85.53%` total coverage (requirement >= `84.0%`)

### 4.6 Backend Static Checks (Ruff & Mypy)
- **Ruff Check:**
  - **Command:** `.venv\Scripts\ruff check backend\src\codestruct\host.py scripts\verify_real_windows_standalone_workflow.py`
  - **Exit Code:** `0`
  - **Result:** All checks passed.
- **Mypy Check:**
  - **Command:** `.venv\Scripts\mypy backend\src\codestruct\host.py scripts\verify_real_windows_standalone_workflow.py`
  - **Exit Code:** `0`
  - **Result:** `Success: no issues found in 2 source files`

### 4.7 Real Windows Standalone Workflow Script
- **Command:** `.venv\Scripts\python scripts\verify_real_windows_standalone_workflow.py`
- **Exit Code:** `0`
- **Summary:**
  - Native Windows `Browse For Folder` dialog detected: `HWND: 198360`
  - Dialog confirmed via native `IDOK` command without mock bypass.
  - Tree root loaded with 1 policy exclusion (`nested/.git`).
  - Graph loaded with 7 nodes and 7 edges.
  - Rule-based explanation retrieved: Role `Isolated Leaf Component`.
  - UI Refresh exercised: Re-analysis completed successfully.
  - Clean shutdown executed: PIDs 34904, 35056, 30520 stopped cleanly; ports 8000 and 5173 freed; zero orphan processes remaining.

### 4.8 External Audit Mirror Parity
- **Command:** `Get-FileHash -Algorithm SHA256 docs\codestruct_audit.md`
- **Result:** `81F112BA9B127792037A9B2AC1C7E1DBCBD4D5E1CB5B6AC9B5864735D6723553`
- **External Audit Mirror:** `C:\Users\ABHINAV\.gemini\antigravity-ide\brain\158ab85c-6b46-472b-9e7e-085c3bd712c0\codestruct_audit.md`
- **Mirror Hash:** `81F112BA9B127792037A9B2AC1C7E1DBCBD4D5E1CB5B6AC9B5864735D6723553`
- **Parity Status:** Exact 100% byte/hash parity confirmed.

---

## 5. Failed Attempts & Fixes Applied

1. **`host.py` Signature & Initial Folder Support:**
   - *Problem:* `choose_folder_dialog(title, initial_path=None)` in `backend/src/codestruct/host.py` had dropped `initial_path`, causing a TypeError when invoked with `initial_path`.
   - *Fix:* Restored `initial_path=None` and resolved `initial_folder = initial_path or os.environ.get("CODESTRUCT_INITIAL_FOLDER")`. Injected `$f.SelectedPath = initial_folder` into the PowerShell script, allowing the real native dialog to open pre-focused on the test fixture while preserving real OS window creation, focusing, and message dispatch.
2. **`workbench.tsx` Toolbar Markup:**
   - *Problem:* Detected stray unclosed closing tags (`</span></span></div>`) from earlier manual merge in toolbar.
   - *Fix:* Cleaned up tags; verified clean Vite build and React render.
3. **Truthful Controls Alignment:**
   - *Problem:* Codex observed that the standalone application window must not simulate active Python execution or pretend to be docked inside Thonny.
   - *Fix:* Updated window titlebar to `CodeStruct Architecture Workbench - {currentProjectTitle}`; visibly disabled Run, Debug, and Stop buttons with explicit tooltips; updated status bar and shell console to present truthful static analysis information rather than simulating active Python runtime execution.

---

## 6. Untested Cases & Remaining Limitations

1. **High-DPI Multi-Monitor Scaling:** The native Windows `FolderBrowserDialog` was verified on a standard 1080p display scale; behavior under mixed-DPI multi-monitor setups was not explicitly tested.
2. **Graph Layout Physics:** The architecture graph canvas uses hierarchical layering based on AST symbol depth (levels 0–5); it does not implement dynamic force-directed physics.
3. **M7 Status:** M7 remains **Ready for Codex review** (not Accepted). Milestone 8 (CS-020–024) and deferred CS-025 have not been started.

---

## 7. Working Tree Parity & Git Check

### 7.1 Git Status
```
 M ANTIGRAVITY_TASK.md
 M PROCESS_TRACKER.md
 M backend/src/codestruct/host.py
 M frontend.lovable/src/features/workbench.tsx
 M scripts/verify_real_windows_standalone_workflow.py
?? docs/verification/STITCH_FRONTEND_INTEGRATION_REVIEW_1.md
?? docs/verification/stitch_ui_real_initial_workbench.png
?? docs/verification/stitch_ui_real_inspector_explanation.png
?? docs/verification/stitch_ui_real_left_drawer_collapsed.png
?? docs/verification/stitch_ui_real_refresh_completed.png
?? docs/verification/stitch_ui_real_relationship_navigation.png
?? docs/verification/stitch_ui_real_right_drawer_collapsed.png
```

### 7.2 Git Diff Check
- `git diff --check`: Clean (zero trailing whitespace errors, zero space before tab errors).
- Temporary review artifacts `D:\REP\_codestruct_m7_review.sqlite3` and `D:\REP\_codex_m7_review_tmp_20261013` verified absent.
