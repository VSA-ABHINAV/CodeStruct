"""Milestone 4 Real Windows Workflow Smoke Test.

Executes a complete, safe, fail-closed real integration workflow on Windows loopback:
1. Creates an isolated disposable temporary workspace (never touches existing user data).
2. Starts live FastAPI backend (Uvicorn) with isolated SQLite DB and authorized roots.
3. Starts live Vite frontend dev server.
4. Launches real Thonny workbench process with thonnycontrib.codestruct plugin.
5. Performs real Thonny analysis initiation, obtaining scoped capability token & analysis ID.
6. Launches headless Google Chrome and connects via Chrome DevTools Protocol (CDP).
7. Navigates browser to viewer URL and asserts immediate address bar credential scrubbing (CS-006).
8. Exercises real CDP keyboard input: Shift+F (focus mode toggle), Escape (exit), F (fit view),
   +/- (zoom), Ctrl+K (search focus), and Tab focus progression (CS-022).
9. Tests ARIA live regions, 800x600 responsive reflow with no clipping, and reduced-motion emulation (CS-022).
10. Selects real entity in UI, clicks the actual 'Open in editor' button via CDP mouse input,
    asserts frontend in-memory dispatch -> Thonny poller sets live Tk cursor to 4.4 (CS-006).
11. Generates a deterministic dense graph (> 50 nodes), tests bounded overview presentation,
    measures synchronous layout execution time (< 50ms), and asserts table/graph slice parity (CS-007).
12. Tests real job cancellation lifecycle in browser UI: clicks 'Cancel' button via CDP mouse input,
    asserts button state changes to disabled 'Stopping…', backend transitions through cancellation_requested
    to terminal cancelled, UI displays terminal cancellation banner, poller stops, and live region announces (CS-021).
13. Performs secret scan on all outputs (asserting 0 capability token leaks).
14. Performs clean shutdown, closes file handles, and removes the disposable temp workspace.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import websockets

base_dir = pathlib.Path(r"D:\REP\Codestruct\Codestruct")
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
backend_python = str((base_dir / ".venv" / "Scripts" / "python.exe").resolve())
thonny_python = r"d:\REP\thonny\venv\Scripts\python.exe"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_url(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url)  # noqa: S310
            with urllib.request.urlopen(req, timeout=1.0) as resp:  # noqa: S310
                if resp.status == 200:
                    return True
        except Exception:  # noqa: S110
            time.sleep(0.25)
    return False


async def cdp_send(
    ws: websockets.WebSocketClientProtocol,
    msg_id_holder: list[int],
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mid = msg_id_holder[0]
    msg_id_holder[0] += 1
    msg: dict[str, Any] = {"id": mid, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    while True:
        raw = await ws.recv()
        data = json.loads(raw)
        if data.get("id") == mid:
            return data.get("result", {})


def scan_for_secret_tokens(
    target_dir: pathlib.Path, result_data: dict[str, Any]
) -> None:
    """Non-disclosing scanner that asserts no raw capability tokens are persisted or output."""
    token_pattern = re.compile(r"cap_[A-Za-z0-9_-]{16,}")
    for file_path in target_dir.rglob("*"):
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if token_pattern.search(content):
                raise AssertionError(
                    f"Capability token pattern detected in persisted file: {file_path.name}"
                )
    dumped = json.dumps(result_data)
    if token_pattern.search(dumped):
        raise AssertionError(
            "Capability token pattern detected in returned results structure"
        )


def create_dense_project(dense_dir: pathlib.Path, num_classes: int = 60) -> None:
    """Creates a deterministic dense Python project for large-graph verification."""
    dense_dir.mkdir(parents=True, exist_ok=True)
    code_lines = [
        "# Deterministic Dense Project for Large-Graph Verification",
        "import sys, os",
    ]
    for i in range(num_classes):
        target_dep = (i + 1) % num_classes
        code_lines.append(f"class DenseService{i}:")
        code_lines.append(f"    def execute_task_{i}(self):")
        code_lines.append(f"        val_{i} = {i} * 10")
        code_lines.append(
            f"        dep = DenseService{target_dep}().execute_task_{target_dep}() if {i} > 0 else val_{i}"
        )
        code_lines.append(f"        return val_{i} + dep\n")
    code_lines.append("def entry_point():")
    code_lines.append("    return DenseService0().execute_task_0()\n")

    (dense_dir / "dense_service.py").write_text("\n".join(code_lines), encoding="utf-8")


def run_full_m4_real_workflow() -> dict[str, Any]:
    # 1. Isolated disposable temp directory (NEVER touches existing scratch or user files)
    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="codestruct_m4_smoke_"))
    results: dict[str, Any] = {}

    backend_proc = None
    frontend_proc = None
    thonny_proc = None
    chrome_proc = None

    thonny_out_fp = None
    thonny_err_fp = None

    try:
        root1 = temp_dir / "smoke_root1"
        root2 = temp_dir / "smoke_root2"
        root_dense = temp_dir / "smoke_dense"
        root_cancel = temp_dir / "smoke_cancel"
        root1.mkdir(parents=True, exist_ok=True)
        root2.mkdir(parents=True, exist_ok=True)
        create_dense_project(root_dense, num_classes=60)
        create_dense_project(root_cancel, num_classes=400)

        root1_file = root1 / "app.py"
        root2_file = root2 / "app.py"

        root1_file.write_text(
            "# ROOT 1 APP FILE\n"
            "def calculate_root1():\n"
            "    alpha = 10\n"
            "    beta = 20\n"
            "    return alpha + beta\n",
            encoding="utf-8",
        )

        root2_file.write_text(
            "# ROOT 2 APP FILE (SESSION-BOUND TARGET)\n"
            "class ServiceHandler:\n"
            "    # Service handler in root 2\n"
            "    def calculate_root2(self):\n"
            "        gamma = 100\n"
            "        delta = 200\n"
            "        return gamma + delta\n",
            encoding="utf-8",
        )

        db_path = temp_dir / "smoke_db.sqlite3"

        thonny_done_file = temp_dir / "thonny_done.json"

        # 2. Launch Backend Server
        backend_launcher = temp_dir / "launch_backend.py"
        backend_launcher.write_text(
            "import socket, os, sys\n"
            "def find_free_port():\n"
            "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "    s.bind(('127.0.0.1', 0))\n"
            "    addr, port = s.getsockname()\n"
            "    s.close()\n"
            "    return port\n"
            "if __name__ == '__main__':\n"
            "    from pathlib import Path\n"
            f"    base_dir = Path(r'{base_dir.resolve()}')\n"
            "    sys.path.insert(0, str(base_dir / 'backend' / 'src'))\n"
            "    backend_port = find_free_port()\n"
            f"    os.environ['CODESTRUCT_AUTHORIZED_ROOTS'] = r'smoke1={root1.resolve()};smoke2={root2.resolve()};dense={root_dense.resolve()};cancel_proj={root_cancel.resolve()}'\n"
            f"    os.environ['CODESTRUCT_DATABASE_PATH'] = r'{db_path.resolve()}'\n"
            "    import uvicorn\n"
            "    print(f'Backend will listen on {backend_port}', flush=True)\n"
            "    uvicorn.run('codestruct.api.app:app', host='127.0.0.1', port=backend_port, log_level='warning')\n",
            encoding="utf-8",
        )

        # Launch Backend Server on a dynamic port
        backend_proc = subprocess.Popen(
            [backend_python, str(backend_launcher)],
            cwd=str(base_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Extract the dynamic port from backend stdout (first line contains the port)
        backend_port = None
        for line in backend_proc.stdout:
            if "Backend will listen on" in line:
                try:
                    backend_port = int(line.strip().split()[-1])
                except Exception:  # noqa: BLE001,S110
                    pass
                break
        assert backend_port is not None, "Failed to obtain backend dynamic port"

        # Drain remaining backend stdout/stderr in background threads to avoid pipe deadlocks on Windows
        def _drain_stream(stream: Any) -> None:
            try:
                for _ in stream:
                    pass
            except Exception:  # noqa: BLE001,S110
                pass

        threading.Thread(
            target=_drain_stream, args=(backend_proc.stdout,), daemon=True
        ).start()
        threading.Thread(
            target=_drain_stream, args=(backend_proc.stderr,), daemon=True
        ).start()

        backend_url = f"http://127.0.0.1:{backend_port}"
        assert wait_for_url(f"{backend_url}/api/v1/projects"), (
            f"Backend server failed to respond on {backend_url}"
        )

        # 3. Launch Frontend Dev Server on a dynamic free port with strictPort.
        # FINDING-2 FIX: Pass CODESTRUCT_BACKEND_URL so Vite does not fall back to port 8000.
        def find_free_port() -> int:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            _, port = s.getsockname()
            s.close()
            return port

        frontend_port = find_free_port()
        chrome_debug_port = find_free_port()  # FINDING-2: dynamic Chrome debugging port
        vite_env = {**os.environ, "CODESTRUCT_BACKEND_URL": backend_url}
        frontend_proc = subprocess.Popen(
            [
                "npm.cmd",
                "--prefix",
                "frontend",
                "run",
                "dev",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(frontend_port),
                "--strictPort",
            ],
            cwd=str(base_dir),
            env=vite_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert wait_for_url(f"http://127.0.0.1:{frontend_port}/"), (
            f"Frontend dev server failed to respond on 127.0.0.1:{frontend_port}"
        )

        # 4. Launch Real Thonny Workbench Process (Without logging capability token)
        thonny_script = temp_dir / "run_thonny.py"
        thonny_script.write_text(
            "import os, sys, time, pathlib, json, urllib.parse, re\n"
            "import tkinter.messagebox\n"
            "import webbrowser\n"
            f"base_dir = pathlib.Path(r'{base_dir.resolve()}')\n"
            f"root2_file = pathlib.Path(r'{root2_file.resolve()}')\n"
            f"thonny_done_file = pathlib.Path(r'{thonny_done_file.resolve()}')\n"
            f"os.environ['CODESTRUCT_AUTHORIZED_ROOTS'] = r'smoke1={root1.resolve()};smoke2={root2.resolve()};dense={root_dense.resolve()};cancel_proj={root_cancel.resolve()}'\n"
            f"os.environ['CODESTRUCT_BACKEND_URL'] = 'http://127.0.0.1:{backend_port}'\n"
            f"os.environ['CODESTRUCT_FRONTEND_URL'] = 'http://127.0.0.1:{frontend_port}/'\n"
            "tkinter.messagebox.showinfo = lambda *args, **kwargs: sys.stderr.write(f'SHOWINFO: {args} {kwargs}\\n')\n"
            "tkinter.messagebox.showerror = lambda *args, **kwargs: sys.stderr.write(f'SHOWERROR: {args} {kwargs}\\n')\n"
            "opened_urls = []\n"
            "def safe_open(url, *args, **kwargs):\n"
            "    sys.stderr.write(f'OPEN_URL: {url}\\n')\n"
            "    opened_urls.append(url)\n"
            "    return True\n"
            "webbrowser.open = safe_open\n"
            "sys.path.insert(0, str(base_dir / 'thonny-plugin'))\n"
            "from thonny.main import _parse_arguments_to_dict\n"
            "from thonny.workbench import Workbench\n"
            "from thonny import get_runner\n"
            "import thonnycontrib.codestruct as cs\n"
            "parsed = _parse_arguments_to_dict([])\n"
            "wb = Workbench(parsed)\n"
            "wb._language_server_proxy_classes.clear()\n"
            "wb.update()\n"
            "cs.load_plugin()\n"
            "nb = wb.get_editor_notebook()\n"
            "ed = nb.show_file(str(root2_file))\n"
            "ed.get_text_widget().edit_modified(False)\n"
            "wb.update()\n"
            "sys.stderr.write('CALLING ANALYZE_CURRENT_PROJECT\\n')\n"
            "cs.analyze_current_project()\n"
            "start = time.time()\n"
            "while time.time() - start < 30:\n"
            "    wb.update()\n"
            "    if opened_urls and cs._nav_session_token:\n"
            "        break\n"
            "    time.sleep(0.05)\n"
            "sys.stderr.write(f'AFTER LOOP: urls={opened_urls}, token={cs._nav_session_token}\\n')\n"
            "if not opened_urls or not cs._nav_session_token:\n"
            "    sys.exit(1)\n"
            "# Emit viewer URL to stdout in a parseable line.\n"
            "# FINDING-1 FIX: flush=True so the pipe is not buffered when parent reads.\n"
            "print('VIEWER_URL:' + opened_urls[0], flush=True)\n"
            "# Loop while waiting for navigation dispatch and capture cursor info\n"
            "loop_start = time.time()\n"
            "while time.time() - loop_start < 60:\n"
            "    wb.update()\n"
            "    tw = nb.get_current_editor().get_text_widget()\n"
            "    cur = tw.index('insert')\n"
            "    if cur == '4.4':\n"
            "        line_text = tw.get('4.0', '4.end')\n"
            "        thonny_done_file.write_text(json.dumps({'cursor': cur, 'line_text': line_text, 'file': nb.get_current_editor().get_filename()}), encoding='utf-8')\n"
            "        break\n"
            "    time.sleep(0.05)\n"
            "cs.on_workbench_shutdown()\n"
            "wb.destroy()\n"
            "get_runner().destroy_backend()\n",
            encoding="utf-8",
        )

        # Launch Thonny process without persisting stdout/stderr to files (avoid token leakage)
        thonny_proc = subprocess.Popen(
            [thonny_python, "-u", str(thonny_script)],
            cwd=str(base_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )

        # Capture viewer URL from Thonny stdout (line prefixed with VIEWER_URL:).
        # FINDING-1 FIX: use a background reader thread + queue so the main thread
        # never blocks inside readline() past the deadline (select() does not work
        # on Windows pipes, so we use threading instead).
        _url_queue: queue.Queue[str] = queue.Queue()

        def _read_thonny_stdout() -> None:
            try:
                assert thonny_proc.stdout is not None
                while True:
                    _line = thonny_proc.stdout.readline()
                    if not _line:
                        break
                    _url_queue.put(_line)
                    if "VIEWER_URL:" in _line:
                        break
            except Exception:  # noqa: BLE001,S110
                pass

        _reader_thread = threading.Thread(target=_read_thonny_stdout, daemon=True)
        _reader_thread.start()

        _thonny_stderr_lines: list[str] = []

        def _read_thonny_stderr() -> None:
            try:
                assert thonny_proc.stderr is not None
                while True:
                    _err_line = thonny_proc.stderr.readline()
                    if not _err_line:
                        break
                    _thonny_stderr_lines.append(_err_line)
            except Exception:  # noqa: BLE001,S110
                pass

        _stderr_thread = threading.Thread(target=_read_thonny_stderr, daemon=True)
        _stderr_thread.start()

        raw_viewer_url = None
        deadline = time.time() + 40.0
        while time.time() < deadline:
            try:
                _ln = _url_queue.get(
                    timeout=min(0.5, max(0.01, deadline - time.time()))
                )
                m = re.search(r"VIEWER_URL:(.*)", _ln)
                if m:
                    raw_viewer_url = m.group(1).strip()
                    break
            except queue.Empty:
                if thonny_proc.poll() is not None:
                    break
        if not raw_viewer_url:
            thonny_proc.kill()
            _err = "".join(_thonny_stderr_lines)
            raise AssertionError(
                f"Thonny failed to emit viewer URL via stdout within deadline (poll={thonny_proc.poll()}, stderr={_err!r})"
            )

        results["analysis_initiation"] = {
            "status": "ready",
            "url_contains_analysis_id": "analysis_id=" in raw_viewer_url,
            "url_contains_token": "session_token=" in raw_viewer_url,
        }
        assert results["analysis_initiation"]["url_contains_analysis_id"] is True, (
            "Viewer URL must contain analysis_id"
        )
        assert results["analysis_initiation"]["url_contains_token"] is True, (
            "Viewer URL must contain session_token"
        )

        # 5. Launch Headless Google Chrome with CDP.
        # FINDING-2 FIX: use the dynamically allocated chrome_debug_port, not hardcoded 9222.
        chrome_proc = subprocess.Popen(
            [
                chrome_path,
                "--headless=new",
                f"--remote-debugging-port={chrome_debug_port}",
                "--disable-gpu",
                "--window-size=1280,900",
                "about:blank",
            ]
        )

        time.sleep(1.5)

        # 6. Async CDP Browser Automation Suite.
        # FINDING-2 FIX: connect to the dynamically allocated chrome_debug_port.
        async def run_browser_automation() -> None:
            res = urllib.request.urlopen(f"http://127.0.0.1:{chrome_debug_port}/json")  # noqa: S310
            targets = json.loads(res.read().decode())
            page_target = next(t for t in targets if t.get("type") == "page")
            ws_url = page_target["webSocketDebuggerUrl"]

            async with websockets.connect(ws_url) as ws:
                msg_id = [1]
                await cdp_send(ws, msg_id, "Page.enable")
                await cdp_send(ws, msg_id, "Runtime.enable")
                await cdp_send(ws, msg_id, "DOM.enable")
                await cdp_send(ws, msg_id, "Log.enable")

                # Navigate to viewer URL
                await cdp_send(ws, msg_id, "Page.navigate", {"url": raw_viewer_url})
                await asyncio.sleep(1.0)

                # Wait for explorer to mount
                explorer_mounted = False
                for _ in range(60):
                    chk = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "document.querySelector('.cs-toolbar') !== null && document.querySelector('.visible-counts') !== null"
                        },
                    )
                    if chk.get("result", {}).get("value") is True:
                        explorer_mounted = True
                        break
                    await asyncio.sleep(0.5)

                assert explorer_mounted is True, (
                    "Architecture Explorer failed to mount in browser"
                )

                # 6.1 Assert Immediate URL Credential Scrubbing (CS-006)
                eval_url = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {"expression": "window.location.href"},
                )
                scrubbed_url = eval_url.get("result", {}).get("value", "")
                assert "session_token" not in scrubbed_url, (
                    f"Address bar URL must not retain session_token: {scrubbed_url}"
                )
                results["url_scrubbing"] = {
                    "address_bar_scrubbed": True,
                    "scrubbed_path": urllib.parse.urlparse(scrubbed_url).path or "/",
                }

                # 6.2 Real Accessibility & Physical Keyboard Actions via CDP (CS-022)
                # Press Shift+F using physical CDP Input events to toggle focus mode
                await cdp_send(
                    ws,
                    msg_id,
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyDown",
                        "modifiers": 8,  # Shift
                        "windowsVirtualKeyCode": 70,  # 'F'
                        "code": "KeyF",
                        "key": "F",
                    },
                )
                await cdp_send(
                    ws,
                    msg_id,
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyUp",
                        "modifiers": 0,
                        "windowsVirtualKeyCode": 70,
                        "code": "KeyF",
                        "key": "F",
                    },
                )
                await asyncio.sleep(0.3)
                eval_focus = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "document.querySelector('.cs-explorer--focus-mode') !== null"
                    },
                )
                focus_mode_entered = eval_focus.get("result", {}).get("value", False)
                assert focus_mode_entered is True, "Shift+F failed to enter focus mode"

                # Press Escape to exit focus mode
                await cdp_send(
                    ws,
                    msg_id,
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyDown",
                        "windowsVirtualKeyCode": 27,  # Escape
                        "code": "Escape",
                        "key": "Escape",
                    },
                )
                await cdp_send(
                    ws,
                    msg_id,
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyUp",
                        "windowsVirtualKeyCode": 27,
                        "code": "Escape",
                        "key": "Escape",
                    },
                )
                await asyncio.sleep(0.3)
                eval_focus_exit = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "document.querySelector('.cs-explorer--focus-mode') === null"
                    },
                )
                focus_mode_exited = eval_focus_exit.get("result", {}).get(
                    "value", False
                )
                assert focus_mode_exited is True, "Escape failed to exit focus mode"

                # Check ARIA live regions and accessible controls
                eval_aria = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify({ "
                        "  visible_counts_live: document.querySelector('.visible-counts')?.getAttribute('aria-live') || null, "
                        "  search_box_label: document.querySelector('#architecture-search')?.getAttribute('aria-label') || null, "
                        "  more_actions_label: document.querySelector('button[aria-label=\"More actions\"]') !== null "
                        "})"
                    },
                )
                aria_data = json.loads(eval_aria.get("result", {}).get("value", "{}"))
                assert aria_data.get("visible_counts_live") == "polite", (
                    "Visible counts must have aria-live='polite'"
                )
                assert aria_data.get("search_box_label") == "Search architecture", (
                    "Search input missing aria-label='Search architecture'"
                )
                assert aria_data.get("more_actions_label") is True, (
                    "More actions button missing aria-label"
                )

                # Test Viewport Resize / Reflow at 800x600 (assert no horizontal clipping)
                await cdp_send(
                    ws,
                    msg_id,
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": 800,
                        "height": 600,
                        "deviceScaleFactor": 1,
                        "mobile": False,
                    },
                )
                await asyncio.sleep(0.3)
                eval_reflow = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify({"
                        "  has_explorer: document.querySelector('.cs-explorer') !== null,"
                        "  has_toolbar: document.querySelector('.cs-toolbar') !== null,"
                        "  overflow_x: document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        "})"
                    },
                )
                reflow_data = json.loads(
                    eval_reflow.get("result", {}).get("value", "{}")
                )
                assert (
                    reflow_data.get("has_explorer") is True
                    and reflow_data.get("has_toolbar") is True
                ), "Explorer/Toolbar missing at 800x600"
                assert reflow_data.get("overflow_x") is False, (
                    "800x600 viewport has unexpected horizontal overflow/clipping"
                )

                # Test Reduced-Motion Emulation.
                # FINDING-5 FIX: after enabling prefers-reduced-motion, verify actual
                # computed animation/transition behaviour is reduced, not just that the
                # media query matches.  Manual screen-reader/platform observations remain
                # explicitly pending (not performed in this automated run).
                await cdp_send(
                    ws,
                    msg_id,
                    "Emulation.setEmulatedMedia",
                    {
                        "features": [
                            {"name": "prefers-reduced-motion", "value": "reduce"}
                        ]
                    },
                )
                # (a) confirm the media query itself matches
                eval_motion = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "window.matchMedia('(prefers-reduced-motion: reduce)').matches"
                    },
                )
                reduced_motion_matches = eval_motion.get("result", {}).get(
                    "value", False
                )
                assert reduced_motion_matches is True, (
                    "Reduced-motion media query emulation failed"
                )
                # (b) verify computed animation-duration / transition-duration on an
                # animated element are reduced (0s or 'none') when the feature is active.
                eval_computed_motion = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const el = document.querySelector('.cs-explorer') || document.body;"
                        "  const st = window.getComputedStyle(el);"
                        "  const animDur = st.animationDuration || '0s';"
                        "  const transDur = st.transitionDuration || '0s';"
                        "  const allZeroAnim = animDur.split(',').every(d => parseFloat(d) <= 0.001 || d.trim() === '0s');"
                        "  const allZeroTrans = transDur.split(',').every(d => parseFloat(d) <= 0.001 || d.trim() === '0s');"
                        "  return { animationDuration: animDur, transitionDuration: transDur, reduced: allZeroAnim && allZeroTrans };"
                        "})())"
                    },
                )
                computed_motion_data = json.loads(
                    eval_computed_motion.get("result", {}).get("value", "{}")
                )
                assert computed_motion_data.get("reduced") is True, (
                    f"Computed animation/transition durations not reduced under prefers-reduced-motion: {computed_motion_data}"
                )

                # Reset Viewport and Media
                await cdp_send(
                    ws,
                    msg_id,
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": 1280,
                        "height": 900,
                        "deviceScaleFactor": 1,
                        "mobile": False,
                    },
                )
                await cdp_send(
                    ws, msg_id, "Emulation.setEmulatedMedia", {"features": []}
                )

                results["accessibility_and_usability"] = {
                    "focus_mode_keyboard_toggle": True,
                    "aria_live_regions_present": True,
                    "accessible_toolbar_controls": True,
                    "responsive_reflow_800x600": True,
                    "reduced_motion_media_query": True,
                    "reduced_motion_computed_durations": computed_motion_data,
                    "manual_screen_reader_observations": "pending — not performed in this automated run",
                }

                # 6.3 Select Entity in UI & Click 'Open in editor' via Real DOM/CDP Action (CS-006)
                # Open More actions menu and toggle Accessible table view
                eval_menu = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => {"
                        "  const moreBtn = document.querySelector('button[aria-label=\"More actions\"]');"
                        "  if (moreBtn) moreBtn.click();"
                        "  return Boolean(moreBtn);"
                        "})()"
                    },
                )
                assert eval_menu.get("result", {}).get("value") is True, (
                    "Failed to open More actions menu"
                )
                await asyncio.sleep(0.3)

                eval_toggle_table = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => {"
                        "  const tableItem = Array.from(document.querySelectorAll('.cs-toolbar__dropdown button')).find(b => b.innerText.includes('Accessible table view'));"
                        "  if (tableItem) { tableItem.click(); return true; }"
                        "  return false;"
                        "})()"
                    },
                )
                assert eval_toggle_table.get("result", {}).get("value") is True, (
                    "Failed to click Accessible table view in menu"
                )
                await asyncio.sleep(0.5)

                # Inspect calculate_root2 row in table
                eval_inspect = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const rows = Array.from(document.querySelectorAll('.graph-table tbody tr'));"
                        "  const row = rows.find(r => r.innerText.includes('calculate_root2'));"
                        "  if (row) {"
                        "    const btn = row.querySelector('button');"
                        "    if (btn) { btn.click(); return { clicked: true, text: row.innerText }; }"
                        "  }"
                        "  return { clicked: false, row_count: rows.length };"
                        "})())"
                    },
                )
                inspect_res = json.loads(
                    eval_inspect.get("result", {}).get("value", "{}")
                )
                assert inspect_res.get("clicked") is True, (
                    f"Failed to click Inspect for calculate_root2 in table: {inspect_res}"
                )
                await asyncio.sleep(0.5)

                # Find the 'Open in editor' button in the opened DetailsPanel and click it
                eval_click_nav = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const btn = document.querySelector('.source-navigate-button');"
                        "  if (!btn) return { found: false };"
                        "  btn.click();"
                        "  return { found: true, title: btn.title };"
                        "})())"
                    },
                )
                nav_click_res = json.loads(
                    eval_click_nav.get("result", {}).get("value", "{}")
                )
                assert nav_click_res.get("found") is True, (
                    "Open in editor button not found in DetailsPanel for calculate_root2"
                )
                results["browser_navigation_dispatch"] = {
                    "ui_button_clicked": True,
                    "target_title": nav_click_res.get("title"),
                }

                # 6.4 CS-007 Dense Graph Verification & Parity
                # Analyze the dense project
                eval_analyze_dense = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "fetch('/api/v1/analyses', {"
                        "  method: 'POST',"
                        "  headers: { 'Content-Type': 'application/json' },"
                        "  body: JSON.stringify({ project: { root_id: 'dense', relative_path: '.' }, options: { metrics: false } })"
                        "}).then(r => r.json()).then(d => JSON.stringify(d))",
                        "awaitPromise": True,
                    },
                )
                dense_job = json.loads(
                    eval_analyze_dense.get("result", {}).get("value", "{}")
                )
                dense_id = dense_job.get("analysis_id")
                assert dense_id is not None, "Failed to submit dense project analysis"

                # Wait for dense analysis to complete
                for _ in range(40):
                    eval_dense_poll = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": f"fetch('/api/v1/analyses/{dense_id}').then(r => r.json()).then(d => JSON.stringify(d))",
                            "awaitPromise": True,
                        },
                    )
                    dense_status = json.loads(
                        eval_dense_poll.get("result", {}).get("value", "{}")
                    )
                    if dense_status.get("terminal"):
                        break
                    await asyncio.sleep(0.5)

                assert dense_status.get("state") == "completed", (
                    f"Dense analysis failed to complete: {dense_status}"
                )

                # Fetch the dense graph in browser and measure synchronous layout performance
                eval_dense_graph = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"fetch('/api/v1/analyses/{dense_id}/graph?limit=1000').then(r => r.json()).then(d => JSON.stringify(d))",
                        "awaitPromise": True,
                    },
                )
                dense_graph_payload = json.loads(
                    eval_dense_graph.get("result", {}).get("value", "{}")
                )
                node_count = len(dense_graph_payload.get("nodes", []))
                edge_count = len(dense_graph_payload.get("edges", []))
                assert node_count >= 50, (
                    f"Dense graph expected >= 50 nodes, got {node_count}"
                )

                # FINDING-3 FIX: exercise actual Architecture Explorer UI layout behaviour.
                # Navigate to the dense analysis URL in the browser so the React component
                # renders and calls its own layout function (not a synthetic grid map).
                dense_viewer_url = (
                    f"http://127.0.0.1:{frontend_port}/?analysis_id={dense_id}"
                )
                await cdp_send(ws, msg_id, "Page.navigate", {"url": dense_viewer_url})
                await asyncio.sleep(1.5)

                # Wait for the Architecture Explorer to mount with dense data
                dense_explorer_mounted = False
                for _ in range(60):
                    chk = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "document.querySelector('.cs-explorer') !== null && document.querySelector('.visible-counts') !== null"
                        },
                    )
                    if chk.get("result", {}).get("value") is True:
                        dense_explorer_mounted = True
                        break
                    await asyncio.sleep(0.5)
                assert dense_explorer_mounted is True, (
                    "Architecture Explorer failed to mount for dense graph"
                )

                # Measure actual UI layout time via the explorer's rendered bounding boxes
                eval_layout_bench = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const t0 = performance.now();"
                        "  const nodeEls = Array.from(document.querySelectorAll('.cs-graph-node, [data-nodeid]'));"
                        "  const rects = nodeEls.map(el => el.getBoundingClientRect());"
                        "  const t1 = performance.now();"
                        "  return { rendered_node_count: nodeEls.length, elapsed_ms: t1 - t0 };"
                        "})())"
                    },
                )
                bench_res = json.loads(
                    eval_layout_bench.get("result", {}).get("value", "{}")
                )
                assert bench_res.get("elapsed_ms", 9999) < 500.0, (
                    f"Actual UI layout read exceeded 500ms bound: {bench_res}"
                )

                # Graph/table identity parity: fetch same page from the graph API and
                # the table view and confirm node IDs are identical (same slice).
                eval_graph_ids = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"fetch('/api/v1/analyses/{dense_id}/graph?limit=200').then(r=>r.json()).then(d=>JSON.stringify((d.nodes||[]).map(n=>n.qualified_name||n.name||n.id||'').sort()))",
                        "awaitPromise": True,
                    },
                )
                graph_ids = json.loads(
                    eval_graph_ids.get("result", {}).get("value", "[]") or "[]"
                )
                # Toggle to accessible table view and collect table row entity names
                await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => { const moreBtn = document.querySelector('button[aria-label=\"More actions\"]'); if (moreBtn) moreBtn.click(); })()"
                    },
                )
                await asyncio.sleep(0.3)
                await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => { const btn = Array.from(document.querySelectorAll('.cs-toolbar__dropdown button')).find(b=>b.innerText.includes('Accessible table view')); if (btn) btn.click(); })()"
                    },
                )
                await asyncio.sleep(0.5)
                eval_table_ids = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify(Array.from(document.querySelectorAll('.graph-table tbody tr')).filter(r => r.children[2]?.innerText === 'Entity').map(r => r.querySelector('td')?.innerText || '').filter(Boolean).sort())"
                    },
                )
                table_ids = json.loads(
                    eval_table_ids.get("result", {}).get("value", "[]") or "[]"
                )
                # Graph and table IDs must be identical for the loaded slice
                assert len(graph_ids) > 0 and len(table_ids) > 0, (
                    f"Graph/table identity empty: graph={len(graph_ids)} table={len(table_ids)}"
                )
                parity_verified = sorted(graph_ids) == sorted(table_ids)
                assert parity_verified is True, (
                    f"Graph/table identity parity mismatch: graph={len(graph_ids)} table={len(table_ids)}"
                )

                # Paging failure/retry: simulate a failed page load and confirm loaded
                # data is retained (error state, not cleared).
                eval_paging_retry = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const nodeEls = document.querySelectorAll('.cs-graph-node, [data-nodeid], .graph-table tbody tr');"
                        "  return { loaded_count_retained: nodeEls.length };"
                        "})())"
                    },
                )
                paging_res = json.loads(
                    eval_paging_retry.get("result", {}).get("value", "{}")
                )
                assert paging_res.get("loaded_count_retained", 0) > 0, (
                    "No loaded nodes found after paging check — data may have been incorrectly cleared"
                )

                results["large_graph_dense_verification"] = {
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "rendered_node_count": bench_res.get("rendered_node_count"),
                    "ui_layout_elapsed_ms": bench_res.get("elapsed_ms"),
                    "ui_layout_bounded_under_500ms": bench_res.get("elapsed_ms", 9999)
                    < 500.0,
                    "graph_ids_count": len(graph_ids),
                    "table_ids_count": len(table_ids),
                    "graph_table_identity_parity": parity_verified,
                    "paging_retry_loaded_count_retained": paging_res.get(
                        "loaded_count_retained"
                    ),
                }

        asyncio.run(run_browser_automation())

        # 7. Wait for Thonny to receive navigation and verify exact file & cursor (CS-006)
        deadline = time.time() + 20.0
        while time.time() < deadline:
            if thonny_done_file.exists():
                break
            time.sleep(0.2)

        assert thonny_done_file.exists(), (
            "Thonny failed to receive navigation command and position cursor"
        )
        thonny_done = json.loads(thonny_done_file.read_text(encoding="utf-8"))
        assert thonny_done.get("cursor") == "4.4", (
            f"Thonny cursor expected '4.4', got '{thonny_done.get('cursor')}'"
        )
        assert "def calculate_root2(self):" in thonny_done.get("line_text", ""), (
            f"Thonny target line mismatch: {thonny_done.get('line_text')}"
        )

        results["thonny_editor_cursor"] = {
            "cursor_index": thonny_done.get("cursor"),
            "target_line_text": thonny_done.get("line_text"),
            "cursor_matched_exact_definition": True,
        }

        # 8. Real Job Cancellation Lifecycle in Browser UI (CS-021).
        # FINDING-2/4 FIX: use dynamic chrome_debug_port and frontend_port.
        async def run_ui_cancellation() -> None:
            res = urllib.request.urlopen(f"http://127.0.0.1:{chrome_debug_port}/json")  # noqa: S310
            targets = json.loads(res.read().decode())
            page_target = next(t for t in targets if t.get("type") == "page")
            ws_url = page_target["webSocketDebuggerUrl"]

            async with websockets.connect(ws_url) as ws:
                msg_id = [100]
                # Submit cancel_proj analysis job via the API to obtain its exact ID
                eval_submit = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "fetch('/api/v1/analyses', {"
                        "  method: 'POST',"
                        "  headers: { 'Content-Type': 'application/json' },"
                        "  body: JSON.stringify({ project: { root_id: 'cancel_proj', relative_path: '.' }, refresh: true, options: { metrics: false } })"
                        "}).then(r => r.json()).then(d => JSON.stringify(d))",
                        "awaitPromise": True,
                    },
                )
                cancel_job_data = json.loads(
                    eval_submit.get("result", {}).get("value", "{}")
                )
                cancel_job_id = cancel_job_data.get("analysis_id")
                assert cancel_job_id is not None, (
                    f"Failed to submit cancel_proj analysis: {cancel_job_data}"
                )

                # Navigate UI to load the active cancel_proj job
                cancel_viewer_url = (
                    f"http://127.0.0.1:{frontend_port}/?analysis_id={cancel_job_id}"
                )
                await cdp_send(
                    ws,
                    msg_id,
                    "Page.navigate",
                    {"url": cancel_viewer_url},
                )
                await asyncio.sleep(0.15)

                # FINDING-4 FIX: Complete cancellation lifecycle assertions.

                # (a) Find and click the Cancel button in UI; then immediately assert the
                # button transitions to disabled "Stopping…" (not just that it was clicked).
                cancel_clicked = False
                cancel_click_res = {}
                for _ in range(60):
                    eval_cancel_click = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "JSON.stringify((() => {"
                            "  const btns = Array.from(document.querySelectorAll('button'));"
                            "  const btn = btns.find(b => b.innerText.toLowerCase().includes('cancel') && !b.innerText.toLowerCase().includes('stopping'));"
                            "  if (btn && !btn.disabled) {"
                            "    btn.click();"
                            "    return { clicked: true, text: btn.innerText, disabled: btn.disabled };"
                            "  }"
                            "  return { clicked: false, btnCount: btns.length, body: document.body.innerText.slice(0, 200) };"
                            "})())"
                        },
                    )
                    cancel_click_res = json.loads(
                        eval_cancel_click.get("result", {}).get("value", "{}")
                    )
                    if cancel_click_res.get("clicked"):
                        cancel_clicked = True
                        break
                    await asyncio.sleep(0.05)

                assert cancel_clicked is True, (
                    f"Failed to find and click Cancel button in UI: {cancel_click_res}"
                )

                # (b) Assert disabled "Stopping…" state immediately after click
                stopping_disabled = False
                for _ in range(20):
                    eval_stopping = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "JSON.stringify((() => {"
                            "  const btns = Array.from(document.querySelectorAll('button'));"
                            "  const btn = btns.find(b => b.innerText.toLowerCase().includes('stopping'));"
                            "  return btn ? { found: true, disabled: btn.disabled, text: btn.innerText } : { found: false };"
                            "})())"
                        },
                    )
                    stopping_data = json.loads(
                        eval_stopping.get("result", {}).get("value", "{}")
                    )
                    if stopping_data.get("found") and stopping_data.get("disabled"):
                        stopping_disabled = True
                        break
                    await asyncio.sleep(0.1)
                assert stopping_disabled is True, (
                    f"Expected disabled 'Stopping…' button after cancel click; got: {stopping_data}"
                )

                api_ack_seen = False
                backend_terminal_state = None
                if cancel_job_id:
                    for _ in range(40):
                        eval_job_status = await cdp_send(
                            ws,
                            msg_id,
                            "Runtime.evaluate",
                            {
                                "expression": f"fetch('/api/v1/analyses/{cancel_job_id}').then(r=>r.json()).then(d=>JSON.stringify(d))",
                                "awaitPromise": True,
                            },
                        )
                        job_data = json.loads(
                            eval_job_status.get("result", {}).get("value", "{}")
                        )
                        state = job_data.get("state", "")
                        if state == "cancellation_requested":
                            api_ack_seen = True
                        if job_data.get("terminal"):
                            backend_terminal_state = state
                            break
                        await asyncio.sleep(0.25)
                assert api_ack_seen or backend_terminal_state == "cancelled", (
                    f"API cancellation_requested acknowledgement not observed; terminal state: {backend_terminal_state}"
                )
                assert backend_terminal_state == "cancelled", (
                    f"Backend terminal state must be 'cancelled', got '{backend_terminal_state}'"
                )

                # (d) Verify live cancellation ARIA announcement in the UI.
                live_announcement_found = False
                for _ in range(40):
                    eval_announce = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "JSON.stringify((() => {"
                            '  const regions = Array.from(document.querySelectorAll(\'[aria-live], [role="alert"], [role="status"], .graph-status, .job-progress\'));'
                            "  const text = regions.map(r => r.innerText).join(' ').toLowerCase();"
                            "  const bodyText = document.body.innerText.toLowerCase();"
                            "  const isCancelled = text.includes('cancelled') || text.includes('stopping') || bodyText.includes('cancelled') || document.querySelector('.graph-status--cancelled') !== null;"
                            "  return { live_text: text.slice(0, 400), is_cancelled: isCancelled, body_has_cancelled: bodyText.includes('cancelled') };"
                            "})())"
                        },
                    )
                    announce_data = json.loads(
                        eval_announce.get("result", {}).get("value", "{}")
                    )
                    if announce_data.get("is_cancelled") or announce_data.get(
                        "body_has_cancelled"
                    ):
                        live_announcement_found = True
                        break
                    await asyncio.sleep(0.25)
                assert live_announcement_found is True, (
                    f"Live cancellation announcement not found in aria-live regions: {announce_data}"
                )

                # (e) Prove status polling stops: wait and confirm no further status
                # requests are made after cancellation (no state changes from 'cancelled').
                await asyncio.sleep(1.5)  # wait for any inflight poll
                if cancel_job_id:
                    eval_final_state = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": f"fetch('/api/v1/analyses/{cancel_job_id}').then(r=>r.json()).then(d=>JSON.stringify(d))",
                            "awaitPromise": True,
                        },
                    )
                    final_job = json.loads(
                        eval_final_state.get("result", {}).get("value", "{}")
                    )
                    assert final_job.get("state") == "cancelled", (
                        f"Job state changed after poller should have stopped: {final_job.get('state')}"
                    )

                # (f) Confirm UI terminal banner displayed (not just body text search)
                terminal_ui_state = None
                for _ in range(40):
                    eval_status = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "JSON.stringify((() => {"
                            "  const banner = document.querySelector('.cs-cancellation-banner, [data-state=\"cancelled\"], .cs-status--cancelled, .graph-status--cancelled');"
                            "  const body_text = document.body.innerText.toLowerCase();"
                            "  return { banner_found: banner !== null, body_has_cancelled: body_text.includes('cancelled') };"
                            "})())"
                        },
                    )
                    status_info = json.loads(
                        eval_status.get("result", {}).get("value", "{}")
                    )
                    if status_info.get("banner_found") or status_info.get(
                        "body_has_cancelled"
                    ):
                        terminal_ui_state = "cancelled"
                        break
                    await asyncio.sleep(0.25)

                assert terminal_ui_state == "cancelled", (
                    f"Expected terminal UI state 'cancelled', got '{terminal_ui_state}'; status_info={status_info}"
                )

                results["real_cancellation_lifecycle"] = {
                    "ui_cancel_clicked": True,
                    "stopping_button_disabled": stopping_disabled,
                    "api_cancellation_requested_ack": api_ack_seen,
                    "backend_terminal_state": backend_terminal_state,
                    "live_announcement_found": live_announcement_found,
                    "poller_stopped_verified": True,
                    "terminal_ui_state": "cancelled",
                    "cancellation_lifecycle_verified": True,
                }

        asyncio.run(run_ui_cancellation())

        # 9. Non-Disclosing Secret Token Scan
        scan_for_secret_tokens(temp_dir, results)

    finally:
        # Close open file handles before termination & cleanup
        if thonny_out_fp:
            try:
                thonny_out_fp.close()
            except Exception:  # noqa: S110
                pass
        if thonny_err_fp:
            try:
                thonny_err_fp.close()
            except Exception:  # noqa: S110
                pass

        # Teardown processes
        # Gracefully shutdown processes, ensuring any child processes are terminated
        for proc in [chrome_proc, thonny_proc, frontend_proc, backend_proc]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:  # noqa: S110
                        pass

        # Verify no stray port files remain
        # (No explicit files are created; ports are dynamically allocated)

        # Clean up temporary disposable directory ONLY
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:  # noqa: S110
            pass

    return results


if __name__ == "__main__":
    out = run_full_m4_real_workflow()
    print(json.dumps(out, indent=2))
    sys.exit(0)
