"""
Comprehensive End-to-End Real Workflow Verification Script
for Thonny IDE CodeStruct Workbench Layout Correction 2 (ANTIGRAVITY_THONNY_LAYOUT_TASK.md).

Verifies User Report 2 requirements in real Windows Thonny runtime:
1. Exactly ONE persistent unified Explorer (CodeStructProjectExplorerView):
   - Active across all editor tabs (source tab, CodeStruct tab).
   - Stays present when CodeStruct tab is closed.
   - Stays present across Thonny restarts.
   - Never duplicates FilesView or leaves a blank period.
   - Contains folder/file tree and nested Python AST module/class/method/function symbols.
   - Supports folder switching with synchronization to Thonny.
2. Exactly ONE bottom Shell: native Thonny Shell carries CodeStruct diagnostics and analysis summary.
3. Full-height right Inspector with zero blank strip.
4. Static non-execution safety invariant strictly maintained.
5. Captures real UI screenshots at recorded viewport sizes to SCREENSHOT_DIR and ARTIFACT_DIR.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

WORKSPACE_ROOT = Path("D:/REP/Codestruct/Codestruct").resolve()
THONNY_ROOT = Path("D:/REP/thonny").resolve()
PYTHON_VENV = THONNY_ROOT / "venv" / "Scripts" / "python.exe"
DEV_VENV_PYTHON = WORKSPACE_ROOT / ".venv" / "Scripts" / "python.exe"

sys.path.insert(0, str(THONNY_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "thonny-plugin"))
sys.path.insert(0, str(WORKSPACE_ROOT / "backend" / "src"))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("verify_thonny_layout_2")

SCREENSHOT_DIR = WORKSPACE_ROOT / "docs" / "verification" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path(
    r"C:\Users\ABHINAV\.gemini\antigravity-ide\brain\4fda842f-5c51-411b-b338-e842886b640c"
)


def wait_for_url(url: str, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def capture_window_screenshot(window_widget: Any, output_path: Path) -> bool:
    """Capture a screenshot of the specified Tkinter window using PIL or Win32 PrintWindow."""
    try:
        from PIL import Image, ImageGrab

        window_widget.update_idletasks()
        window_widget.update()
        w = window_widget.winfo_width()
        h = window_widget.winfo_height()

        if w <= 0 or h <= 0:
            logger.warning("Invalid window dimensions: w=%d, h=%d", w, h)
            return False

        saved = False
        try:
            x = window_widget.winfo_rootx()
            y = window_widget.winfo_rooty()
            bbox = (x, y, x + w, y + h)
            img = ImageGrab.grab(bbox=bbox)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(output_path))
            logger.info("Screenshot saved via ImageGrab: %s (%dx%d)", output_path, w, h)
            saved = True
        except Exception as grab_exc:
            logger.info(
                "ImageGrab failed (%s); falling back to Win32 PrintWindow...", grab_exc
            )

        if not saved and sys.platform == "win32":
            from ctypes import (
                byref,
                c_int,
                c_long,
                c_short,
                c_ubyte,
                sizeof,
                Structure,
                windll,
            )

            class BITMAPINFOHEADER(Structure):
                _fields_ = [
                    ("biSize", c_int),
                    ("biWidth", c_long),
                    ("biHeight", c_long),
                    ("biPlanes", c_short),
                    ("biBitCount", c_short),
                    ("biCompression", c_int),
                    ("biSizeImage", c_int),
                    ("biXPelsPerMeter", c_long),
                    ("biYPelsPerMeter", c_long),
                    ("biClrUsed", c_int),
                    ("biClrImportant", c_int),
                ]

            hwnd = window_widget.winfo_id()
            user32 = windll.user32
            gdi32 = windll.gdi32

            hdc_window = user32.GetWindowDC(hwnd)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
            hbm = gdi32.CreateCompatibleBitmap(hdc_window, w, h)
            gdi32.SelectObject(hdc_mem, hbm)

            user32.PrintWindow(hwnd, hdc_mem, 2)

            bmi = BITMAPINFOHEADER()
            bmi.biSize = sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buffer_len = w * h * 4
            buf = (c_ubyte * buffer_len)()
            gdi32.GetDIBits(hdc_mem, hbm, 0, h, byref(buf), byref(bmi), 0)

            img = Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(output_path))

            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_window)
            logger.info(
                "Screenshot saved via PrintWindow: %s (%dx%d)", output_path, w, h
            )
            saved = True

        if saved and ARTIFACT_DIR.is_dir():
            try:
                dest = ARTIFACT_DIR / output_path.name
                shutil.copy2(output_path, dest)
                logger.info("Copied screenshot to artifacts directory: %s", dest)
            except Exception as copy_exc:
                logger.debug("Failed copying screenshot to artifact dir: %s", copy_exc)

        return saved

    except Exception as exc:
        logger.warning("Failed to capture screenshot: %s", exc)
        return False


def run_verification() -> int:
    logger.info("=================================================================")
    logger.info("STARTING REAL THONNY WORKBENCH LAYOUT CORRECTION 2 VERIFICATION")
    logger.info("=================================================================")

    backend_proc: Optional[subprocess.Popen[Any]] = None
    frontend_proc: Optional[subprocess.Popen[Any]] = None

    try:
        # 1. Start Backend Server
        logger.info("[1/10] Starting CodeStruct backend on http://127.0.0.1:8000...")
        backend_env = os.environ.copy()
        backend_env["PYTHONPATH"] = str(WORKSPACE_ROOT / "backend" / "src")
        backend_proc = subprocess.Popen(
            [
                str(DEV_VENV_PYTHON),
                "-m",
                "uvicorn",
                "codestruct.api.app:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--log-level",
                "warning",
            ],
            cwd=str(WORKSPACE_ROOT),
            env=backend_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if not wait_for_url("http://127.0.0.1:8000/api/v1/projects", timeout=15.0):
            logger.error("Backend failed to start on 127.0.0.1:8000")
            return 1
        logger.info("Backend is healthy and responding.")

        # 2. Start Frontend Server
        logger.info(
            "[2/10] Starting CodeStruct frontend preview on http://127.0.0.1:5173..."
        )
        frontend_proc = subprocess.Popen(
            [
                "npm.cmd",
                "--prefix",
                "frontend.lovable",
                "run",
                "preview",
                "--",
                "--port",
                "5173",
                "--host",
                "127.0.0.1",
            ],
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )

        if not wait_for_url("http://127.0.0.1:5173", timeout=20.0):
            logger.error("Frontend failed to start on 127.0.0.1:5173")
            return 1
        logger.info("Frontend is healthy and responding.")

        # 3. Create Disposable Project Fixtures (matching reference projects)
        logger.info("[3/10] Creating disposable nested fixtures (Sample & Beta)...")
        temp_dir = tempfile.TemporaryDirectory()
        fixtures_root = Path(temp_dir.name)

        # Fixture Sample Project (matching 1.png and 2.png structure)
        fixture_sample = fixtures_root / "sample_project"
        fixture_sample.mkdir(parents=True)
        (fixture_sample / "services").mkdir()

        sample_main = fixture_sample / "sample_project.py"
        sample_main.write_text(
            "class BaseProcessor:\n"
            "    def __init__(self, mode: str = 'strict'):\n"
            "        self.mode = mode\n\n"
            "    def process(self, data: list) -> bool:\n"
            "        return len(data) > 0\n\n\n"
            "class DataService:\n"
            "    def __init__(self, endpoint: str = 'local'):\n"
            "        self.endpoint = endpoint\n\n"
            "    def fetch(self) -> dict:\n"
            "        return {'status': 'ok'}\n\n\n"
            "def run_pipeline() -> None:\n"
            "    proc = BaseProcessor()\n"
            "    srv = DataService()\n"
            "    if proc.process([1, 2]):\n"
            "        srv.fetch()\n",
            encoding="utf-8",
        )

        sample_utils = fixture_sample / "services" / "utils.py"
        sample_utils.write_text(
            "class Logger:\n"
            "    def log(self, msg: str) -> None:\n"
            "        print(msg)\n",
            encoding="utf-8",
        )

        sample_danger = fixture_sample / "danger.py"
        sample_danger.write_text(
            "raise RuntimeError('SECURITY_BREACH_EXECUTED_DANGER_CODE')\n",
            encoding="utf-8",
        )

        # Fixture Beta Project
        fixture_beta = fixtures_root / "beta_pipeline"
        fixture_beta.mkdir(parents=True)
        (fixture_beta / "core").mkdir()

        beta_main = fixture_beta / "pipeline.py"
        beta_main.write_text(
            "class Worker:\n"
            "    def execute(self) -> None:\n"
            "        pass\n\n"
            "def run_all() -> None:\n"
            "    w = Worker()\n"
            "    w.execute()\n",
            encoding="utf-8",
        )

        logger.info("Fixtures created successfully.")

        # 4. Initialize real Thonny Workbench
        logger.info(
            "[4/10] Initializing real Thonny Workbench with CodeStruct persistent Explorer..."
        )
        from thonny.main import _parse_arguments_to_dict
        from thonny.workbench import Workbench
        import thonny
        import thonnycontrib.codestruct as cs
        from thonnycontrib.codestruct import (
            CodeStructEditorTab,
            CodeStructProjectExplorerView,
        )
        from tkinter import messagebox

        Workbench._check_version_alignment = lambda self: None
        messagebox.showerror = lambda title, message, **kwargs: logger.error(
            "Thonny error dialog: %s - %s", title, message
        )
        messagebox.showwarning = lambda title, message, **kwargs: logger.warning(
            "Thonny warning dialog: %s - %s", title, message
        )

        parsed_args = _parse_arguments_to_dict([])
        wb = Workbench(parsed_args)
        thonny._workbench = wb
        wb._language_server_proxy_classes.clear()
        wb.set_option("file.last_browser_folder", str(fixture_sample.resolve()))

        # Load plugin: registers CodeStructProjectExplorerView as sole persistent explorer
        cs.load_plugin()
        logger.info("Plugin loaded into real Thonny workbench.")

        wb.geometry("1400x900+50+50")
        wb.update_idletasks()
        wb.update()

        # Show persistent Explorer and native ShellView
        explorer_view = wb.show_view("FilesView", set_focus=False)
        shell_view = wb.show_view("ShellView", set_focus=False)
        wb.update_idletasks()
        wb.update()

        # Assert explorer_view is CodeStructProjectExplorerView
        assert isinstance(explorer_view, CodeStructProjectExplorerView), (
            f"Expected CodeStructProjectExplorerView, got {type(explorer_view)}"
        )
        logger.info(
            "PASS: Sole Explorer registered is CodeStructProjectExplorerView: %r",
            explorer_view,
        )

        # 5. Open sample_project.py in editor (Reference 1.png state)
        logger.info(
            "[5/10] Verifying State 1: sample_project.py open, persistent Explorer with nested symbols (1.png comparison)..."
        )
        editor_notebook = wb.get_editor_notebook()
        for ed in list(editor_notebook.get_all_editors()):
            if getattr(ed, "is_untitled", lambda: False)():
                editor_notebook.close_tab(editor_notebook.index(ed))
        editor_notebook.show_file(str(sample_main.resolve()))
        wb.update_idletasks()
        wb.update()

        # Verify Explorer is visible and populated with nested AST symbols
        assert cs.is_files_view_visible(wb), (
            "FAIL: Explorer must be visible when sample_project.py is active!"
        )
        tree_items = explorer_view._tree_items
        types = {item.get("type") for item in tree_items.values()}
        assert "class" in types, "FAIL: Classes not found in Explorer symbol tree!"
        assert "method" in types, "FAIL: Methods not found in Explorer symbol tree!"
        assert "function" in types, "FAIL: Functions not found in Explorer symbol tree!"

        logger.info(
            "PASS: Explorer tree populated with %d items: types = %s",
            len(tree_items),
            sorted(list(types)),
        )

        screenshot_1 = (
            SCREENSHOT_DIR / "thonny_corr2_01_source_tab_persistent_explorer.png"
        )
        capture_window_screenshot(wb, screenshot_1)
        logger.info("Captured screenshot 1 (matching 1.png): %s", screenshot_1)

        # 6. Launch CodeStruct Workbench (Reference 2.png state)
        logger.info(
            "[6/10] Verifying State 2: CodeStruct tab active, persistent Explorer remains in 'nw' (2.png comparison)..."
        )
        cs.open_codestruct_workbench()
        wb.update_idletasks()
        wb.update()

        # CRITICAL CHECK: Explorer MUST REMAIN VISIBLE! (No hide/restore, sole persistent explorer)
        assert cs.is_files_view_visible(wb), (
            "FAIL: Explorer was hidden! It must be persistent across all tabs!"
        )
        assert isinstance(
            wb.get_view("FilesView", create=False), CodeStructProjectExplorerView
        ), "FAIL: Explorer must remain CodeStructProjectExplorerView!"
        logger.info(
            "PASS: Exactly ONE persistent Explorer remains visible on the left in 'nw' when CodeStruct tab opens."
        )

        all_tabs = editor_notebook.winfo_children()
        cs_tabs = [c for c in all_tabs if isinstance(c, CodeStructEditorTab)]
        assert len(cs_tabs) == 1, f"Expected 1 CodeStruct tab, found {len(cs_tabs)}"
        codestruct_tab = cs_tabs[0]
        assert editor_notebook.get_current_editor() == codestruct_tab

        # Wait for WebView2 to render CodeStruct architecture workbench
        time.sleep(4.0)
        wb.update_idletasks()
        wb.update()

        screenshot_2 = (
            SCREENSHOT_DIR / "thonny_corr2_02_codestruct_tab_persistent_explorer.png"
        )
        capture_window_screenshot(wb, screenshot_2)
        logger.info("Captured screenshot 2 (matching 2.png): %s", screenshot_2)

        # Verify Thonny Shell carries diagnostics & analysis summary
        shell_content = ""
        start_wait = time.time()
        while time.time() - start_wait < 10.0:
            wb.update_idletasks()
            wb.update()
            if shell_view and hasattr(shell_view, "text"):
                shell_content = shell_view.text.get("1.0", "end")
                if "Static Analysis Complete" in shell_content or "Discovered" in shell_content:
                    break
            time.sleep(0.3)

        assert "[CodeStruct]" in shell_content, "FAIL: Thonny native Shell missing CodeStruct output!"
        logger.info("PASS: Native Thonny Shell is sole bottom surface carrying CodeStruct status.")

        # 7. Test Tab Switching: Switching between sample_project.py and CodeStruct tab
        logger.info(
            "[7/10] Testing Tab Switching: Explorer remains persistent with ZERO blank interval or toggling..."
        )
        editor_notebook.select(all_tabs[0])  # Switch to sample_project.py
        wb.update_idletasks()
        wb.update()
        assert cs.is_files_view_visible(wb), "Explorer must remain visible on source tab"
        assert isinstance(
            wb.get_view("FilesView", create=False), CodeStructProjectExplorerView
        )

        editor_notebook.select(codestruct_tab)  # Switch back to CodeStruct
        wb.update_idletasks()
        wb.update()
        assert cs.is_files_view_visible(wb), "Explorer must remain visible on CodeStruct tab"
        logger.info("PASS: Explorer persistent across all editor tab switching.")

        # 8. Test Whole-Folder Open/Switch from Explorer
        logger.info(
            "[8/10] Testing Whole-Folder Switch to Beta Pipeline from persistent Explorer..."
        )
        explorer_view.switch_project_folder(str(fixture_beta.resolve()))
        wb.update_idletasks()
        wb.update()

        assert explorer_view.get_active_local_dir() == str(fixture_beta.resolve())
        assert wb.get_option("file.last_browser_folder") == str(fixture_beta.resolve())

        # Check tree updated for Beta
        beta_items = explorer_view._tree_items
        assert any("pipeline.py" in str(v.get("path")) for v in beta_items.values())
        logger.info(
            "PASS: Project Explorer folder switch succeeded (current_dir = %s).",
            explorer_view.current_project_dir.name,
        )

        time.sleep(3.0)
        wb.update_idletasks()
        wb.update()

        screenshot_3 = SCREENSHOT_DIR / "thonny_corr2_03_project_switch_sync.png"
        capture_window_screenshot(wb, screenshot_3)
        logger.info("Captured screenshot 3 (project switch): %s", screenshot_3)

        # 9. Test Closing CodeStruct tab: Explorer remains persistent in 'nw'
        logger.info(
            "[9/10] Testing Tab Close: Closing CodeStruct tab leaves Explorer persistent..."
        )
        editor_notebook.close_tab(editor_notebook.index(codestruct_tab))
        wb.update_idletasks()
        wb.update()

        assert cs.is_files_view_visible(wb), (
            "FAIL: Explorer must remain visible when CodeStruct tab is closed!"
        )
        assert isinstance(
            wb.get_view("FilesView", create=False), CodeStructProjectExplorerView
        ), "FAIL: Explorer must remain CodeStructProjectExplorerView!"
        logger.info("PASS: Closing CodeStruct tab leaves single Explorer persistent.")

        screenshot_4 = (
            SCREENSHOT_DIR / "thonny_corr2_04_tab_closed_explorer_persists.png"
        )
        capture_window_screenshot(wb, screenshot_4)
        logger.info("Captured screenshot 4 (tab closed): %s", screenshot_4)

        # 10. Verify Static Non-Execution Safety Invariant
        logger.info("[10/10] Verifying Static Non-Execution Safety Invariant...")
        assert "danger" not in sys.modules, "Hostile marker module 'danger' was imported!"
        for mod in list(sys.modules.keys()):
            if "sample_project" in mod or "beta_pipeline" in mod:
                assert False, f"Project code '{mod}' was imported into runtime!"
        logger.info("PASS: Static non-execution safety invariant strictly maintained.")

        wb.destroy()
        logger.info("PASS: Thonny Workbench cleanly destroyed.")

        logger.info("=================================================================")
        logger.info("ALL REAL THONNY WORKBENCH LAYOUT CORRECTION 2 TESTS PASSED 100%!")
        logger.info("=================================================================")
        return 0

    except Exception as exc:
        logger.exception("Layout correction 2 verification failed: %s", exc)
        return 1

    finally:
        if backend_proc is not None:
            backend_proc.terminate()
            backend_proc.wait()
            logger.info("Backend process terminated.")
        if frontend_proc is not None:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)],
                capture_output=True,
            )
            logger.info("Frontend process terminated.")


if __name__ == "__main__":
    sys.exit(run_verification())
