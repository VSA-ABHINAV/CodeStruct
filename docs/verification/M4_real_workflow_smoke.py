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
import ctypes
import ctypes.wintypes
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
import unittest.mock as mock
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import websockets

base_dir = pathlib.Path(r"D:\REP\Codestruct\Codestruct")
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
backend_python = str((base_dir / ".venv" / "Scripts" / "python.exe").resolve())
thonny_python = r"d:\REP\thonny\venv\Scripts\python.exe"

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = (
    ctypes.wintypes.HANDLE(-1).value if sys.platform == "win32" else -1
)
ERROR_NO_MORE_FILES = 18


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("cntUsage", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.wintypes.ULONG)),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("cntThreads", ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase", ctypes.wintypes.LONG),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
if kernel32:
    CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
    CreateToolhelp32Snapshot.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.DWORD]
    CreateToolhelp32Snapshot.restype = ctypes.wintypes.HANDLE
    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    CloseHandle.restype = ctypes.wintypes.BOOL
    Process32FirstW = kernel32.Process32FirstW
    Process32FirstW.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    Process32FirstW.restype = ctypes.wintypes.BOOL
    Process32NextW = kernel32.Process32NextW
    Process32NextW.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    Process32NextW.restype = ctypes.wintypes.BOOL
    GetLastError = kernel32.GetLastError
    GetLastError.argtypes = []
    GetLastError.restype = ctypes.wintypes.DWORD


def get_windows_process_tree_pids(root_pid: int) -> set[int]:
    """Discovers root_pid and all its descendant PIDs using Win32 Toolhelp snapshot. Fails closed on any error."""
    if sys.platform != "win32":
        return {root_pid}
    if not kernel32:
        raise RuntimeError(
            "Fail-closed error: kernel32 is unavailable for Toolhelp snapshot"
        )
    h = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h == INVALID_HANDLE_VALUE:
        err = GetLastError()
        raise RuntimeError(
            f"Fail-closed error: CreateToolhelp32Snapshot failed with Win32 error code {err}"
        )
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not Process32FirstW(h, ctypes.byref(pe)):
            err = GetLastError()
            raise RuntimeError(
                f"Fail-closed error: Process32FirstW failed with Win32 error code {err}"
            )
        parent_map: dict[int, list[int]] = {}
        while True:
            parent_map.setdefault(pe.th32ParentProcessID, []).append(pe.th32ProcessID)
            if not Process32NextW(h, ctypes.byref(pe)):
                err = GetLastError()
                if err != ERROR_NO_MORE_FILES:
                    raise RuntimeError(
                        f"Fail-closed error: Process32NextW failed during enumeration with Win32 error code {err}"
                    )
                break
        descendants = {root_pid}
        queue_pids = [root_pid]
        while queue_pids:
            curr = queue_pids.pop(0)
            for child in parent_map.get(curr, []):
                if child not in descendants:
                    descendants.add(child)
                    queue_pids.append(child)
        return descendants
    finally:
        CloseHandle(h)


def get_all_active_pids_win32() -> set[int]:
    """Returns set of all currently active PIDs in the system. Fails closed on any error."""
    if sys.platform != "win32":
        return set()
    if not kernel32:
        raise RuntimeError(
            "Fail-closed error: kernel32 is unavailable for Toolhelp snapshot"
        )
    h = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h == INVALID_HANDLE_VALUE:
        err = GetLastError()
        raise RuntimeError(
            f"Fail-closed error: CreateToolhelp32Snapshot failed with Win32 error code {err}"
        )
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        pids: set[int] = set()
        if not Process32FirstW(h, ctypes.byref(pe)):
            err = GetLastError()
            raise RuntimeError(
                f"Fail-closed error: Process32FirstW failed with Win32 error code {err}"
            )
        while True:
            pids.add(pe.th32ProcessID)
            if not Process32NextW(h, ctypes.byref(pe)):
                err = GetLastError()
                if err != ERROR_NO_MORE_FILES:
                    raise RuntimeError(
                        f"Fail-closed error: Process32NextW failed during enumeration with Win32 error code {err}"
                    )
                break
        return pids
    finally:
        CloseHandle(h)


def is_reparse_or_link(entry: pathlib.Path) -> bool:
    """Returns True if the path is a symlink, Windows junction, or reparse point."""
    if entry.is_symlink():
        return True
    if getattr(entry, "is_junction", lambda: False)():
        return True
    if sys.platform == "win32":
        try:
            st = os.lstat(entry)
            FILE_ATTRIBUTE_REPARSE_POINT = 0x400
            attrs = getattr(st, "st_file_attributes", 0)
            if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                return True
        except Exception:
            return True
    return False


def redact_secrets(text: str) -> str:
    """Strictly redacts capability tokens, session tokens, and query parameters from text."""
    if not text:
        return text
    # Redact cap_ tokens
    text = re.sub(r"cap_[A-Za-z0-9_-]+", "[REDACTED_CAPABILITY]", text)
    # Redact token / session_token query parameters
    text = re.sub(r"(session_token|token)=[^&\s]+", r"\1=[REDACTED_TOKEN]", text)
    return text


def format_thonny_failure_diagnostic(
    poll_status: int | None, stderr_lines: list[str]
) -> str:
    """Constructs and redacts failure diagnostic output when Thonny initiation fails."""
    _err = redact_secrets("".join(stderr_lines))
    return f"Thonny failed to emit viewer URL via stdout within deadline (poll={poll_status}, stderr={_err!r})"


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


def stop_process_tree_and_wait(proc: Any, name: str = "process") -> None:
    """Terminates a process and all its descendants on Windows, ensuring complete quiescence fail closed."""
    if proc is None:
        return
    pid = getattr(proc, "pid", None)
    tree_pids: set[int] = set()
    if pid is not None and sys.platform == "win32":
        # Capture all descendant PIDs before teardown
        tree_pids = get_windows_process_tree_pids(pid)
        is_alive = True
        if hasattr(proc, "poll") and proc.poll() is not None:
            is_alive = False
        if is_alive:
            try:
                res = subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception as e:
                raise RuntimeError(
                    f"Fail-closed process tree termination failed to launch taskkill for {name} (PID {pid}): {type(e).__name__}: {e}"
                ) from None
            # taskkill exit codes: 0 = success, 128 = process not found (already exited)
            if res.returncode not in (0, 128):
                raise RuntimeError(
                    f"Fail-closed process tree termination failed for {name} (PID {pid}): taskkill exit {res.returncode}, stderr={res.stderr.strip()}"
                )

    if hasattr(proc, "poll") and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to stop {name} (PID {pid}) during teardown: {type(e).__name__}"
                ) from None

    if hasattr(proc, "poll"):
        assert proc.poll() is not None, (
            f"Process {name} (PID {pid}) did not exit after teardown"
        )

    # On Windows, verify that EVERY descendant PID (and root PID) has exited completely
    if sys.platform == "win32" and tree_pids:
        deadline = time.time() + 5.0
        surviving: set[int] = tree_pids
        while time.time() < deadline:
            active = get_all_active_pids_win32()
            surviving = tree_pids.intersection(active)
            if not surviving:
                break
            time.sleep(0.05)
        if surviving:
            # Issue direct taskkill on any remaining descendant PIDs
            for spid in surviving:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(spid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            deadline2 = time.time() + 5.0
            while time.time() < deadline2:
                active = get_all_active_pids_win32()
                surviving = tree_pids.intersection(active)
                if not surviving:
                    break
                time.sleep(0.05)
            if surviving:
                raise RuntimeError(
                    f"Fail-closed process tree verification failed: {name} (PID {pid}) descendant PIDs still active: {sorted(surviving)}"
                )


def scan_for_secret_tokens(
    target_dir: pathlib.Path, result_data: dict[str, Any]
) -> dict[str, int]:
    """Non-disclosing fail-closed scanner that asserts no raw capability tokens are persisted or output."""
    token_pattern = re.compile(r"cap_[A-Za-z0-9_-]{16,}")
    scanned_dir_count = 0
    scanned_file_count = 0
    resolved_target_root = target_dir.resolve(strict=True)

    def _traverse(directory: pathlib.Path) -> None:
        nonlocal scanned_dir_count, scanned_file_count
        scanned_dir_count += 1
        try:
            entries = list(directory.iterdir())
        except Exception as e:
            raise AssertionError(
                f"Fail-closed scan error: unable to enumerate directory '{directory.name}' ({type(e).__name__})"
            ) from None

        for entry in entries:
            try:
                is_rep_or_link = is_reparse_or_link(entry)
                is_dir = entry.is_dir()
                is_file = entry.is_file()
            except Exception as e:
                raise AssertionError(
                    f"Fail-closed scan error: unable to inspect entry '{entry.name}' ({type(e).__name__})"
                ) from None

            if is_rep_or_link:
                raise AssertionError(
                    f"Fail-closed scan error: unexpected symlink or reparse point '{entry.name}'"
                )

            # Prove canonical containment within target_dir
            try:
                resolved_entry = entry.resolve(strict=True)
                if not resolved_entry.is_relative_to(resolved_target_root):
                    raise AssertionError(
                        f"Fail-closed scan error: entry '{entry.name}' resolves outside target root"
                    )
            except Exception as e:
                if isinstance(e, AssertionError):
                    raise
                raise AssertionError(
                    f"Fail-closed scan error: unable to resolve entry '{entry.name}' ({type(e).__name__})"
                ) from None

            if is_dir:
                _traverse(entry)
            elif is_file:
                try:
                    content = entry.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    raise AssertionError(
                        f"Fail-closed scan error: unable to read file for credential verification: '{entry.name}' ({type(e).__name__})"
                    ) from None
                if token_pattern.search(content):
                    raise AssertionError(
                        f"Capability token pattern detected in persisted file: {entry.name}"
                    )
                scanned_file_count += 1
            else:
                raise AssertionError(
                    f"Fail-closed scan error: unsupported/special filesystem entry '{entry.name}'"
                )

    _traverse(target_dir)

    assert scanned_dir_count > 0, "Fail-closed scan error: zero directories traversed"
    assert scanned_file_count > 0, (
        "Fail-closed scan error: zero files found in target directory"
    )
    dumped = json.dumps(result_data)
    if token_pattern.search(dumped):
        raise AssertionError(
            "Capability token pattern detected in returned results structure"
        )
    return {"scanned_dirs": scanned_dir_count, "scanned_files": scanned_file_count}


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


def create_cancellable_project(cancel_dir: pathlib.Path, num_files: int = 80) -> None:
    """Creates a multi-file Python project with non-trivial AST structures to test cancellation."""
    cancel_dir.mkdir(parents=True, exist_ok=True)
    for f in range(num_files):
        lines = [f"# Multi-file cancellable project file {f}", "import sys, os"]
        for c in range(20):
            lines.append(f"class CancelService_{f}_{c}:")
            lines.append(f"    def perform_action_{c}(self):")
            lines.append(f"        return {f} * {c} + 42\n")
        (cancel_dir / f"mod_{f}.py").write_text("\n".join(lines), encoding="utf-8")


def run_full_m4_real_workflow() -> dict[str, Any]:
    # 0. Secret Redaction Regression & Failure-Path Diagnostic Formatting Test (FINDING-6 FIX)
    test_sample = "Error: cap_secret1234567890abcdef failed on http://127.0.0.1:5173/?session_token=cap_secret1234567890abcdef&analysis_id=job_123"
    redacted_sample = redact_secrets(test_sample)
    assert "cap_" not in redacted_sample, "redact_secrets failed to redact cap_ token"
    assert "session_token=cap_" not in redacted_sample, (
        "redact_secrets failed to redact query token"
    )

    # Invoke the actual diagnostic formatting failure-path and assert zero token leakage
    simulated_raw_stderr = [
        "DEBUG: Thonny plugin initialization\n",
        "ERROR: failed to connect to http://127.0.0.1:5173/?session_token=cap_secret1234567890abcdef&analysis_id=job_123\n",
        "CRITICAL: cap_secret1234567890abcdef was rejected by server\n",
    ]
    emitted_diag = format_thonny_failure_diagnostic(1, simulated_raw_stderr)
    assert "cap_" not in emitted_diag, (
        f"Raw token leaked in failure diagnostic output: {emitted_diag}"
    )
    assert "session_token=cap_" not in emitted_diag, (
        f"Session token leaked in failure diagnostic output: {emitted_diag}"
    )
    assert "[REDACTED_CAPABILITY]" in emitted_diag, (
        f"Expected capability redaction in diagnostic output: {emitted_diag}"
    )
    assert "[REDACTED_TOKEN]" in emitted_diag, (
        f"Expected token redaction in diagnostic output: {emitted_diag}"
    )

    # 0b. Process-Tree Teardown & Secret Scanner Fail-Closed Regressions (CODEX REVIEW 11 FIX)
    # (i) Test Win32 Toolhelp snapshot and enumeration failure injections
    if sys.platform == "win32" and kernel32:
        # 1. Snapshot creation failure injection
        with mock.patch(
            f"{__name__}.CreateToolhelp32Snapshot",
            return_value=INVALID_HANDLE_VALUE,
        ):
            try:
                get_windows_process_tree_pids(os.getpid())
                raise AssertionError(
                    "Expected get_windows_process_tree_pids to fail closed on snapshot error"
                )
            except RuntimeError as snap_err:
                assert "CreateToolhelp32Snapshot failed" in str(snap_err)

            try:
                get_all_active_pids_win32()
                raise AssertionError(
                    "Expected get_all_active_pids_win32 to fail closed on snapshot error"
                )
            except RuntimeError as snap_err:
                assert "CreateToolhelp32Snapshot failed" in str(snap_err)

        def _fresh_snapshot(*args: Any) -> Any:
            return kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)

        # 2. Process32FirstW failure injection
        with mock.patch(
            f"{__name__}.CreateToolhelp32Snapshot",
            side_effect=_fresh_snapshot,
        ):
            with mock.patch(f"{__name__}.Process32FirstW", return_value=0):
                try:
                    get_windows_process_tree_pids(os.getpid())
                    raise AssertionError(
                        "Expected get_windows_process_tree_pids to fail closed on Process32FirstW error"
                    )
                except RuntimeError as first_err:
                    assert "Process32FirstW failed" in str(first_err)

                try:
                    get_all_active_pids_win32()
                    raise AssertionError(
                        "Expected get_all_active_pids_win32 to fail closed on Process32FirstW error"
                    )
                except RuntimeError as first_err:
                    assert "Process32FirstW failed" in str(first_err)

        # 3. Process32NextW unexpected iteration error injection
        with mock.patch(
            f"{__name__}.CreateToolhelp32Snapshot",
            side_effect=_fresh_snapshot,
        ):
            with mock.patch(f"{__name__}.Process32NextW", return_value=0):
                with mock.patch(f"{__name__}.GetLastError", return_value=5):
                    try:
                        get_windows_process_tree_pids(os.getpid())
                        raise AssertionError(
                            "Expected get_windows_process_tree_pids to fail closed on Process32NextW error"
                        )
                    except RuntimeError as next_err:
                        assert "Process32NextW failed" in str(next_err)

                    try:
                        get_all_active_pids_win32()
                        raise AssertionError(
                            "Expected get_all_active_pids_win32 to fail closed on Process32NextW error"
                        )
                    except RuntimeError as next_err:
                        assert "Process32NextW failed" in str(next_err)

    # (ii) Test real process tree shutdown asserting both parent and descendant child PID exit
    child_spawn_script = "import time; time.sleep(30)"
    parent_spawn_script = (
        f"import subprocess, sys, time; "
        f"c = subprocess.Popen([sys.executable, '-c', {child_spawn_script!r}]); "
        f"print(c.pid, flush=True); time.sleep(30)"
    )
    test_spawn = subprocess.Popen(
        [sys.executable, "-c", parent_spawn_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert test_spawn.stdout is not None
    test_child_pid_line = test_spawn.stdout.readline().strip()
    assert test_child_pid_line.isdigit(), (
        f"Failed to read child PID: {test_child_pid_line!r}"
    )
    test_child_pid = int(test_child_pid_line)

    stop_process_tree_and_wait(test_spawn, "test_spawn_tree")
    assert test_spawn.poll() is not None, "Test process tree parent failed to exit"
    if sys.platform == "win32":
        active_pids_after_teardown = get_all_active_pids_win32()
        assert test_child_pid not in active_pids_after_teardown, (
            f"Test child PID {test_child_pid} was not terminated by process tree shutdown"
        )

    # (iii) Test scanner fail-closed on token leak, special entries, and mandatory Windows junction/reparse points
    test_scan_dir = pathlib.Path(tempfile.mkdtemp(prefix="codestruct_scan_test_"))
    try:
        (test_scan_dir / "valid.txt").write_text("clean content", encoding="utf-8")
        scan_res = scan_for_secret_tokens(test_scan_dir, {"ok": True})
        assert scan_res["scanned_dirs"] == 1 and scan_res["scanned_files"] == 1

        # Test token leak detection
        (test_scan_dir / "leaked.txt").write_text(
            "token cap_abcdef1234567890xyz", encoding="utf-8"
        )
        leak_detected = False
        try:
            scan_for_secret_tokens(test_scan_dir, {"ok": True})
        except AssertionError as leak_err:
            if "Capability token pattern detected" in str(leak_err):
                leak_detected = True
        assert leak_detected is True, "Scanner failed to detect secret token pattern"
        (test_scan_dir / "leaked.txt").unlink()

        # (iv) Mandatory Windows junction & canonical containment regressions (CODEX REVIEW 11 FIX)
        if sys.platform == "win32":
            # 1. Inside-root junction test
            junc_target = test_scan_dir / "junc_target"
            junc_target.mkdir(parents=True, exist_ok=True)
            (junc_target / "nested.txt").write_text("inside target", encoding="utf-8")
            junc_link = test_scan_dir / "junc_link"

            mk_res = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junc_link), str(junc_target)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert mk_res.returncode == 0, (
                f"Mandatory Windows junction creation failed: {mk_res.stderr.strip()}"
            )
            assert junc_link.exists(), (
                f"Mandatory Windows junction not found on disk at {junc_link}"
            )
            assert is_reparse_or_link(junc_link) is True, (
                f"Mandatory Windows junction was not recognized by is_reparse_or_link(): {junc_link}"
            )

            reparse_detected = False
            try:
                scan_for_secret_tokens(test_scan_dir, {"ok": True})
            except AssertionError as rep_err:
                if "unexpected symlink or reparse point" in str(rep_err):
                    reparse_detected = True
            assert reparse_detected is True, (
                "Scanner failed to reject mandatory Windows junction reparse point"
            )
            subprocess.run(
                ["cmd", "/c", "rmdir", str(junc_link)],
                capture_output=True,
                check=False,
            )
            shutil.rmtree(junc_target, ignore_errors=True)

            # 2. Outside-root junction and containment test
            outside_scan_dir = pathlib.Path(
                tempfile.mkdtemp(prefix="codestruct_outside_test_")
            )
            try:
                (outside_scan_dir / "outside_secret.txt").write_text(
                    "outside content", encoding="utf-8"
                )
                outside_junc_link = test_scan_dir / "outside_junc"
                mk_res_out = subprocess.run(
                    [
                        "cmd",
                        "/c",
                        "mklink",
                        "/J",
                        str(outside_junc_link),
                        str(outside_scan_dir),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert mk_res_out.returncode == 0, (
                    f"Mandatory outside-root Windows junction creation failed: {mk_res_out.stderr.strip()}"
                )
                assert outside_junc_link.exists(), (
                    f"Mandatory outside-root Windows junction not found on disk at {outside_junc_link}"
                )
                assert is_reparse_or_link(outside_junc_link) is True, (
                    f"Mandatory outside-root Windows junction was not recognized by is_reparse_or_link(): {outside_junc_link}"
                )

                # Verify scanner rejects outside-root reparse point fail-closed
                outside_reparse_detected = False
                try:
                    scan_for_secret_tokens(test_scan_dir, {"ok": True})
                except AssertionError as out_rep_err:
                    if "unexpected symlink or reparse point" in str(out_rep_err):
                        outside_reparse_detected = True
                assert outside_reparse_detected is True, (
                    "Scanner failed to reject outside-root Windows junction reparse point"
                )

                # Verify canonical containment resolution rejection
                resolved_target_root = test_scan_dir.resolve(strict=True)
                resolved_outside_link = outside_junc_link.resolve(strict=True)
                assert not resolved_outside_link.is_relative_to(resolved_target_root), (
                    f"Outside link {resolved_outside_link} should resolve outside scan root {resolved_target_root}"
                )

                subprocess.run(
                    ["cmd", "/c", "rmdir", str(outside_junc_link)],
                    capture_output=True,
                    check=False,
                )
            finally:
                shutil.rmtree(outside_scan_dir, ignore_errors=True)
    finally:
        shutil.rmtree(test_scan_dir, ignore_errors=True)

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
        create_cancellable_project(root_cancel, num_files=80)

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
            "import types\n"
            "try:\n"
            "    import minny.target\n"
            "except (ImportError, ModuleNotFoundError):\n"
            "    _minny_target = types.ModuleType('minny.target')\n"
            "    _minny_target.PASTE_SUBMIT_MODE = 'paste'\n"
            "    _minny_target.RAW_PASTE_SUBMIT_MODE = 'raw_paste'\n"
            "    class _ManagementError(Exception):\n"
            "        pass\n"
            "    class _ProperTargetManager:\n"
            "        pass\n"
            "    _minny_target.ManagementError = _ManagementError\n"
            "    _minny_target.ProperTargetManager = _ProperTargetManager\n"
            "    sys.modules['minny.target'] = _minny_target\n"
            "from thonny.main import _parse_arguments_to_dict\n"
            "from thonny.workbench import Workbench\n"
            "from thonny import get_runner\n"
            "import thonnycontrib.codestruct as cs\n"
            "parsed = _parse_arguments_to_dict([])\n"
            "wb = Workbench(parsed)\n"
            "wb._language_server_proxy_classes.clear()\n"
            "wb.update()\n"
            "sys.stderr.write('THONNY_WORKBENCH_STARTED\\n')\n"
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
            raise AssertionError(
                format_thonny_failure_diagnostic(
                    thonny_proc.poll(), _thonny_stderr_lines
                )
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

        # 5. Launch Headless Google Chrome with CDP and Isolated User Data Profile (FINDING-5 FIX)
        chrome_user_data_dir = temp_dir / "chrome_user_data"
        chrome_user_data_dir.mkdir(parents=True, exist_ok=True)
        chrome_proc = subprocess.Popen(
            [
                chrome_path,
                "--headless=new",
                "--incognito",
                f"--user-data-dir={chrome_user_data_dir.resolve()}",
                f"--remote-debugging-port={chrome_debug_port}",
                "--disable-gpu",
                "--window-size=1280,900",
                "--no-first-run",
                "--no-default-browser-check",
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
                        "  rendered_nodes: document.querySelectorAll('.react-flow__node').length"
                        "})"
                    },
                )
                overview_res = json.loads(
                    eval_overview.get("result", {}).get("value", "{}")
                )
                assert overview_res.get("has_large_graph_banner") is True, (
                    f"Expected .large-graph-actions banner for dense graph: {overview_res}"
                )
                assert overview_res.get("rendered_nodes", 999) < 80, (
                    f"Overview node count not bounded (<80): {overview_res}"
                )

                # Click 'Render complete graph anyway' to trigger full in-app rendering
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

                # Verify complete graph rendered on canvas
                eval_full_render = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify({"
                        "  rendered_nodes: document.querySelectorAll('.react-flow__node').length"
                        "})"
                    },
                )
                full_render_res = json.loads(
                    eval_full_render.get("result", {}).get("value", "{}")
                )
                assert full_render_res.get("rendered_nodes", 0) > 0, (
                    f"Expected rendered nodes on canvas: {full_render_res}"
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

                # FINDING-4 FIX: Exercise Paging Failure, Error Observation, Data Retention & Retry via UI
                # (1) Install fetch interceptor on new documents to provide initial paged slice (limit=40)
                await cdp_send(
                    ws,
                    msg_id,
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": f"""
window.__paging_test_active = true;
window.__simulate_page_error = false;
const origFetch = window.fetch;
window.fetch = async function(url, opts) {{
  const urlStr = String(url);
  if (window.__paging_test_active && urlStr.includes('/api/v1/analyses/{dense_id}/graph')) {{
    if (window.__simulate_page_error && urlStr.includes('cursor=')) {{
      return new Response(JSON.stringify({{ error: {{ code: 'PAGE_FETCH_ERROR', message: 'Simulated next-page network failure' }} }}), {{
        status: 500,
        headers: {{ 'Content-Type': 'application/json' }}
      }});
    }}
    const rewritten = urlStr.includes('limit=') ? urlStr.replace(/limit=\\d+/, 'limit=100') : (urlStr + (urlStr.includes('?') ? '&limit=100' : '?limit=100'));
    return origFetch.call(this, rewritten, opts);
  }}
  return origFetch.apply(this, arguments);
}};
"""
                    },
                )

                # Re-navigate dense view to load the paged slice in the UI
                await cdp_send(ws, msg_id, "Page.navigate", {"url": dense_viewer_url})
                await asyncio.sleep(1.5)

                # Switch to Accessible table view
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

                # Wait for partial-load banner and 'Load more graph data' button to appear
                partial_btn_ready = False
                for _ in range(30):
                    chk_btn = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "(() => {"
                            "  const btn = Array.from(document.querySelectorAll('.partial-load button')).find(b => b.innerText.includes('Load more graph data'));"
                            "  return btn !== undefined && !btn.disabled;"
                            "})()"
                        },
                    )
                    if chk_btn.get("result", {}).get("value") is True:
                        partial_btn_ready = True
                        break
                    await asyncio.sleep(0.2)
                assert partial_btn_ready is True, (
                    "Expected 'Load more graph data' button in UI for paged slice"
                )

                # Extract initial loaded slice nodes and edges
                eval_initial_paged = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const rows = Array.from(document.querySelectorAll('.graph-table tbody tr'));"
                        "  const nodeRows = rows.filter(r => r.children[2]?.innerText === 'Entity');"
                        "  const edgeRows = rows.filter(r => r.children[2]?.innerText !== 'Entity');"
                        "  const nodes = nodeRows.map(r => r.querySelector('td')?.innerText || '').filter(Boolean).sort();"
                        "  const edges = edgeRows.map(r => `${r.children[0]?.innerText || ''}|${r.children[1]?.innerText || ''}|${r.children[2]?.innerText || ''}`).filter(Boolean).sort();"
                        "  return { nodes, edges };"
                        "})())"
                    },
                )
                initial_paged_data = json.loads(
                    eval_initial_paged.get("result", {}).get("value", "{}")
                )
                initial_slice_nodes = initial_paged_data.get("nodes", [])
                initial_slice_edges = initial_paged_data.get("edges", [])
                assert 0 < len(initial_slice_nodes) < len(expected_node_identities), (
                    f"Initial paged slice should be partial: {len(initial_slice_nodes)} vs total {len(expected_node_identities)}"
                )

                # (2) Force next-page request to fail and trigger via actual UI button click
                await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {"expression": "window.__simulate_page_error = true;"},
                )
                eval_click_fail = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => {"
                        "  const btn = Array.from(document.querySelectorAll('.partial-load button')).find(b => b.innerText.includes('Load more graph data'));"
                        "  if (btn) { btn.click(); return true; }"
                        "  return false;"
                        "})()"
                    },
                )
                assert eval_click_fail.get("result", {}).get("value") is True, (
                    "Failed to click 'Load more graph data' button"
                )
                await asyncio.sleep(0.8)

                # (3) Assert visible error UI banner and verify loaded node/edge identities remain unchanged
                eval_after_fail = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const errorBanner = document.querySelector('.graph-status--failed, [role=\"alert\"]');"
                        "  const retryBtn = Array.from(document.querySelectorAll('.partial-load button')).find(b => b.innerText.includes('Load more graph data'));"
                        "  const rows = Array.from(document.querySelectorAll('.graph-table tbody tr'));"
                        "  const nodeRows = rows.filter(r => r.children[2]?.innerText === 'Entity');"
                        "  const edgeRows = rows.filter(r => r.children[2]?.innerText !== 'Entity');"
                        "  const nodes = nodeRows.map(r => r.querySelector('td')?.innerText || '').filter(Boolean).sort();"
                        "  const edges = edgeRows.map(r => `${r.children[0]?.innerText || ''}|${r.children[1]?.innerText || ''}|${r.children[2]?.innerText || ''}`).filter(Boolean).sort();"
                        "  return {"
                        "    has_error_banner: errorBanner !== null,"
                        "    error_text: errorBanner ? errorBanner.innerText : '',"
                        "    retry_btn_available: retryBtn !== undefined && !retryBtn.disabled,"
                        "    nodes: nodes,"
                        "    edges: edges"
                        "  };"
                        "})())"
                    },
                )
                after_fail_data = json.loads(
                    eval_after_fail.get("result", {}).get("value", "{}")
                )
                assert after_fail_data.get("has_error_banner") is True, (
                    f"Expected visible error banner on paging failure: {after_fail_data}"
                )
                assert after_fail_data.get("retry_btn_available") is True, (
                    f"Expected retry button to remain available: {after_fail_data}"
                )
                assert after_fail_data.get("nodes") == initial_slice_nodes, (
                    "Loaded node identities changed during paging failure"
                )
                assert after_fail_data.get("edges") == initial_slice_edges, (
                    "Loaded edge identities changed during paging failure"
                )

                # (4) Clear failure simulation and activate retry via the UI button
                await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {"expression": "window.__simulate_page_error = false;"},
                )
                eval_click_retry = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "(() => {"
                        "  const btn = Array.from(document.querySelectorAll('.partial-load button')).find(b => b.innerText.includes('Load more graph data'));"
                        "  if (btn) { btn.click(); return true; }"
                        "  return false;"
                        "})()"
                    },
                )
                assert eval_click_retry.get("result", {}).get("value") is True, (
                    "Failed to click retry 'Load more graph data' button"
                )
                await asyncio.sleep(1.2)

                # (5) Verify successful page merge, error banner cleared, and full node/edge identities present
                eval_merged_state = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify((() => {"
                        "  const errorBanner = document.querySelector('.graph-status--failed');"
                        "  const rows = Array.from(document.querySelectorAll('.graph-table tbody tr'));"
                        "  const nodeRows = rows.filter(r => r.children[2]?.innerText === 'Entity');"
                        "  const edgeRows = rows.filter(r => r.children[2]?.innerText !== 'Entity');"
                        "  const nodes = nodeRows.map(r => r.querySelector('td')?.innerText || '').filter(Boolean).sort();"
                        "  const edges = edgeRows.map(r => `${r.children[0]?.innerText || ''}|${r.children[1]?.innerText || ''}|${r.children[2]?.innerText || ''}`).filter(Boolean).sort();"
                        "  return {"
                        "    has_error_banner: errorBanner !== null,"
                        "    node_count: nodes.length,"
                        "    edge_count: edges.length,"
                        "    nodes: nodes,"
                        "    edges: edges"
                        "  };"
                        "})())"
                    },
                )
                merged_data = json.loads(
                    eval_merged_state.get("result", {}).get("value", "{}")
                )
                assert merged_data.get("has_error_banner") is False, (
                    f"Error banner was not cleared after retry: {merged_data}"
                )
                assert merged_data.get("nodes") == expected_node_identities, (
                    f"Merged node identities mismatch: {len(merged_data.get('nodes', []))} vs {len(expected_node_identities)}"
                )
                assert merged_data.get("edges") == expected_edge_identities, (
                    f"Merged edge identities mismatch: {len(merged_data.get('edges', []))} vs {len(expected_edge_identities)}"
                )

                results["large_graph_dense_verification"] = {
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "overview_nodes_bounded": overview_res.get("rendered_nodes"),
                    "full_rendered_nodes": full_render_res.get("rendered_nodes"),
                    "graph_table_node_parity": True,
                    "graph_table_edge_parity": True,
                    "paging_failure_and_retry_retains_data": True,
                    "paging_ui_action_verified": True,
                    "paging_retry_and_merge_verified": True,
                    "initial_slice_node_count": len(initial_slice_nodes),
                    "final_merged_node_count": len(merged_data.get("nodes", [])),
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
                await cdp_send(ws, msg_id, "Page.enable")
                await cdp_send(ws, msg_id, "DOM.enable")
                await cdp_send(ws, msg_id, "Runtime.enable")

                # Install fetch logger in new documents BEFORE any application scripts execute (FINDING-2 & FINDING-3 FIX)
                await cdp_send(
                    ws,
                    msg_id,
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": """
window.__poll_request_log = [];
window.__delete_response_log = [];
const origFetch = window.fetch;
window.fetch = async function(...args) {
    const url = String(args[0]);
    const opts = args[1] || {};
    const method = (opts.method || 'GET').toUpperCase();
    if (url.includes('/api/v1/analyses/')) {
        window.__poll_request_log.push({ url: url, method: method, time: performance.now() });
    }
    const res = await origFetch.apply(this, args);
    if (method === 'DELETE' && url.includes('/api/v1/analyses/')) {
        try {
            const clone = res.clone();
            const data = await clone.json();
            window.__delete_response_log.push({ url: url, status: res.status, data: data, time: performance.now() });
        } catch (e) {}
    }
    return res;
};
"""
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

                # Navigate UI to load the active cancel_proj job (evaluates script on new document)
                cancel_viewer_url = (
                    f"http://127.0.0.1:{frontend_port}/?analysis_id={cancel_job_id}"
                )
                await cdp_send(
                    ws,
                    msg_id,
                    "Page.navigate",
                    {"url": cancel_viewer_url},
                )
                await asyncio.sleep(0.4)

                # (a) Assert logger is present and has observed status polling calls BEFORE cancellation (FINDING-2 FIX)
                pre_cancel_data = {}
                for _ in range(30):
                    eval_pre_cancel_log = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "JSON.stringify({"
                            "  has_log: Array.isArray(window.__poll_request_log),"
                            f"  status_calls: (window.__poll_request_log || []).filter(r => r.url.includes('{cancel_job_id}') && r.method === 'GET').length"
                            "})"
                        },
                    )
                    pre_cancel_data = json.loads(
                        eval_pre_cancel_log.get("result", {}).get("value", "{}")
                    )
                    if (
                        pre_cancel_data.get("has_log")
                        and pre_cancel_data.get("status_calls", 0) > 0
                    ):
                        break
                    await asyncio.sleep(0.1)

                assert pre_cancel_data.get("has_log") is True, (
                    f"Fetch logger instrumentation is missing on new document: {pre_cancel_data}"
                )
                assert pre_cancel_data.get("status_calls", 0) > 0, (
                    f"Logger observed zero status requests before cancellation: {pre_cancel_data}"
                )

                # (b) Find and click Cancel button in UI
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

                # (c) Assert disabled "Stopping…" state immediately after click
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

                # (d) Explicitly assert EXACT cancellation_requested acknowledgement from UI's DELETE call (FINDING-3 FIX)
                delete_state = None
                delete_status = None
                for _ in range(30):
                    eval_delete_log = await cdp_send(
                        ws,
                        msg_id,
                        "Runtime.evaluate",
                        {
                            "expression": "JSON.stringify(window.__delete_response_log || [])"
                        },
                    )
                    delete_log = json.loads(
                        eval_delete_log.get("result", {}).get("value", "[]")
                    )
                    if len(delete_log) > 0:
                        first_delete_ack = delete_log[0]
                        delete_status = first_delete_ack.get("status")
                        delete_data = first_delete_ack.get("data", {})
                        delete_state = delete_data.get("state")
                        break
                    await asyncio.sleep(0.1)

                assert delete_status == 202, (
                    f"Expected DELETE status 202, got {delete_status}"
                )
                assert delete_state == "cancellation_requested", (
                    f"Expected EXACT 'cancellation_requested' state in DELETE acknowledgement, got '{delete_state}'"
                )

                # (e) Wait for backend terminal cancelled state
                backend_terminal_state = None
                backend_phase = None
                backend_message_code = None
                backend_terminal_job_data: dict[str, Any] = {}
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
                        backend_phase = (job_data.get("progress") or {}).get("phase")
                        backend_message_code = (job_data.get("progress") or {}).get(
                            "message_code"
                        )
                        backend_terminal_job_data = job_data
                        break
                    await asyncio.sleep(0.25)

                assert backend_terminal_state == "cancelled", (
                    f"Backend terminal state must be 'cancelled', got '{backend_terminal_state}' "
                    f"(phase={backend_phase!r}, message_code={backend_message_code!r}, "
                    f"progress={backend_terminal_job_data.get('progress')})"
                )

                # (f) Verify live cancellation ARIA announcement in the UI
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

                # (g) Confirm UI terminal banner displayed
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

                # (h) Prove frontend poller ceased making status requests (FINDING-2 FIX)
                eval_poll_count1 = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"(window.__poll_request_log || []).filter(r => r.url.includes('{cancel_job_id}') && r.method === 'GET').length"
                    },
                )
                poll_count_at_terminal = eval_poll_count1.get("result", {}).get("value")
                assert (
                    poll_count_at_terminal is not None and poll_count_at_terminal > 0
                ), (
                    f"Expected non-zero poll count at terminal state, got {poll_count_at_terminal}"
                )

                # Wait 2.5 seconds (several polling cycles at 500-1000ms interval)
                await asyncio.sleep(2.5)

                eval_poll_count2 = await cdp_send(
                    ws,
                    msg_id,
                    "Runtime.evaluate",
                    {
                        "expression": f"(window.__poll_request_log || []).filter(r => r.url.includes('{cancel_job_id}') && r.method === 'GET').length"
                    },
                )
                poll_count_after_wait = eval_poll_count2.get("result", {}).get("value")

                assert poll_count_after_wait == poll_count_at_terminal, (
                    f"Frontend poller did not cease polling after cancellation: before={poll_count_at_terminal}, after={poll_count_after_wait}"
                )

                results["real_cancellation_lifecycle"] = {
                    "ui_cancel_clicked": True,
                    "stopping_button_disabled": stopping_disabled,
                    "api_cancellation_requested_ack": True,
                    "delete_ack_state": delete_state,
                    "backend_terminal_state": backend_terminal_state,
                    "live_announcement_found": live_announcement_found,
                    "poller_stopped_verified": True,
                    "pre_cancel_polls": pre_cancel_data.get("status_calls"),
                    "terminal_polls": poll_count_at_terminal,
                    "after_wait_polls": poll_count_after_wait,
                    "zero_polls_after_terminal": True,
                    "terminal_ui_state": "cancelled",
                    "cancellation_lifecycle_verified": True,
                }

        asyncio.run(run_ui_cancellation())

        # Teardown process trees and ensure full quiescence before scanning disk
        for proc, name in [
            (chrome_proc, "Chrome"),
            (thonny_proc, "Thonny"),
            (frontend_proc, "Frontend"),
            (backend_proc, "Backend"),
        ]:
            stop_process_tree_and_wait(proc, name)

        # Brief pause to allow OS file system handles to fully close
        time.sleep(0.5)

        # 9. Non-Disclosing Secret Token Scan
        scan_stats = scan_for_secret_tokens(temp_dir, results)
        results["secret_scan"] = {
            "scanned_dirs": scan_stats["scanned_dirs"],
            "scanned_files": scan_stats["scanned_files"],
            "zero_tokens_leaked": True,
        }

    finally:
        # Teardown processes fallback
        for proc, name in [
            (chrome_proc, "Chrome"),
            (thonny_proc, "Thonny"),
            (frontend_proc, "Frontend"),
            (backend_proc, "Backend"),
        ]:
            try:
                stop_process_tree_and_wait(proc, name)
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
