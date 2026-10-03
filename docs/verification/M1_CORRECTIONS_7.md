# Milestone 1: Review 7 Corrections & Verification Evidence

Date: 2026-09-30  
Status: Ready for Codex Review  
Addressing: `docs/verification/M1_CODEX_REVIEW_7.md` and `ANTIGRAVITY_TASK.md`

---

## 1. Summary of Changes

### 1.1 Navigation Poller Stale STOP & Switch Protection (`CS-002`)
- **Root Cause**: `_do_poll` previously queued `("STOP", None)` when an HTTP 401/403/404/410 or backend URLError occurred. If a user switched sessions (initiating generation 2) while generation 1's poll request was in-flight, generation 2 drained the queue and observed `STOP`, unconditionally clearing `_nav_poll_active = False` and disabling the new session.
- **Fix**:
  1. Updated `_do_poll` in `thonny-plugin/thonnycontrib/codestruct/__init__.py` to enqueue generation-scoped STOP messages: `("STOP", generation)`.
  2. Scoped the queue draining loop in `_poll_navigate`:
     - Discards any `STOP` message whose generation `stop_gen != _nav_poll_generation`.
     - Discards any `NAVIGATE` message whose generation or token does not match the active session.
  3. Added `_flush_nav_queue()` helper called at each session start (`_start_navigation_polling`) to purge leftover messages from previous generations.
  4. Preserved all Tk main-thread dispatching constraints (worker thread only places tuples on `_nav_queue`; Tk main thread executes all UI updates and file navigations).
- **Automated Verification**:
  - `docs/verification/M1_review7_queue_probe.py` runs and asserts `New session active after old STOP: True`.
  - Added unit tests in `thonny-plugin/tests/test_plugin.py`:
    - `test_poll_navigate_stale_stop_ignored_and_new_session_remains_active`
    - `test_poll_navigate_stale_navigate_discarded_and_new_session_navigates`
    - `test_in_flight_old_http_error_does_not_disable_new_generation`

### 1.2 Vite Watcher Configuration Reconciliation (`CS-003`)
- **Root Cause**: `frontend/package.json` invokes plain `vite` which loads `frontend/vite.config.js`. A previously added `frontend/vite.config.ts` was referencing unused TanStack config packages and had placed the Windows `bun.lock` watch ignore in the inactive config file.
- **Fix**:
  1. Added `server.watch.ignored: ["**/bun.lock", "**/.git/**"]` to active `frontend/vite.config.js`.
  2. Removed stray unused `frontend/vite.config.ts`.
  3. Preserved React plugin, base path (`/`), and `/api` proxy configuration.
- **Automated Verification**:
  - `scratch/verify_vite_proxy.py` verified that Vite dev server starts boundedly, loads `frontend/vite.config.js`, serves `http://127.0.0.1:5173/` (status 200), and proxies API requests `/api/v1/projects` to backend `http://127.0.0.1:8000/api/v1/projects` (status 200, valid JSON response).

### 1.3 Smoke Credential Cleanup & Workflow Report Clarifications (`CS-023`)
- **Credential Sanitization**:
  - Sanitized/redacted `scratch/session_info.json`.
  - Updated `scratch/run_thonny_session.py` to clean up `session_info.json` upon completion.
- **Report Claims Update**:
  - Updated `docs/verification/M1_REAL_WORKFLOW.md` to precisely describe that core Thonny `Workbench`/`EditorNotebook`, HTTP communication, headless Chrome browser page via CDP, and Tk text widget were real, while `webbrowser.open` and `tkinter.messagebox` were substituted/monkeypatched in the harness to avoid blocking popups and extra browser windows.
  - Clarified that active editor tab switching tests active editor scoping rather than in-flight generation races (which are covered by deterministic unit tests).

---

## 2. Test Verification Matrix

| Test Suite | Scope | Result | Details |
|:---|:---|:---|:---|
| `pytest` (Full project) | Backend + Plugin | **215 passed, 1 skipped** | Total coverage: **92%** (exceeds 84% gate). 1 skip: Windows symlink test. |
| `pytest` (Plugin focused) | `thonny-plugin/tests/test_plugin.py` | **52 passed, 1 skipped** | All navigation, session-switching, and error recovery tests passed. |
| `M1_review7_queue_probe.py` | Queue probe | **Passed (Exit 0)** | `New session active after old STOP: True` |
| `vitest` (Frontend) | `frontend` | **94 passed across 10 files** | All unit, component, accessibility, and contract fixture tests passed. |
| `verify_vite_proxy.py` | Dev start & Proxy | **Passed (Exit 0)** | Verified root HTML (200) and proxied `/api/v1/projects` (200). |
| `eslint` | `frontend` | **Passed (Exit 0)** | `eslint .` clean with 0 errors. |
| `vite build` | `frontend` | **Passed (Exit 0)** | Production bundle built in 536ms. |
| `ruff check` | Repo | **Passed (Exit 0)** | `All checks passed!` |
| `ruff format --check` | Repo | **Passed (Exit 0)** | `178 files already formatted` |
| `mypy` | `mypy.ini` | **Passed (Exit 0)** | `Success: no issues found in 50 source files` |

---

## 3. Conclusion

All findings from `M1_CODEX_REVIEW_7.md` have been fully resolved. Milestone 1 is ready for Codex review. Milestone 2 has not been started.
