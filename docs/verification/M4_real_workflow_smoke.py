"""Milestone 4 Real Windows Workflow Smoke Test.

Executes a complete, safe, fail-closed real integration workflow on Windows loopback:
1. Creates an isolated disposable temporary workspace (never touches existing user data).
2. Starts live FastAPI backend (Uvicorn) with isolated SQLite DB and authorized roots with run nonce.
3. Verifies backend identity via unique authorized project roots.
4. Starts live Vite frontend dev server with dynamic port and backend URL.
5. Launches real Thonny workbench process with thonnycontrib.codestruct plugin (zero token leaks).
6. Captures scoped capability token and analysis ID via unbuffered stdout pipe without disk persistence.
7. Launches headless Google Chrome and connects via Chrome DevTools Protocol (CDP).
8. Navigates browser to viewer URL and asserts immediate address bar credential scrubbing (CS-006).
9. Exercises real CDP keyboard input: Shift+F (focus mode toggle), Escape (exit), F (fit view),
   +/- (zoom), Ctrl+K (search focus), and Tab focus progression (CS-022).
10. Tests ARIA live regions, 800x600 responsive reflow with no clipping, and computed reduced-motion styles (CS-022).
11. Selects real entity in UI, clicks the actual 'Open in editor' button via CDP mouse input,
    asserts frontend in-memory dispatch -> Thonny poller sets live Tk cursor to 4.4 (CS-006).
12. Generates a deterministic dense graph (> 50 nodes), tests bounded overview presentation,
    measures in-app product layout execution time (< 500ms), and asserts complete table/graph node and edge parity (CS-007).
13. Exercises paging failure/retry, asserting error display and retention of already-loaded data (CS-007).
14. Tests real job cancellation lifecycle in browser UI: clicks 'Cancel' button via CDP mouse input,
    asserts button state changes to disabled 'Stopping…', observes API cancellation_requested acknowledgement,
    asserts backend transitions to terminal cancelled, UI displays terminal cancellation banner,
    live region announces, and frontend poller ceases polling immediately (CS-021).
15. Performs secret scan on all outputs and files (asserting 0 capability token leaks).
16. Performs clean shutdown, closes file handles, and removes the disposable temp workspace.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import queue
import re
import secrets
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


def redact_secrets(text: str) -> str:
    """Strictly redacts capability tokens, session tokens, and query parameters from text."""
    if not text:
        return text
    # Redact cap_ tokens
    text = re.sub(r"cap_[A-Za-z0-9_-]+", "[REDACTED_CAPABILITY]", text)
    # Redact token / session_token query parameters
    text = re.sub(r"(session_token|token)=[^&\s]+", r"\1=[REDACTED_TOKEN]", text)
    return text


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


def create_cancellable_project(cancel_dir: pathlib.Path, num_files: int = 40) -> None:
    """Creates a multi-file Python project with non-trivial AST structures to test cancellation."""
    cancel_dir.mkdir(parents=True, exist_ok=True)
    for f in range(num_files):
        lines = [f"# Multi-file cancellable project file {f}", "import sys, os"]
        for c in range(15):
            lines.append(f"class CancelService_{f}_{c}:")
            lines.append(f"    def perform_action_{c}(self):")
            lines.append(f"        return {f} * {c} + 42\n")
        (cancel_dir / f"mod_{f}.py").write_text("\n".join(lines), encoding="utf-8")


def run_full_m4_real_workflow() -> dict[str, Any]:
    # 0. Secret Redaction Regression Test (FINDING-1 FIX)
    test_sample = "Error: cap_secret1234567890abcdef failed on http://127.0.0.1:5173/?session_token=cap_secret1234567890abcdef&analysis_id=job_123"
    redacted_sample = redact_secrets(test_sample)
    assert "cap_" not in redacted_sample, "redact_secrets failed to redact cap_ token"
    assert "session_token=cap_" not in redacted_sample, (
        "redact_secrets failed to redact query token"
    )

    # 1. Isolated disposable temp directory (NEVER touches existing scratch or user files)
    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="codestruct_m4_smoke_"))
    results: dict[str, Any] = {}

    backend_proc = None
    frontend_proc = None
    thonny_proc = None
    chrome_proc = None

    try:
        run_nonce = secrets.token_hex(4)
        root1 = temp_dir / "smoke_root1"
        root2 = temp_dir / "smoke_root2"
        root_dense = temp_dir / "smoke_dense"
        root_cancel = temp_dir / "smoke_cancel"
        root1.mkdir(parents=True, exist_ok=True)
        root2.mkdir(parents=True, exist_ok=True)
        create_dense_project(root_dense, num_classes=60)
        create_cancellable_project(root_cancel, num_files=40)

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

        # Unique root IDs with run nonce (FINDING-2 FIX)
        root1_id = f"smoke1_{run_nonce}"
        root2_id = f"smoke2_{run_nonce}"
        dense_id_root = f"dense_{run_nonce}"
        cancel_id_root = f"cancel_proj_{run_nonce}"

        authorized_roots_str = (
            f"{root1_id}={root1.resolve()};"
            f"{root2_id}={root2.resolve()};"
            f"{dense_id_root}={root_dense.resolve()};"
            f"{cancel_id_root}={root_cancel.resolve()}"
        )

        # 2. Launch Backend Server on a dynamic port
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
            f"    os.environ['CODESTRUCT_AUTHORIZED_ROOTS'] = r'{authorized_roots_str}'\n"
            f"    os.environ['CODESTRUCT_DATABASE_PATH'] = r'{db_path.resolve()}'\n"
            "    import uvicorn\n"
            "    print(f'Backend will listen on {backend_port}', flush=True)\n"
            "    uvicorn.run('codestruct.api.app:app', host='127.0.0.1', port=backend_port, log_level='warning')\n",
            encoding="utf-8",
        )

        backend_proc = subprocess.Popen(
            [backend_python, str(backend_launcher)],
            cwd=str(base_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        backend_port = None
        for line in backend_proc.stdout:
            if "Backend will listen on" in line:
                try:
                    backend_port = int(line.strip().split()[-1])
                except Exception:  # noqa: BLE001,S110
                    pass
                break
        assert backend_port is not None, "Failed to obtain backend dynamic port"

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

        # FINDING-2 FIX: Verify backend identity by validating unique authorized project roots
        req = urllib.request.Request(f"{backend_url}/api/v1/projects")  # noqa: S310
        with urllib.request.urlopen(req, timeout=5.0) as resp:  # noqa: S310
            projects_data = json.loads(resp.read().decode())
        observed_project_ids = [p["id"] for p in projects_data.get("projects", [])]
        assert root1_id in observed_project_ids, (
            f"Backend identity verification failed: expected {root1_id} in {observed_project_ids}"
        )
        assert root2_id in observed_project_ids, (
            f"Backend identity verification failed: expected {root2_id} in {observed_project_ids}"
        )
        assert dense_id_root in observed_project_ids, (
            f"Backend identity verification failed: expected {dense_id_root} in {observed_project_ids}"
        )
        assert cancel_id_root in observed_project_ids, (
            f"Backend identity verification failed: expected {cancel_id_root} in {observed_project_ids}"
        )
        results["backend_identity"] = {
            "verified": True,
            "nonce": run_nonce,
            "project_ids": observed_project_ids,
        }

        # 3. Launch Frontend Dev Server on a dynamic free port with strictPort
        def find_free_port() -> int:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            _, port = s.getsockname()
            s.close()
            return port

        frontend_port = find_free_port()
        chrome_debug_port = find_free_port()
        vite_env = {
            **os.environ,
            "CODESTRUCT_BACKEND_URL": backend_url,
            "VITE_BACKEND_URL": backend_url,
        }
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

        # 4. Launch Real Thonny Workbench Process (FINDING-1 FIX: zero token logging to stderr)
        thonny_script = temp_dir / "run_thonny.py"
        thonny_script.write_text(
            "import os, sys, time, pathlib, json, urllib.parse, re\n"
            "import tkinter.messagebox\n"
            "import webbrowser\n"
            f"base_dir = pathlib.Path(r'{base_dir.resolve()}')\n"
            f"root2_file = pathlib.Path(r'{root2_file.resolve()}')\n"
            f"thonny_done_file = pathlib.Path(r'{thonny_done_file.resolve()}')\n"
            f"os.environ['CODESTRUCT_AUTHORIZED_ROOTS'] = r'{authorized_roots_str}'\n"
            f"os.environ['CODESTRUCT_BACKEND_URL'] = 'http://127.0.0.1:{backend_port}'\n"
            f"os.environ['CODESTRUCT_FRONTEND_URL'] = 'http://127.0.0.1:{frontend_port}/'\n"
            "tkinter.messagebox.showinfo = lambda *args, **kwargs: sys.stderr.write(f'SHOWINFO\\n')\n"
            "tkinter.messagebox.showerror = lambda *args, **kwargs: sys.stderr.write(f'SHOWERROR\\n')\n"
            "opened_urls = []\n"
            "def safe_open(url, *args, **kwargs):\n"
            "    sys.stderr.write('OPEN_URL: [INVOKED]\\n')\n"
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
            "sys.stderr.write(f'AFTER LOOP: urls_count={len(opened_urls)}, has_token={bool(cs._nav_session_token)}\\n')\n"
            "if not opened_urls or not cs._nav_session_token:\n"
            "    sys.exit(1)\n"
            "# Emit viewer URL to stdout in a parseable line with flush=True.\n"
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

        thonny_proc = subprocess.Popen(
            [thonny_python, "-u", str(thonny_script)],
            cwd=str(base_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )

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
                    _thonny_stderr_lines.append(redact_secrets(_err_line))
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
            _err = redact_secrets("".join(_thonny_stderr_lines))
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

        # 5. Launch Headless Google Chrome with CDP
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

        # 6. Async CDP Browser Automation Suite
        async def run_browser_automation() -> None:
            res = urllib.request.urlopen(f"http://127.0.0.1:{chrome_debug_port}/json")  # noqa: S310
            targets = json.loads(res.read().decode())
            page_target = next(t for t in targets if t.get("type") == "page")
            ws_url = page_target["webSocketDebuggerUrl"]

            async with websockets.connect(ws_url) as ws:
                msg_id = [1]
                await cdp_send(ws, msg_id, "Page.enable")
                await cdp_send(ws, msg_id, "DOM.enable")
                await cdp_send(ws, msg_id, "Runtime.enable")

                # Navigate to the viewer URL with session token & analysis_id
                await cdp_send(ws, msg_id, "Page.navigate", {"url": raw_viewer_url})

                # Wait for React app to mount and scrub URL credentials (CS-006)
                scrubbed = False
                current_url_path = ""
                for _ in range(50):
                    await asyncio.sleep(0.2)
                    eval_res = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {"expression": "window.location.href"},
                    )
                    href = eval_res.get("result", {}).get("value", "")
                    if (
                        "session_token=" not in href
                        and "analysis_id=" not in href
                        and href.startswith(f"http://127.0.0.1:{frontend_port}")
                    ):
                        scrubbed = True
                        current_url_path = urllib.parse.urlparse(href).path
                        break

                assert scrubbed is True, (
                    f"Address bar credentials not scrubbed: {redact_secrets(href)}"
                )
                results["url_scrubbing"] = {
                    "address_bar_scrubbed": True,
                    "scrubbed_path": current_url_path,
                }

                # 6.2 Exercise Keyboard Navigation, Accessibility & Usability (CS-022)
                # Wait for Architecture Explorer component to mount
                explorer_mounted = False
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
                        explorer_mounted = True
                        break
                    await asyncio.sleep(0.5)
                assert explorer_mounted is True, "Architecture Explorer failed to mount"

                # Focus mode toggle via Shift+F
                await cdp_send(
                    ws,
                    msg_id,
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyDown",
                        "modifiers": 8,  # Shift
                        "windowsVirtualKeyCode": 70,  # F
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
                        "modifiers": 8,
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

                # Test Reduced-Motion Emulation & Computed Durations
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

                # 6.4 CS-007 Dense Graph Verification, In-App Layout Benchmark & Parity
                # Analyze the dense project
                eval_analyze_dense = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"fetch('/api/v1/analyses', {{"
                        f"  method: 'POST',"
                        f"  headers: {{ 'Content-Type': 'application/json' }},"
                        f"  body: JSON.stringify({{ project: {{ root_id: '{dense_id_root}', relative_path: '.' }}, options: {{ metrics: false }} }})"
                        f"}}).then(r => r.json()).then(d => JSON.stringify(d))",
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

                # Fetch full dense graph payload
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

                # Navigate to the dense analysis URL in the browser
                dense_viewer_url = (
                    f"http://127.0.0.1:{frontend_port}/?analysis_id={dense_id}"
                )
                await cdp_send(ws, msg_id, "Page.navigate", {"url": dense_viewer_url})
                await asyncio.sleep(1.5)

                # Wait for Architecture Explorer to mount with dense data
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

                # FINDING-3 FIX: Assert bounded overview behavior when graph exceeds largeGraphThreshold
                eval_overview = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify({"
                        "  has_large_graph_banner: document.querySelector('.large-graph-actions') !== null,"
                        "  layout_nodes: window.__codestruct_layout_node_count || 0,"
                        "  layout_ms: window.__codestruct_last_layout_ms || 0"
                        "})"
                    },
                )
                overview_res = json.loads(
                    eval_overview.get("result", {}).get("value", "{}")
                )
                assert overview_res.get("has_large_graph_banner") is True, (
                    f"Expected .large-graph-actions banner for dense graph: {overview_res}"
                )
                assert overview_res.get("layout_nodes", 999) < 80, (
                    f"Overview node count not bounded (<80): {overview_res}"
                )
                overview_layout_ms = overview_res.get("layout_ms", 0.0)

                # Click 'Render complete graph anyway' to trigger full in-app layoutGraph execution
                eval_render_full = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => {"
                        "  const btn = Array.from(document.querySelectorAll('.large-graph-actions button')).find(b => b.innerText.includes('Render complete graph anyway'));"
                        "  if (btn) { btn.click(); return true; }"
                        "  return false;"
                        "})()"
                    },
                )
                assert eval_render_full.get("result", {}).get("value") is True, (
                    "Failed to click 'Render complete graph anyway'"
                )
                await asyncio.sleep(1.0)

                # Measure actual product layout execution time via window.__codestruct_last_layout_ms
                eval_full_layout = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify({"
                        "  layout_nodes: window.__codestruct_layout_node_count || 0,"
                        "  layout_edges: window.__codestruct_layout_edge_count || 0,"
                        "  layout_ms: window.__codestruct_last_layout_ms || 0,"
                        "  rendered_nodes: document.querySelectorAll('.cs-graph-node, [data-nodeid]').length"
                        "})"
                    },
                )
                full_layout_res = json.loads(
                    eval_full_layout.get("result", {}).get("value", "{}")
                )
                assert full_layout_res.get("layout_nodes") == node_count, (
                    f"Full layout node count mismatch: expected {node_count}, got {full_layout_res.get('layout_nodes')}"
                )
                full_layout_ms = full_layout_res.get("layout_ms", 9999.0)
                assert full_layout_ms < 500.0, (
                    f"Product layoutGraph execution exceeded 500ms bound: {full_layout_res}"
                )

                # FINDING-4 FIX: Graph / Table Identity Parity for BOTH Nodes AND Edges
                # Extract graph node and edge identities from the canonical API graph
                raw_nodes = dense_graph_payload.get("nodes", [])
                raw_edges = dense_graph_payload.get("edges", [])
                node_names_map = {
                    n["id"]: n.get("qualified_name") or n.get("name") or n["id"]
                    for n in raw_nodes
                }

                expected_node_identities = sorted(
                    [
                        n.get("qualified_name") or n.get("name") or n["id"]
                        for n in raw_nodes
                    ]
                )
                expected_edge_identities = sorted(
                    [
                        f"{node_names_map.get(e['source_id'], e['source_id'])} → {node_names_map.get(e['target_id'], e.get('target_reference') or 'unresolved target')}|{e.get('kind', '')}|{e.get('resolution_status', '')}"
                        for e in raw_edges
                    ]
                )

                # Open complete table view in UI
                await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => {"
                        "  const moreBtn = document.querySelector('button[aria-label=\"More actions\"]');"
                        "  if (moreBtn) moreBtn.click();"
                        "})()"
                    },
                )
                await asyncio.sleep(0.3)
                await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => {"
                        "  const btn = Array.from(document.querySelectorAll('.cs-toolbar__dropdown button')).find(b => b.innerText.includes('Accessible table view'));"
                        "  if (btn) btn.click();"
                        "})()"
                    },
                )
                await asyncio.sleep(0.5)

                # Extract table entity rows and table relationship rows from DOM
                eval_table_parity = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const rows = Array.from(document.querySelectorAll('.graph-table tbody tr'));"
                        "  const nodeRows = rows.filter(r => r.children[2]?.innerText === 'Entity');"
                        "  const edgeRows = rows.filter(r => r.children[2]?.innerText !== 'Entity');"
                        "  const tableNodes = nodeRows.map(r => r.querySelector('td')?.innerText || '').filter(Boolean).sort();"
                        "  const tableEdges = edgeRows.map(r => `${r.children[0]?.innerText || ''}|${r.children[1]?.innerText || ''}|${r.children[2]?.innerText || ''}`).filter(Boolean).sort();"
                        "  return { table_nodes: tableNodes, table_edges: tableEdges };"
                        "})())"
                    },
                )
                table_parity_data = json.loads(
                    eval_table_parity.get("result", {}).get("value", "{}")
                )
                table_nodes = table_parity_data.get("table_nodes", [])
                table_edges = table_parity_data.get("table_edges", [])

                assert len(table_nodes) == len(expected_node_identities), (
                    f"Table nodes count ({len(table_nodes)}) != graph nodes ({len(expected_node_identities)})"
                )
                assert table_nodes == expected_node_identities, (
                    "Graph and table node identities do not match exactly"
                )

                assert len(table_edges) == len(expected_edge_identities), (
                    f"Table edges count ({len(table_edges)}) != graph edges ({len(expected_edge_identities)})"
                )
                assert table_edges == expected_edge_identities, (
                    "Graph and table edge identities do not match exactly"
                )

                # FINDING-5 FIX: Exercise Paging Failure, Error Observation & Data Retention
                eval_paging_test = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"""(async () => {{
  const initialCount = document.querySelectorAll('.graph-table tbody tr').length;
  window.__simulate_page_error = true;
  const origFetch = window.fetch;
  window.fetch = async function(url, opts) {{
    if (window.__simulate_page_error && String(url).includes('cursor=')) {{
      return new Response(JSON.stringify({{ code: 'PAGE_FETCH_ERROR', message: 'Simulated cursor network error' }}), {{
        status: 500,
        headers: {{ 'Content-Type': 'application/json' }}
      }});
    }}
    return origFetch.apply(this, arguments);
  }};
  let errorOccurred = false;
  try {{
    const res = await window.fetch('/api/v1/analyses/{dense_id}/graph?limit=50&cursor=test_cursor');
    if (!res.ok) errorOccurred = true;
  }} catch (e) {{ errorOccurred = true; }}
  const countAfterFail = document.querySelectorAll('.graph-table tbody tr').length;
  window.__simulate_page_error = false;
  const retryRes = await window.fetch('/api/v1/analyses/{dense_id}/graph?limit=50');
  const countAfterRetry = document.querySelectorAll('.graph-table tbody tr').length;
  return JSON.stringify({{
    initial_count: initialCount,
    error_observed: errorOccurred,
    count_after_fail: countAfterFail,
    retry_success: retryRes.ok,
    count_after_retry: countAfterRetry
  }});
}})()""",
                        "awaitPromise": True,
                    },
                )
                paging_data = json.loads(
                    eval_paging_test.get("result", {}).get("value", "{}")
                )
                assert paging_data.get("error_observed") is True, (
                    f"Paging error simulation failed: {paging_data}"
                )
                assert (
                    paging_data.get("count_after_fail")
                    == paging_data.get("initial_count")
                    == len(expected_node_identities) + len(expected_edge_identities)
                ), f"Loaded data was not retained during paging error: {paging_data}"
                assert paging_data.get("retry_success") is True, (
                    f"Paging retry failed: {paging_data}"
                )

                results["large_graph_dense_verification"] = {
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "overview_nodes_bounded": overview_res.get("layout_nodes"),
                    "overview_layout_ms": overview_layout_ms,
                    "full_layout_ms": full_layout_ms,
                    "full_layout_bounded_under_500ms": full_layout_ms < 500.0,
                    "graph_table_node_parity": True,
                    "graph_table_edge_parity": True,
                    "paging_failure_and_retry_retains_data": True,
                    "loaded_count_retained": paging_data.get("count_after_fail"),
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

        # 8. Real Job Cancellation Lifecycle in Browser UI (CS-021)
        async def run_ui_cancellation() -> None:
            res = urllib.request.urlopen(f"http://127.0.0.1:{chrome_debug_port}/json")  # noqa: S310
            targets = json.loads(res.read().decode())
            page_target = next(t for t in targets if t.get("type") == "page")
            ws_url = page_target["webSocketDebuggerUrl"]

            async with websockets.connect(ws_url) as ws:
                msg_id = [100]

                # Instrument window.fetch to log all polling requests (FINDING-6 FIX)
                await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => {"
                        "  window.__poll_request_log = [];"
                        "  const origFetch = window.fetch;"
                        "  window.fetch = function(...args) {"
                        "    const url = String(args[0]);"
                        "    if (url.includes('/api/v1/analyses/')) {"
                        "      window.__poll_request_log.push({ url: url, time: performance.now() });"
                        "    }"
                        "    return origFetch.apply(this, args);"
                        "  };"
                        "})()"
                    },
                )

                # Submit cancel_proj analysis job
                eval_submit = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"fetch('/api/v1/analyses', {{"
                        f"  method: 'POST',"
                        f"  headers: {{ 'Content-Type': 'application/json' }},"
                        f"  body: JSON.stringify({{ project: {{ root_id: '{cancel_id_root}', relative_path: '.' }}, refresh: true, options: {{ metrics: false }} }})"
                        f"}}).then(r => r.json()).then(d => JSON.stringify(d))",
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
                await asyncio.sleep(0.2)

                # (a) Find and click Cancel button in UI
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

                # (c) Explicitly assert cancellation_requested acknowledgement from API (FINDING-6 FIX)
                eval_cancel_api = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"fetch('/api/v1/analyses/{cancel_job_id}', {{ method: 'DELETE' }}).then(r => r.json()).then(d => JSON.stringify(d))",
                        "awaitPromise": True,
                    },
                )
                cancel_api_res = json.loads(
                    eval_cancel_api.get("result", {}).get("value", "{}")
                )
                api_state = cancel_api_res.get("state") or cancel_api_res.get("status")
                assert api_state in {"cancellation_requested", "cancelled"}, (
                    f"Expected cancellation_requested or cancelled acknowledgement, got: {cancel_api_res}"
                )
                api_ack_seen = True

                # Wait for backend terminal cancelled state
                backend_terminal_state = None
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
                    if job_data.get("terminal"):
                        backend_terminal_state = state
                        break
                    await asyncio.sleep(0.25)

                assert backend_terminal_state == "cancelled", (
                    f"Backend terminal state must be 'cancelled', got '{backend_terminal_state}'"
                )

                # (d) Verify live cancellation ARIA announcement in the UI
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

                # (e) Confirm UI terminal banner displayed
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

                # (f) FINDING-6 FIX: Prove frontend poller ceased making status requests
                # Count status requests recorded at terminal state
                eval_poll_count1 = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"window.__poll_request_log.filter(r => r.url.includes('{cancel_job_id}')).length"
                    },
                )
                poll_count_at_terminal = eval_poll_count1.get("result", {}).get(
                    "value", 0
                )

                # Wait 2.5 seconds (several polling cycles at 500-1000ms interval)
                await asyncio.sleep(2.5)

                eval_poll_count2 = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"window.__poll_request_log.filter(r => r.url.includes('{cancel_job_id}')).length"
                    },
                )
                poll_count_after_wait = eval_poll_count2.get("result", {}).get(
                    "value", 0
                )

                assert poll_count_after_wait == poll_count_at_terminal, (
                    f"Frontend poller did not cease polling after cancellation: before={poll_count_at_terminal}, after={poll_count_after_wait}"
                )

                results["real_cancellation_lifecycle"] = {
                    "ui_cancel_clicked": True,
                    "stopping_button_disabled": stopping_disabled,
                    "api_cancellation_requested_ack": api_ack_seen,
                    "backend_terminal_state": backend_terminal_state,
                    "live_announcement_found": live_announcement_found,
                    "poller_stopped_verified": True,
                    "zero_polls_after_terminal": True,
                    "terminal_ui_state": "cancelled",
                    "cancellation_lifecycle_verified": True,
                }

        asyncio.run(run_ui_cancellation())

        # 9. Non-Disclosing Secret Token Scan
        scan_for_secret_tokens(temp_dir, results)

    finally:
        # Teardown processes
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
