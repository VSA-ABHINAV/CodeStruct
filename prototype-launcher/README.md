# CodeStruct Prototype Launcher

This folder provides a complete double-click launcher system for running the CodeStruct prototype locally on Windows.

---

## 1. Quick Start

### Starting the Prototype
1. **Double-click** the **`Start CodeStruct Prototype`** shortcut on your Windows Desktop (or double-click `Start-CodeStruct-Prototype.cmd` in this directory).
2. The launcher will automatically:
   - Validate configuration and dependencies.
   - Start or safely reuse the backend server on loopback (`http://127.0.0.1:8000`).
   - Start or safely reuse the frontend viewer on loopback (`http://127.0.0.1:5173`).
   - Launch the Thonny IDE with the CodeStruct adapter and an isolated user profile configured.
3. In Thonny, open any Python file from your project (for example, `main.py`).
4. Click **Tools → Analyze with CodeStruct** from the top menu bar.
5. In the confirmation dialog, confirm the project folder to start analysis. The analysis result will automatically open in your default web browser.

### Stopping the Prototype
1. **Double-click** the **`Stop CodeStruct Prototype`** shortcut on your Windows Desktop (or double-click `Stop-CodeStruct-Prototype.cmd` in this directory).
2. The launcher terminates only the background services (backend and frontend) owned by this launcher session.
3. **Thonny is left open** so you never lose unsaved editor files or changes. You can save your work and close Thonny normally.

---

## 2. File and Directory Structure

```text
prototype-launcher/
├── Start-CodeStruct-Prototype.cmd     # Double-click entry point to start prototype
├── Stop-CodeStruct-Prototype.cmd      # Double-click entry point to stop services
├── Start-CodeStruct-Prototype.ps1     # Core startup, verification, and launch logic
├── Stop-CodeStruct-Prototype.ps1      # Safe process-termination logic
├── Create-Desktop-Shortcuts.ps1       # Shortcut generator for active Windows Desktop
├── prototype-config.json              # Central configuration file
├── README.md                          # User documentation (this file)
├── logs/                              # Service stdout and stderr log files
│   ├── backend-out.log
│   ├── backend-err.log
│   └── frontend.log
└── runtime/                           # Runtime locks, state, database, and profiles
    ├── launcher.lock                  # Single-start lock
    ├── prototype-state.json           # Active PID and process tracking
    ├── prototype_database.sqlite3     # Dedicated prototype database
    └── thonny_user_profile/           # Isolated Thonny configuration directory
```

---

## 3. Desktop Shortcuts

Desktop shortcuts are placed on the active Windows Desktop (`C:\Users\ABHINAV\OneDrive\Desktop`):
- **`Start CodeStruct Prototype.lnk`** → points to `Start-CodeStruct-Prototype.cmd`
- **`Stop CodeStruct Prototype.lnk`** → points to `Stop-CodeStruct-Prototype.cmd`

To regenerate or update these shortcuts at any time, run:
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Create-Desktop-Shortcuts.ps1
```

---

## 4. Configuration Reference (`prototype-config.json`)

All runtime settings are defined in `prototype-config.json`. You can modify these values without changing script code:

| Setting | Default Value | Description |
| :--- | :--- | :--- |
| `codeStructDirectory` | `D:\REP\Codestruct\Codestruct` | CodeStruct repository root |
| `backendPythonExecutable` | Python 3.13 executable | Python interpreter with backend dependencies |
| `frontendDirectory` | `D:\REP\Codestruct\Codestruct\frontend` | Frontend directory containing `package.json` and Vite |
| `thonnyDirectory` | `D:\REP\thonny` | Thonny repository checkout directory |
| `thonnyPythonExecutable` | `D:\REP\thonny\venv\Scripts\python.exe` | Thonny virtual environment Python interpreter |
| `thonnyPluginDirectory` | `D:\REP\Codestruct\Codestruct\thonny-plugin` | Directory containing `thonnycontrib.codestruct` |
| `demonstrationRootId` | `demo_root` | Root identifier used for backend authorization and adapter mapping |
| `demonstrationProjectDirectory` | Scratch demo project path | Absolute path to the analyzed Python project directory |
| `backendHost` | `127.0.0.1` | Loopback host for backend API |
| `backendPort` | `8000` | Port for backend API server |
| `frontendHost` | `127.0.0.1` | Loopback host for Vite dev server |
| `frontendPort` | `5173` | Port for frontend UI |
| `startupTimeoutSeconds` | `25` | Maximum seconds to wait for services to report ready |
| `databasePath` | `runtime\prototype_database.sqlite3` | Dedicated SQLite database for prototype runs |
| `thonnyUserProfileDirectory` | `runtime\thonny_user_profile` | Isolated Thonny configuration and profile directory |

---

## 5. Selecting Another Demonstration Project

To analyze a different Python project:
1. Open `prototype-config.json` in a text editor.
2. Update `demonstrationProjectDirectory` to point to the absolute path of your project directory:
   ```json
   "demonstrationProjectDirectory": "C:\\path\\to\\your\\python_project"
   ```
3. If desired, you may also change `demonstrationRootId` (e.g. `"my_project"`). The launcher will automatically ensure the backend's `CODESTRUCT_AUTHORIZED_ROOTS` and the adapter's `CODESTRUCT_ROOT_MAPPINGS` match identically.
4. Restart the prototype using `Start CodeStruct Prototype`.

---

## 6. Port Conflicts & Troubleshooting

### Port Conflicts
- If port `8000` or `5173` is occupied by an unrecognized process, the launcher halts immediately with an error message displaying the conflicting PID.
- To resolve:
  1. Identify or close the conflicting application.
  2. Or change `backendPort` / `frontendPort` in `prototype-config.json` to an unused port (e.g. `8080` / `5174`).

### Stale State and Crash Recovery
- If a previous session crashed or terminated abnormally, double-clicking `Start CodeStruct Prototype` will automatically inspect the state, verify if recorded processes are alive, and cleanly restart services.
- If a lock error persists, verify no other launcher window is active and delete `runtime\launcher.lock`.

### Inspecting Logs
All standard output and error messages are written in real time to the `logs/` directory:
- Backend stdout: `logs\backend-out.log`
- Backend stderr: `logs\backend-err.log`
- Frontend output: `logs\frontend.log`

---

## 7. Security and Safety Highlights
- **Loopback Only:** All network services bind strictly to `127.0.0.1`.
- **No Global System Modifications:** Environment variables (`PYTHONPATH`, `CODESTRUCT_AUTHORIZED_ROOTS`, `CODESTRUCT_ROOT_MAPPINGS`, `THONNY_USER_DIR`) are scoped strictly to the launcher and its child processes.
- **Process Ownership Guard:** The stop script checks both PID and process start-time against the session state before terminating to prevent killing recycled PIDs.
- **Safe from Data Loss:** Stopping services leaves Thonny running so unsaved editor changes are never lost.
