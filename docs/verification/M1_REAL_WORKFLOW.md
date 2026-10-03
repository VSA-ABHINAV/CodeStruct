# Milestone 1: Real Application Workflow Verification

Date: 2026-09-29  
Status: Complete — Live Thonny Workbench, Headless Chrome CDP, and Real FastAPI Backend Verified  
Gate Addressed: `M1_CODEX_REVIEW_6.md` Only Remaining M1 Gate (CS-002 Real-Workflow Verification)

---

## 1. Executive Summary

Milestone 1's real application smoke verification was executed end-to-end on Windows loopback against real running processes. The core Thonny `Workbench`/`EditorNotebook`, HTTP communication, headless Chrome browser page via CDP, and Tk text widget were real. To automate the workflow cleanly without blocking UI popups or opening extra browser windows, `webbrowser.open` and `tkinter.messagebox` were substituted/monkeypatched in the harness.

The smoke workflow proved:
1. **Real Running Stack**: Real FastAPI backend (`127.0.0.1:8000`), real Vite frontend dev server (`127.0.0.1:5173`), and real Thonny IDE workbench (`Workbench` instance with `EditorNotebook` running under Tk 8.6.15) executing against two isolated temporary roots (`smoke_root1` and `smoke_root2`).
2. **Analysis Initiation & Token Scrubbing**: Thonny plugin initiated analysis of `smoke_root2/app.py`, obtained a scoped capability session token (`cap_eZrP***`), and opened the browser URL `http://127.0.0.1:5173?analysis_id=ana__RZ2MYeaWK0Jp11Z60H1pE04&session_token=cap_eZrP***`. Headless Google Chrome loaded the page, and the frontend immediately scrubbed `session_token` from the browser address bar via `window.history.replaceState`, leaving `http://127.0.0.1:5173/`.
3. **Interactive Graph Navigation**: Chrome selected the `calculate_root2()` method pill in the rendered React Flow graph and clicked `.source-navigate-button` ("Open in editor"). The frontend dispatched `POST /api/v1/editor/navigate` with `{ session_token: "cap_eZrP***", relative_path: "app.py", line: 4, column: 5 }` and displayed immediate feedback `"Navigation command sent to editor (app.py:4)."`.
4. **Live Tk Text Widget Cursor**: Thonny's background polling loop retrieved the pending navigation command, safely scheduled execution onto the Tk main thread via `_nav_queue`, verified session scope, opened `smoke_root2/app.py` in `EditorNotebook`, and set the live Tk text widget `insert` mark directly to `4.4` (corresponding to API line 4, column 5: `    def calculate_root2(self):`).
5. **Two-Root Session Isolation**: Both `smoke_root1` and `smoke_root2` contained identical filenames (`app.py`). The live editor remained strictly bound to `smoke_root2/app.py`, completely isolated from `smoke_root1/app.py`.
6. **Active Editor Tab Switching & Stale Command Protection**: With `smoke_root1/app.py` switched into the active editor tab, stale tokens (`cap_stale_token_12345`), path traversal (`../smoke_root1/app.py`), and scope filename mismatches (`other_nonexistent.py`) were rejected without moving the cursor or editing source. (Note: Tab-switching validates active editor scoping; generation-switch poller races are tested separately via deterministic unit tests).
7. **Safe Failure Feedback**: Direct API probes against invalid session tokens, path traversal (`../app.py`), and out-of-scope targets returned HTTP 403 Forbidden with structured machine-readable error codes.
8. **Clean Shutdown & Listener Verification**: All spawned processes were terminated cleanly. Ports `8000`, `5173`, and `9222` were verified with zero lingering TCP listeners.

---

## 2. Test Fixture Setup

Two isolated temporary roots were created on the local filesystem:

- **Root 1 Path**: `C:\Users\ABHINAV\.gemini\antigravity-ide\brain\f818b53b-c7ec-4b08-9231-1cf2dc9e3c32\scratch\smoke_root1\app.py`
  ```python
  # ROOT 1 APP FILE
  def calculate_root1():
      alpha = 10
      beta = 20
      return alpha + beta
  ```
- **Root 2 Path**: `C:\Users\ABHINAV\.gemini\antigravity-ide\brain\f818b53b-c7ec-4b08-9231-1cf2dc9e3c32\scratch\smoke_root2\app.py`
  ```python
  # ROOT 2 APP FILE (SESSION-BOUND TARGET)
  class ServiceHandler:
      # Service handler in root 2
      def calculate_root2(self):
          gamma = 100
          delta = 200
          return gamma + delta
  ```

---

## 3. Real Workflow Execution Sequence & Observations

### 3.1 Stack Startup

- **Backend**: Started with Python virtualenv (`.venv\Scripts\python.exe`) running Uvicorn on `127.0.0.1:8000` with authorized roots `smoke1` and `smoke2` and fresh SQLite database `smoke_db.sqlite3`.
- **Frontend**: Started with Vite (`npm run dev`) on `127.0.0.1:5173`.
- **Thonny IDE**: Started with real Thonny workbench environment (`d:\REP\thonny\venv\Scripts\python.exe`) loading `thonnycontrib.codestruct`. Real `EditorNotebook` opened `smoke_root2\app.py`. Initial text widget cursor index: `8.0`.

### 3.2 Analysis Initiation & Credential Scrubbing

- `analyze_current_project()` was invoked in Thonny.
- `CodeStructAnalysisWorker` registered file selection with backend, obtained scoped capability `cap_eZrP***`, submitted analysis `ana__RZ2MYeaWK0Jp11Z60H1pE04`, and polled until `JobState.COMPLETED`.
- Generated viewer URL: `http://127.0.0.1:5173?analysis_id=ana__RZ2MYeaWK0Jp11Z60H1pE04&session_token=cap_eZrP***` (redacted).
- Google Chrome (headless CDP port `9222`) navigated to the viewer URL.
- **Observed Address Bar URL**: `http://127.0.0.1:5173/`
- **Credential Scrubbing Result**: `session_token` was scrubbed from the browser URL bar immediately (`True`), leaving no sensitive capability token in browser history.

### 3.3 UI Interaction & Navigation Dispatch

- Chrome inspected the DOM, located the `calculate_root2()` method pill within the `ServiceHandler` class card, and dispatched a click event.
- Selection updated to method node `n_btfdktkhviamv6a3du4lnfx6ny` (`calculate_root2`, `app.py:4:5`).
- Chrome clicked the `.source-navigate-button` ("Open in editor").
- **Observed Navigation Feedback**: `"Navigation command sent to editor (app.py:4)."`

### 3.4 Live Editor Cursor Update & Isolation Verification

- Thonny navigation poller retrieved command `nav_***` with target `app.py`, line 4, column 5.
- The command was transferred across thread boundaries to `_nav_queue`, and executed strictly on the Tk main thread via `_poll_navigate`.
- **Observed Active Editor Filename**: `C:\Users\ABHINAV\.gemini\antigravity-ide\brain\f818b53b-c7ec-4b08-9231-1cf2dc9e3c32\scratch\smoke_root2\app.py`
- **Observed Cursor Index (`tw.index("insert")`)**: `4.4` (maps exactly to API line 4, column 5 in Tk 0-indexed column coordinates).
- **Observed Line Text**: `    def calculate_root2(self):`
- **Two-Root Isolation**:
  - `file_matched_root2`: `True`
  - `isolated_from_root1`: `True` (editor remained strictly on `smoke_root2`, never switching to `smoke_root1`).

### 3.5 Session Switching & Stale Command Protection

The active editor was manually switched to `smoke_root1\app.py` (initial cursor index: `1.0`):
1. **Stale Token Navigation**: Dispatched command with token `cap_stale_token_12345`.
   - **Observed**: Navigation rejected (`session mismatch or no file registered for session`).
   - `stale_session_rejected`: `True` (cursor in `smoke_root1` remained unchanged at `1.0`).
2. **Path Traversal Defense-in-Depth**: Dispatched command with `relative_path="../smoke_root1/app.py"`.
   - **Observed**: Plugin defense-in-depth caught traversal: `Navigation rejected: path traversal in relative_path`.
   - `traversal_rejected_in_plugin`: `True`.
3. **Scope Mismatch Defense-in-Depth**: Dispatched command with `relative_path="other_nonexistent.py"`.
   - **Observed**: Plugin rejected mismatch: `target does not match session-registered file 'app.py'`.
   - `scope_mismatch_rejected_in_plugin`: `True`.

### 3.6 Backend API Failure Feedback

Direct HTTP requests to `POST /api/v1/editor/navigate`:
1. Invalid session token (`cap_invalid_xyz`): Rejected with HTTP `403 Forbidden` (`backend_invalid_session_status: 403`).
2. Path traversal (`../app.py`): Rejected with HTTP `403 Forbidden` (`backend_traversal_status: 403`).
3. Out-of-scope target (`other.py`): Rejected with HTTP `403 Forbidden` (`backend_scope_status: 403`).

### 3.7 Process Shutdown & Port Listener Verification

- Thonny workbench shutdown via `on_workbench_shutdown()`, destroying Tk root and backend runner.
- Frontend dev server terminated.
- Backend server terminated.
- Google Chrome process terminated.
- **Port Listener Check**:
  - Port `8000`: `Free` (no TCP listener)
  - Port `5173`: `Free` (no TCP listener)
  - Port `9222`: `Free` (no TCP listener)

---

## 4. Verification Artifacts & Machine Evidence

All smoke artifacts are preserved in the artifact scratch directory:

| Artifact | Description | Status |
|:---|:---|:---|
| `smoke_m1_summary.json` | Complete machine-readable summary of Thonny editor observations, cursor indices, isolation flags, and failure feedback | Verified |
| `browser_nav_result.json` | Chrome CDP automation results (URL scrubbing, node clicks, feedback messages) | Verified |
| `codestruct_real_browser_graph.png` | Real browser screenshot of rendered React Flow graph | Captured |
| `codestruct_real_browser_nav_feedback.png` | Real browser screenshot of DetailsPanel with "Navigation command sent to editor (app.py:4)" feedback | Captured |
| `run_thonny_session.py` | Reproduction script for real Thonny workbench lifecycle and Tk cursor validation | Preserved |
| `run_browser_nav.py` | Reproduction script for CDP headless browser navigation and interaction | Preserved |
| `launch_backend.py` | Guarded backend launcher with isolated scratch database and roots | Preserved |

### 4.1 Summary JSON Excerpt (`smoke_m1_summary.json`)

```json
{
  "navigation_success": true,
  "observed_active_filename": "C:\\Users\\ABHINAV\\.gemini\\antigravity-ide\\brain\\f818b53b-c7ec-4b08-9231-1cf2dc9e3c32\\scratch\\smoke_root2\\app.py",
  "observed_cursor_index": "4.4",
  "observed_line_text": "    def calculate_root2(self):",
  "expected_filename": "C:\\Users\\ABHINAV\\.gemini\\antigravity-ide\\brain\\f818b53b-c7ec-4b08-9231-1cf2dc9e3c32\\scratch\\smoke_root2\\app.py",
  "expected_cursor_index": "4.4",
  "file_matched_root2": true,
  "isolated_from_root1": true,
  "stale_session_rejected": true,
  "traversal_rejected_in_plugin": true,
  "scope_mismatch_rejected_in_plugin": true,
  "backend_invalid_session_rejected": true,
  "backend_invalid_session_status": 403,
  "backend_traversal_rejected": true,
  "backend_traversal_status": 403,
  "backend_scope_rejected": true,
  "backend_scope_status": 403
}
```

### 4.2 Browser Navigation JSON Excerpt (`browser_nav_result.json`)

```json
{
  "initial_url": "http://127.0.0.1:5173?analysis_id=ana__RZ2MYeaWK0Jp11Z60H1pE04&session_token=cap_eZrP***",
  "scrubbed_url": "http://127.0.0.1:5173/",
  "session_token_scrubbed": true,
  "graph_screenshot": "C:\\Users\\ABHINAV\\.gemini\\antigravity-ide\\brain\\f818b53b-c7ec-4b08-9231-1cf2dc9e3c32\\scratch\\codestruct_real_browser_graph.png",
  "node_click_status": "CLICKED_METHOD_PILL: calculate_root2()",
  "nav_button_status": "CLICKED_NAV_BUTTON",
  "feedback_message": "Navigation command sent to editor (app.py:4).",
  "feedback_screenshot": "C:\\Users\\ABHINAV\\.gemini\\antigravity-ide\\brain\\f818b53b-c7ec-4b08-9231-1cf2dc9e3c32\\scratch\\codestruct_real_browser_nav_feedback.png"
}
```

---

## 5. Concrete Defects Discovered and Resolved During Real Smoke

1. **Missing `session_token` in `CodeStructAnalysisWorker`**:
   - `thonny-plugin/thonnycontrib/codestruct/__init__.py:379` originally passed only `frontend_url` and `analysis_id` to `build_viewer_url()`, omitting `session_token`.
   - **Fix**: Updated worker to pass `session_token = self.root_id if self.root_id and self.root_id.startswith("cap_") else None`.
2. **Cross-Thread Tkinter Scheduling Violation**:
   - `thonny-plugin/thonnycontrib/codestruct/__init__.py:877, 918` called `wb.after()` from the background thread `codestruct-nav-poll`, triggering `RuntimeError: main thread is not in main loop` in Python/Tkinter.
   - **Fix**: Added thread-safe `_nav_queue: queue.Queue`. The worker thread now strictly enqueues navigation messages, while the Tk main thread drains the queue in `_poll_navigate` via scheduled `wb.after()` callbacks.
3. **Windows Multiprocessing Spawn Entry Point Re-execution**:
   - Under Windows, `multiprocessing.get_context("spawn").Process` re-imports the main entrypoint module. When the backend was started from a launcher without `if __name__ == "__main__":` guarding all setup and imports, the spawned analysis worker re-imported `codestruct.api.app:app`, which called `recover_interrupted()`, marking the active job as `PROCESS_RESTARTED` and failing with `InvalidTransitionError`.
   - **Fix**: Guarded launcher with `if __name__ == "__main__":` and cleaned database initialization so spawned workers execute `run_analysis_worker` safely without top-level re-initialization.
4. **Vite File Watcher `EBUSY` on `bun.lock`**:
   - Vite dev server crashed with `EBUSY: resource busy or locked, watch '.../frontend/bun.lock'` on Windows.
   - **Fix**: Added `server.watch.ignored: ["**/bun.lock", "**/.git/**"]` to `frontend/vite.config.js`.
5. **Class Card Method Pill Interactive Selection**:
   - Nested method pills (`.cs-method-pill`) in `ClassCardNode.jsx` previously lacked click handlers, making direct method selection via method pills impossible in the canvas.
   - **Fix**: Wired `onClick` on `.cs-method-pill` to `data.onSelectMethod({ type: 'node', id: m.id })`, allowing direct method selection and navigation to method source coordinates (`app.py:4:5`).

---

## 6. Conclusion & Gate Readiness

Milestone 1's real application smoke verification demonstrated real backend, real Thonny workbench, real headless browser via CDP, live Tk widget index observations (`4.4`), verified two-root session isolation, defense-in-depth failure feedback, and clean listener shutdown. Milestone 1 is ready for final Codex review. Milestone 2 remains not started.
