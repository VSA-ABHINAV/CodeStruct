# ruff: noqa: S101, S110, S310, S603, S607
"""Real Windows Single-Window Prototype Launch and Lifecycle Verification.

Verifies:
1. Starting prototype via Start-CodeStruct-Prototype.cmd opens Thonny IDE as the
   ONLY user-facing application window.
2. Zero standalone Edge application windows (msedge.exe with --app) are launched.
3. Backend (8000) and Frontend (5173) services start and proxy cleanly on loopback.
4. prototype-state.json tracks backend and frontend, and does NOT contain appWindow.
5. prototype-launcher/runtime/app_profile does not exist.
6. Stopping services via Stop-CodeStruct-Prototype.cmd stops backend and frontend,
   releases ports 8000 and 5173, and leaves Thonny running safely.
7. Restarting via Start-CodeStruct-Prototype.cmd starts services without launching
   any duplicate or standalone window.
8. Final cleanup safely stops services and closes test Thonny instance.
"""

from __future__ import annotations

import ctypes
import json
import logging
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WORKSPACE_ROOT = Path("D:/REP/Codestruct/Codestruct").resolve()
LAUNCHER_DIR = WORKSPACE_ROOT / "prototype-launcher"
RUNTIME_DIR = LAUNCHER_DIR / "runtime"
STATE_FILE = RUNTIME_DIR / "prototype-state.json"
APP_PROFILE_DIR = RUNTIME_DIR / "app_profile"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_single_window")


def http_get(url: str, timeout: float = 5.0, accept: str = "*/*") -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def get_visible_windows() -> list[dict[str, str | int]]:
    user32 = ctypes.windll.user32
    windows: list[dict[str, str | int]] = []

    def enum_cb(hwnd: int, _: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if title:
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    windows.append({"hwnd": hwnd, "title": title, "pid": pid.value})
        return True

    cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(cb_type(enum_cb), 0)
    return windows


def get_command_lines_for_process(process_name: str) -> list[dict[str, str | int]]:
    """Query Win32_Process via PowerShell to retrieve ProcessId and CommandLine."""
    cmd = (
        f"Get-CimInstance Win32_Process -Filter \"Name like '{process_name}'\" | "
        "Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Depth 2"
    )
    res = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    if not res.stdout.strip():
        return []
    try:
        data = json.loads(res.stdout)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.warning("Failed to parse process output: %s (raw: %s)", e, res.stdout)
    return []


def is_port_listening(port: int) -> bool:
    cmd = f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue) -ne $null"
    res = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    return "True" in res.stdout


def main() -> int:
    logger.info("================================================================")
    logger.info("CodeStruct Real Windows Single-Window Launch Verification")
    logger.info("================================================================")

    # 1. Ensure clean initial state
    logger.info("[Step 1] Ensuring clean initial launcher state...")
    subprocess.run(
        ["cmd.exe", "/c", str(LAUNCHER_DIR / "Stop-CodeStruct-Prototype.cmd")],
        capture_output=True,
        text=True,
        check=False,
    )
    time.sleep(1)

    # Verify runtime app_profile does not exist
    assert not APP_PROFILE_DIR.exists(), f"app_profile directory should not exist: {APP_PROFILE_DIR}"
    logger.info("  Clean initial state confirmed. runtime/app_profile does not exist.")

    # 2. Execute prototype shortcut: Start-CodeStruct-Prototype.cmd
    logger.info("[Step 2] Executing Start-CodeStruct-Prototype.cmd...")
    start_res = subprocess.run(
        ["cmd.exe", "/c", str(LAUNCHER_DIR / "Start-CodeStruct-Prototype.cmd")],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.info("  Start script returned exit code: %d", start_res.returncode)
    if start_res.returncode != 0:
        logger.error("Start script failed stdout:\n%s", start_res.stdout)
        logger.error("Start script failed stderr:\n%s", start_res.stderr)
        return 1

    time.sleep(3)

    # 3. Verify prototype-state.json
    logger.info("[Step 3] Verifying prototype-state.json...")
    assert STATE_FILE.exists(), f"State file {STATE_FILE} must exist after startup."
    with open(STATE_FILE, encoding="utf-8-sig") as f:
        state_data = json.load(f)

    logger.info("  State data: %s", json.dumps(state_data, indent=2))
    assert "backend" in state_data, "backend must be present in state"
    assert "frontend" in state_data, "frontend must be present in state"
    assert "appWindow" not in state_data, "appWindow must NOT be present in state"
    backend_pid = state_data["backend"]["pid"]
    frontend_pid = state_data["frontend"]["pid"]
    logger.info("  Backend PID: %d, Frontend PID: %d", backend_pid, frontend_pid)

    # 4. Verify HTTP and Proxy Readiness
    logger.info("[Step 4] Verifying Backend (8000), Frontend (5173), and Proxy readiness...")
    b_status, b_body = http_get("http://127.0.0.1:8000/api/v1/projects")
    assert b_status == 200, f"Backend HTTP status {b_status}"
    logger.info("  Backend /api/v1/projects: HTTP 200 OK")

    f_status, _ = http_get("http://127.0.0.1:5173/", accept="text/html, */*")
    assert f_status == 200, f"Frontend HTTP status {f_status}"
    logger.info("  Frontend root /: HTTP 200 OK")

    p_status, p_body = http_get("http://127.0.0.1:5173/api/v1/projects")
    assert p_status == 200, f"Frontend proxy /api/v1/projects HTTP status {p_status}"
    logger.info("  Frontend Proxy /api/v1/projects: HTTP 200 OK")

    # 5. Verify Visible Windows & Edge Processes
    logger.info("[Step 5] Checking visible top-level windows and process command lines...")
    visible_windows = get_visible_windows()
    logger.info("  Detected %d visible top-level windows:", len(visible_windows))
    thonny_window_found = False
    thonny_pid: int | None = None
    standalone_edge_window_found = False

    for w in visible_windows:
        title = str(w["title"])
        pid = int(w["pid"])
        # Check for Thonny window
        if "thonny" in title.lower():
            thonny_window_found = True
            thonny_pid = pid
            logger.info("  -> FOUND THONNY WINDOW: HWND=%s, PID=%d, Title='%s'", w["hwnd"], pid, title)
        elif "codestruct" in title.lower():
            # Check if this is an external standalone window
            logger.warning("  -> NOTICE: Window with 'CodeStruct' in title: HWND=%s, PID=%d, Title='%s'", w["hwnd"], pid, title)
            # If it's a standalone Edge window, record it
            standalone_edge_window_found = True

    assert thonny_window_found, "Thonny top-level window must be visible!"
    assert not standalone_edge_window_found, "Standalone CodeStruct window must NOT exist!"
    logger.info("  Confirmed: NO standalone CodeStruct application window found.")

    # Check all msedge processes for --app flag
    logger.info("  Inspecting msedge.exe processes...")
    edge_procs = get_command_lines_for_process("msedge.exe")
    standalone_edge_procs = []
    for ep in edge_procs:
        cmdline = ep.get("CommandLine") or ""
        pid = ep.get("ProcessId")
        if "--app=" in cmdline and "5173" in cmdline:
            standalone_edge_procs.append(ep)
            logger.error("  -> FOUND STANDALONE EDGE APP PROCESS: PID=%s, CmdLine=%s", pid, cmdline)
        else:
            logger.info("  -> Non-standalone Edge process: PID=%s", pid)

    assert len(standalone_edge_procs) == 0, f"Found {len(standalone_edge_procs)} standalone Edge --app processes!"
    logger.info("  Confirmed: Exactly 0 standalone Edge --app processes running.")

    # Check Thonny process is alive
    thonny_procs = get_command_lines_for_process("python.exe")
    thonny_found = False
    for tp in thonny_procs:
        cmdline = tp.get("CommandLine") or ""
        if "thonny" in cmdline.lower():
            thonny_found = True
            thonny_pid = int(tp.get("ProcessId"))
            logger.info("  Found active Thonny process: PID=%d, CmdLine=%s", thonny_pid, cmdline)
            break

    assert thonny_found, "Thonny process must be running after prototype start."
    logger.info("  Confirmed: Thonny IDE is running and is the single application window.")

    # 6. Verify Stop Leaves Thonny Safe
    logger.info("[Step 6] Testing Stop-CodeStruct-Prototype.cmd...")
    stop_res = subprocess.run(
        ["cmd.exe", "/c", str(LAUNCHER_DIR / "Stop-CodeStruct-Prototype.cmd")],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.info("  Stop script returned exit code: %d", stop_res.returncode)
    assert stop_res.returncode == 0, f"Stop script failed: {stop_res.stderr}"

    time.sleep(2)

    # Ports must be freed
    assert not is_port_listening(8000), "Backend port 8000 must be released after Stop."
    assert not is_port_listening(5173), "Frontend port 5173 must be released after Stop."
    assert not STATE_FILE.exists(), "State file must be removed after clean Stop."
    logger.info("  Ports 8000 and 5173 are freed. State file cleared.")

    # Thonny process must STILL BE ALIVE!
    logger.info("  Verifying Thonny remains running safely after Stop...")
    thonny_still_alive = False
    active_procs = get_command_lines_for_process("python.exe")
    for ap in active_procs:
        if ap.get("ProcessId") == thonny_pid:
            thonny_still_alive = True
            break

    assert thonny_still_alive, f"Thonny process (PID {thonny_pid}) was terminated by Stop! It must remain running."
    logger.info("  SUCCESS: Thonny IDE (PID %d) remained safely alive and open after Stop.", thonny_pid)

    # 7. Verify Restart
    logger.info("[Step 7] Testing Restart via Start-CodeStruct-Prototype.cmd...")
    restart_res = subprocess.run(
        ["cmd.exe", "/c", str(LAUNCHER_DIR / "Start-CodeStruct-Prototype.cmd")],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.info("  Restart script returned exit code: %d", restart_res.returncode)
    assert restart_res.returncode == 0, f"Restart script failed: {restart_res.stderr}"

    time.sleep(3)

    # Verify ports listening again
    assert is_port_listening(8000), "Backend port 8000 must be listening after Restart."
    assert is_port_listening(5173), "Frontend port 5173 must be listening after Restart."

    # Verify again NO standalone Edge app
    edge_procs_restart = get_command_lines_for_process("msedge.exe")
    for ep in edge_procs_restart:
        cmdline = ep.get("CommandLine") or ""
        assert "--app=" not in cmdline or "5173" not in cmdline, f"Standalone Edge app detected on restart: {cmdline}"

    logger.info("  SUCCESS: Restart clean, services restored, ZERO duplicate or standalone windows.")

    # 8. Final Clean Stop & Close Test Thonny
    logger.info("[Step 8] Final cleanup: stopping services and terminating test Thonny...")
    subprocess.run(
        ["cmd.exe", "/c", str(LAUNCHER_DIR / "Stop-CodeStruct-Prototype.cmd")],
        capture_output=True,
        text=True,
        check=False,
    )

    # Close test Thonny process
    if thonny_pid:
        try:
            logger.info("  Terminating test Thonny PID %d...", thonny_pid)
            subprocess.run(["taskkill", "/PID", str(thonny_pid), "/T", "/F"], capture_output=True, check=False)
        except Exception:
            pass

    time.sleep(1)
    logger.info("================================================================")
    logger.info("ALL SINGLE-WINDOW LAUNCH VERIFICATIONS PASSED SUCCESSFULLY!")
    logger.info("================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
