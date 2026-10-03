# Thonny CodeStruct Plugin

A robust, thread-safe integration plugin for the [Thonny IDE](https://thonny.org) that enables analyzing Python projects using [CodeStruct](https://github.com/codestruct) and exploring the resulting architecture graph and diagnostics directly in the web browser.

---

## Features & Behavior

1. **Tools Menu Command**:
   - Registers **"Analyze with CodeStruct"** under Thonny's `Tools` menu (`command_id="codestruct_analyze"`).

2. **Explicit Root Mapping & Containment Resolution**:
   - Eliminates unsafe alias guessing or server fallback. Requires explicit mapping between local directories and server project root IDs.
   - Strictly enforces path-component containment and longest-prefix / most-specific root matching.
   - Detects and rejects conflicting duplicate IDs or duplicate directory assignments.

3. **Safe Concurrency & Thread-Safe UI Marshaling**:
   - Suppresses duplicate clicks while an operation is in progress (`_active_operation`).
   - Keeps all network requests entirely off the Tkinter main thread inside background daemon threads.
   - Communicates results and errors via a thread-safe `queue.Queue` drained by a scheduled Tkinter main-thread callback (`wb.after(50, ...)`).
   - Never invokes Tkinter widget methods directly from worker threads.
   - Cancels workers and suppresses late UI callbacks during Thonny shutdown.

4. **Safe Viewer URL Construction & Loopback Security**:
   - Validates that backend and frontend URLs strictly resolve to loopback addresses (`127.0.0.1`, `localhost`, `::1`).
   - Preserves configured URL base path, query parameters, and fragments while safely URL-encoding the `analysis_id` parameter.
   - Detects browser launch failures and provides copyable URLs.

5. **Unsaved Buffer Inspection**:
   - Inspects open local editor buffers within the selected project.
   - Prompts the user with explicit choices (**Analyze Saved Files** vs **Cancel and Save**) without modifying or overwriting files.

---

## Configuration

Configure the local project root mappings via environment variable:

```bash
# Format: <root_id>=<absolute_path>[;<root_id2>=<absolute_path2>]
export CODESTRUCT_ROOT_MAPPINGS="demo_root=/absolute/path/to/demo_project;pkg_root=/absolute/path/to/package"
```

Optional service URLs (defaults to loopback ports):
```bash
export CODESTRUCT_BACKEND_URL="http://127.0.0.1:8000"
export CODESTRUCT_FRONTEND_URL="http://127.0.0.1:5173"
```

---

## API Contract & Submission Details

The plugin submits analysis requests to the backend using:

- **Endpoint**: `POST /api/v1/analyses`
- **Headers**:
  - `Content-Type: application/json`
  - `Accept: application/json`
- **Request Body**:
  ```json
  {
    "project": {
      "root_id": "<root_id>",
      "relative_path": "<relative_path>"
    },
    "options": {
      "metrics": false
    },
    "refresh": false
  }
  ```
- **Response (202 Accepted / 200 OK)**:
  ```json
  {
    "analysis_id": "ana_...",
    "state": "queued" | "running" | "completed",
    "terminal": false | true,
    ...
  }
  ```

Upon receiving the `analysis_id`, the plugin formats the browser viewer URL:
```text
http://127.0.0.1:5173/?analysis_id=ana_...
```
and launches the browser viewer, which handles real-time polling and rendering.

---

## Installation & Development

To install in editable development mode inside Thonny's Python environment:

```powershell
& "D:\REP\thonny\venv\Scripts\python.exe" -m pip install -e "d:\REP\Codestruct\Codestruct\thonny-plugin"
```

### Running Tests

```powershell
$env:PYTHONPATH="d:\REP\Codestruct\Codestruct\thonny-plugin"
& "D:\REP\thonny\venv\Scripts\python.exe" -m unittest discover -s "d:\REP\Codestruct\Codestruct\thonny-plugin\tests" -v
```
