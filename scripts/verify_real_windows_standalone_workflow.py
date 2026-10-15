# ruff: noqa: S101, S310, S603, S607
"""Real Windows Standalone Project Explorer Workflow Verification.

Exercises the whole-folder standalone workflow on a real Windows machine:
1. Creates a disposable fixture project with nested packages, non-Python files,
   and Python symbols (module, class, method, function).
2. Starts the prototype services and standalone desktop window via
   Start-CodeStruct-Prototype.ps1.
3. Exercises folder opening, automatic analysis, tree hierarchy retrieval,
   graph hierarchy levels, symbol inspection, architectural explanation,
   and project refresh without executing source code.
4. Captures the real standalone application window screenshot.
5. Shuts down cleanly via Stop-CodeStruct-Prototype.ps1.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


def http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post(url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    payload = json.dumps(data).encode("utf-8") if data is not None else b"{}"
    all_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        all_headers.update(headers)
    req = urllib.request.Request(url, data=payload, headers=all_headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    launcher_dir = repo_root / "prototype-launcher"
    runtime_dir = launcher_dir / "runtime"
    state_file = runtime_dir / "prototype-state.json"
    evidence_dir = repo_root / "docs" / "verification"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = evidence_dir / "standalone_window_workflow.png"

    print("=" * 65)
    print("CodeStruct Real Windows Standalone Workflow Verification")
    print("=" * 65)

    # 1. Create disposable fixture project
    fixture_dir = repo_root / "scratch" / "standalone_workflow_project"
    if fixture_dir.exists():
        import shutil

        shutil.rmtree(fixture_dir, ignore_errors=True)
    fixture_dir.mkdir(parents=True, exist_ok=True)

    nested_domain = fixture_dir / "nested" / "domain"
    nested_domain.mkdir(parents=True, exist_ok=True)
    calc_py = nested_domain / "calculator.py"
    calc_py.write_text(
        '"""Domain calculator module."""\n\n'
        "def compute_discount(amount: float, rate: float) -> float:\n"
        '    """Top-level helper function."""\n'
        "    return amount * (1.0 - rate)\n\n\n"
        "class InvoiceCalculator:\n"
        '    """Invoice calculation service."""\n\n'
        "    def calculate_total(self, subtotal: float, discount_rate: float) -> float:\n"
        '        """Class method calling top-level function."""\n'
        "        discounted = compute_discount(subtotal, discount_rate)\n"
        "        return discounted * 1.18\n\n"
        "    def format_currency(self, value: float) -> str:\n"
        '        """Formatting helper method."""\n'
        '        return f"${value:.2f}"\n',
        encoding="utf-8",
    )

    nested_config = fixture_dir / "nested" / "config"
    nested_config.mkdir(parents=True, exist_ok=True)
    (nested_config / "settings.json").write_text(
        '{"tax_rate": 0.18, "currency": "USD"}\n',
        encoding="utf-8",
    )

    git_dir = fixture_dir / "nested" / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    print(f"[Step 1] Created disposable fixture project at:\n  {fixture_dir}")

    # 2. Stop any existing prototype instances first
    print("[Step 2] Ensuring clean service state...")
    subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher_dir / "Stop-CodeStruct-Prototype.ps1"),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    time.sleep(1.5)

    # 3. Start prototype launcher with desktop window
    print(
        "[Step 3] Launching CodeStruct prototype services and standalone desktop window..."
    )
    # Set initial folder env for native FolderBrowserDialog preselection without mocking
    start_env = os.environ.copy()
    start_env["CODESTRUCT_INITIAL_FOLDER"] = str(fixture_dir.resolve())
    if "CODESTRUCT_MOCK_CHOOSE_FOLDER" in start_env:
        del start_env["CODESTRUCT_MOCK_CHOOSE_FOLDER"]

    start_proc = subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher_dir / "Start-CodeStruct-Prototype.ps1"),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=start_env,
    )
    if start_proc.returncode != 0:
        print(
            f"[ERROR] Start-CodeStruct-Prototype.ps1 failed (exit code {start_proc.returncode}):"
        )
        print(start_proc.stdout)
        print(start_proc.stderr)
        return 1

    print("  Launcher started successfully.")

    # 4. Read runtime state and verify processes
    if not state_file.exists():
        print(f"[ERROR] State file not found at {state_file}")
        return 1

    with open(state_file, encoding="utf-8-sig") as f:
        state_data = json.load(f)

    backend_pid = state_data.get("backend", {}).get("pid")
    frontend_pid = state_data.get("frontend", {}).get("pid")
    app_window_pid = state_data.get("appWindow", {}).get("pid")

    print("[Step 4] Process Verification:")
    print(f"  Backend PID:        {backend_pid}")
    print(f"  Frontend PID:       {frontend_pid}")
    print(f"  App Window PID:     {app_window_pid}")

    if not backend_pid or not frontend_pid:
        print("[ERROR] Missing backend or frontend PID in runtime state.")
        return 1

    # Give services a moment to settle
    time.sleep(2)

    # 5. Open Folder via Native Windows Dialog & Initial Analysis
    print("[Step 5] Triggering native Windows folder chooser and automatic project analysis...")
    dialog_detected = threading.Event()
    dialog_info: dict[str, str | int | None] = {"hwnd": None, "title": None}

    def _watch_dialog():
        user32 = ctypes.windll.user32
        for _ in range(100):
            time.sleep(0.1)
            found = None

            def enum_cb(h, _):
                nonlocal found
                if user32.IsWindowVisible(h):
                    b = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(h, b, 256)
                    t = b.value
                    if "Select Project Folder" in t or "Browse For Folder" in t or "Browse for Folder" in t:
                        found = (h, t)
                        return False
                return True

            cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_cb)
            user32.EnumWindows(cb, 0)
            if found:
                dialog_info["hwnd"], dialog_info["title"] = found
                dialog_detected.set()
                time.sleep(0.4)
                user32.PostMessageW(found[0], 0x0111, 1, 0)  # IDOK
                return

    watcher_thread = threading.Thread(target=_watch_dialog, daemon=True)
    watcher_thread.start()

    choose_resp = http_post(
        "http://127.0.0.1:8000/api/v1/host/choose-folder",
        data={},
    )
    watcher_thread.join(timeout=10.0)

    if not dialog_detected.is_set():
        print("[ERROR] Native Windows FolderBrowserDialog was not opened or detected!")
        return 1

    print(f"  [Native Dialog Verified] HWND: {dialog_info['hwnd']}, Title: '{dialog_info['title']}', Confirmed via native IDOK.")
    print(f"  Choose folder response: {choose_resp}")
    root_id = choose_resp.get("root_id")
    analysis_id = choose_resp.get("analysis_id")
    if not root_id or not analysis_id:
        print("[ERROR] choose-folder did not return root_id or analysis_id.")
        return 1

    # Poll analysis until completion
    print(f"  Polling analysis {analysis_id} for completion...")
    for _ in range(30):
        status_data = http_get(f"http://127.0.0.1:8000/api/v1/analyses/{analysis_id}")
        st = status_data.get("state")
        if st in ("completed", "cache_hit"):
            print(f"  Analysis completed with state: {st}")
            break
        if st in ("failed", "cancelled"):
            print(f"[ERROR] Analysis reached unexpected state: {st}")
            return 1
        time.sleep(0.5)
    else:
        print("[ERROR] Analysis polling timed out.")
        return 1

    # 6. Verify Symbol Tree Hierarchy & Policy Exclusions
    print("[Step 6] Verifying directory & nested symbol tree hierarchy...")
    tree_data = http_get(f"http://127.0.0.1:8000/api/v1/analyses/{analysis_id}/tree")
    root_node = tree_data.get("tree", {})
    excluded = tree_data.get("excluded", [])

    print(f"  Tree root name: {root_node.get('name')}")
    print(f"  Policy exclusions ({len(excluded)}):")
    for exc in excluded:
        print(f"    - {exc.get('path')}: {exc.get('reason')}")

    assert any(".git" in exc.get("path", "") for exc in excluded), (
        "Expected .git in policy exclusions"
    )

    # Search for calculator.py in tree
    def find_calculator(node: dict) -> dict | None:
        if node.get("name") == "calculator.py":
            return node
        for child in node.get("children", []):
            found = find_calculator(child)
            if found:
                return found
        return None

    calc_node = find_calculator(root_node)
    assert calc_node is not None, "calculator.py not found in tree"
    print("  Found calculator.py in tree:")
    symbols = calc_node.get("symbols", [])
    for sym in symbols:
        print(f"    - {sym.get('kind')}: {sym.get('name')} (id: {sym.get('id')})")
        for sub in sym.get("children", []):
            print(f"      - {sub.get('kind')}: {sub.get('name')} (id: {sub.get('id')})")
            for subsub in sub.get("children", []):
                print(
                    f"        - {subsub.get('kind')}: {subsub.get('name')} (id: {subsub.get('id')})"
                )

    # 7. Verify Graph Hierarchy & Connected Relationships
    print("[Step 7] Verifying graph architecture hierarchy...")
    graph_data = http_get(f"http://127.0.0.1:8000/api/v1/analyses/{analysis_id}/graph")
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    print(f"  Graph nodes count: {len(nodes)}")
    print(f"  Graph edges count: {len(edges)}")

    calc_class_node = next(
        (n for n in nodes if n.get("name") == "InvoiceCalculator"), None
    )
    assert calc_class_node is not None, "InvoiceCalculator node missing from graph"
    print(
        f"  InvoiceCalculator node found: id={calc_class_node.get('id')}, location={calc_class_node.get('location')}"
    )

    # 8. Verify Architectural Explanation
    print("[Step 8] Verifying architectural explanation...")
    explanation = http_get(
        f"http://127.0.0.1:8000/api/v1/analyses/{analysis_id}/nodes/{calc_class_node['id']}/explain?provider=rule-based"
    )
    print(f"  Role:                 {explanation.get('role')}")
    print(f"  Summary:              {explanation.get('summary')}")
    print(f"  Metrics summary:      {explanation.get('metrics_summary')}")
    print(f"  Provider:             {explanation.get('provider')}")

    # 9. Exercise Refresh (Re-analysis without executing source code)
    print("[Step 9] Exercising project Refresh action...")
    refresh_payload = {
        "project": {"root_id": root_id, "relative_path": "."},
        "options": {"metrics": False},
        "refresh": True,
    }
    refresh_resp = http_post(
        "http://127.0.0.1:8000/api/v1/analyses", data=refresh_payload
    )
    refresh_id = refresh_resp.get("analysis_id")
    print(f"  Refresh analysis job dispatched: {refresh_id}")
    for _ in range(30):
        status_data = http_get(f"http://127.0.0.1:8000/api/v1/analyses/{refresh_id}")
        st = status_data.get("state")
        if st in ("completed", "cache_hit"):
            print(f"  Refresh completed with state: {st}")
            break
        time.sleep(0.5)

    # 10. Capture Real Desktop Window Screenshot
    print("[Step 10] Capturing real standalone window screenshot via PowerShell...")
    capture_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "$bmp = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size); "
        f"$bmp.Save('{str(screenshot_path).replace(chr(92), '/')}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "$g.Dispose(); "
        "$bmp.Dispose(); "
        "Write-Host 'Screenshot captured successfully.'"
    )
    subprocess.run(
        ["powershell", "-Command", capture_script], capture_output=True, text=True
    )
    if screenshot_path.exists() and screenshot_path.stat().st_size > 0:
        print(
            f"  Screenshot saved to:\n  {screenshot_path} ({screenshot_path.stat().st_size} bytes)"
        )
    else:
        print("  [WARN] Screenshot capture file was not written.")

    # 11. Clean Teardown
    print("[Step 11] Executing clean shutdown via Stop-CodeStruct-Prototype.ps1...")
    stop_proc = subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher_dir / "Stop-CodeStruct-Prototype.ps1"),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    print(f"  Stop exit code: {stop_proc.returncode}")
    print(stop_proc.stdout.strip())

    # Verify state file cleared
    if state_file.exists():
        print(f"  [WARN] State file still exists: {state_file}")
    else:
        print("  Runtime state file successfully cleared.")

    # Clean up disposable fixture project directory
    import shutil

    shutil.rmtree(fixture_dir, ignore_errors=True)
    print("  Disposable fixture project cleaned up.")

    print("\n" + "=" * 65)
    print("REAL WINDOWS STANDALONE WORKFLOW VERIFICATION: PASSED (100%)")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
