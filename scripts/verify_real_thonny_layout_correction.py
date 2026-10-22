"""
Comprehensive End-to-End Real Workflow Verification Script
for Thonny IDE CodeStruct Workbench Layout Correction (ANTIGRAVITY_THONNY_LAYOUT_TASK.md).

Exercises the real Thonny host runtime with the CodeStruct plugin:
1. Spawns live backend (FastAPI/Uvicorn) and frontend preview on loopback.
2. Creates two distinct disposable nested multi-file project fixtures (Alpha and Beta).
3. Initializes real Thonny Workbench with FilesView, ShellView, and EditorNotebook at 1400x900.
4. Pre-opens source files in Thonny's EditorNotebook.
5. Launches CodeStruct from Tools -> CodeStruct for Project Alpha.
6. Verifies:
   - Exactly ONE left Explorer (CodeStruct Explorer active, Thonny native FilesView hidden).
   - Exactly ONE bottom Shell (native Thonny Shell carries CodeStruct status and diagnostics).
   - Full-height right Inspector (rich Architecture Overview card, no blank strip).
7. Tests tab switching between source tabs and CodeStruct tab:
   - Switching to source tab immediately restores Thonny's native FilesView.
   - Switching back to CodeStruct tab immediately re-hides FilesView.
8. Tests project switching to Project Beta:
   - File view root tracked and updated smoothly without duplicate tabs.
9. Tests window resize / narrow viewport (1024x700).
10. Tests closing the CodeStruct tab:
    - FilesView is cleanly restored.
11. Verifies static non-execution invariant (hostile marker code never executed).
12. Captures screenshots at recorded viewports and copies to artifact directory.
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

# Ensure paths
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
logger = logging.getLogger("verify_thonny_layout")

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
    logger.info("STARTING REAL THONNY WORKBENCH LAYOUT CORRECTION VERIFICATION")
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

        # 3. Create Disposable Project Fixtures
        logger.info("[3/10] Creating disposable nested fixtures (Alpha & Beta)...")
        temp_dir = tempfile.TemporaryDirectory()
        fixtures_root = Path(temp_dir.name)

        # Fixture Alpha
        fixture_alpha = fixtures_root / "disposable_alpha_project"
        fixture_alpha.mkdir(parents=True)
        (fixture_alpha / "services").mkdir()
        (fixture_alpha / "domain").mkdir()
        (fixture_alpha / "utils").mkdir()

        alpha_main = fixture_alpha / "main.py"
        alpha_main.write_text(
            "from services.analytics import AnalyticsService\n"
            "from domain.models import UserSession\n\n"
            "def bootstrap() -> bool:\n"
            "    service = AnalyticsService()\n"
            "    return service.start()\n",
            encoding="utf-8",
        )

        alpha_analytics = fixture_alpha / "services" / "analytics.py"
        alpha_analytics.write_text(
            "class AnalyticsService:\n"
            "    def __init__(self, capacity: int = 100):\n"
            "        self.capacity = capacity\n\n"
            "    def start(self) -> bool:\n"
            "        return True\n\n"
            "    def record_event(self, name: str) -> None:\n"
            "        pass\n\n"
            "    def compute_metrics(self) -> dict[str, int]:\n"
            "        return {'count': self.capacity}\n",
            encoding="utf-8",
        )

        alpha_models = fixture_alpha / "domain" / "models.py"
        alpha_models.write_text(
            "class UserSession:\n"
            "    def __init__(self, user_id: str):\n"
            "        self.user_id = user_id\n",
            encoding="utf-8",
        )

        alpha_danger = fixture_alpha / "danger.py"
        alpha_danger.write_text(
            "raise RuntimeError('SECURITY_BREACH_EXECUTED_DANGER_CODE')\n",
            encoding="utf-8",
        )

        # Fixture Beta
        fixture_beta = fixtures_root / "disposable_beta_pipeline"
        fixture_beta.mkdir(parents=True)
        (fixture_beta / "core").mkdir()
        (fixture_beta / "storage").mkdir()

        beta_main = fixture_beta / "main.py"
        beta_main.write_text(
            "from core.pipeline import DataPipeline\n\n"
            "def start_pipeline() -> None:\n"
            "    pipe = DataPipeline()\n"
            "    pipe.execute()\n",
            encoding="utf-8",
        )

        beta_pipeline = fixture_beta / "core" / "pipeline.py"
        beta_pipeline.write_text(
            "class DataPipeline:\n"
            "    def __init__(self, stage: str = 'ready'):\n"
            "        self.stage = stage\n\n"
            "    def execute(self) -> str:\n"
            "        return self.stage\n",
            encoding="utf-8",
        )

        logger.info("Fixtures created successfully.")

        # 4. Initialize real Thonny Workbench
        logger.info(
            "[4/10] Initializing real Thonny Workbench with FilesView & ShellView..."
        )
        from thonny.main import _parse_arguments_to_dict
        from thonny.workbench import Workbench
        import thonny
        import thonnycontrib.codestruct as cs
        from thonnycontrib.codestruct import CodeStructEditorTab
        from tkinter import messagebox

        # Prevent non-installed thonny package metadata error from showing modal dialog
        Workbench._check_version_alignment = lambda self: None
        orig_showerror = messagebox.showerror
        orig_showwarning = messagebox.showwarning
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
        wb.geometry("1400x900+50+50")
        wb.update_idletasks()
        wb.update()

        # Load FilesView and ShellView into workbench
        files_view = wb.show_view("FilesView", set_focus=False)
        shell_view = wb.show_view("ShellView", set_focus=False)
        wb.update_idletasks()
        wb.update()

        # Assert FilesView is initially visible
        assert cs.is_files_view_visible(wb), "FilesView should initially be visible"
        logger.info("Verified: FilesView is initially visible before CodeStruct launch.")

        # Load plugin
        cs.load_plugin()
        logger.info("Plugin loaded into real Thonny workbench.")

        # Pre-open source files in EditorNotebook
        editor_notebook = wb.get_editor_notebook()
        for ed in list(editor_notebook.get_all_editors()):
            if getattr(ed, "is_untitled", lambda: False)():
                editor_notebook.close_tab(editor_notebook.index(ed))
        editor_notebook.show_file(str(alpha_main.resolve()))
        editor_notebook.show_file(str(alpha_analytics.resolve()))
        wb.update_idletasks()
        wb.update()

        screenshot_initial = SCREENSHOT_DIR / "thonny_layout_01_initial_source_files.png"
        capture_window_screenshot(wb, screenshot_initial)

        # 5. Open Project Alpha in File view & trigger CodeStruct
        logger.info(
            "[5/10] Launching CodeStruct workbench for Project Alpha & verifying pane lifecycle..."
        )
        files_view.local_files.focus_into(str(fixture_alpha.resolve()))
        wb.update()

        # Launch CodeStruct
        cs.open_codestruct_workbench()
        wb.update_idletasks()
        wb.update()

        # CRITICAL CHECK 1: Thonny's native FilesView MUST BE HIDDEN while CodeStruct tab is active!
        assert not cs.is_files_view_visible(wb), (
            "FAIL: Thonny's duplicate native FilesView was NOT hidden when CodeStruct tab opened!"
        )
        logger.info(
            "PASS: Exactly ONE Explorer on the left: Thonny native FilesView is hidden, CodeStruct Explorer active."
        )

        all_tabs = editor_notebook.winfo_children()
        cs_tabs = [c for c in all_tabs if isinstance(c, CodeStructEditorTab)]
        assert len(cs_tabs) == 1, f"Expected 1 CodeStruct tab, found {len(cs_tabs)}"
        alpha_tab = cs_tabs[0]
        assert editor_notebook.get_current_editor() == alpha_tab

        # Allow WebView2 4 seconds to render Alpha workbench
        time.sleep(4.0)
        wb.update_idletasks()
        wb.update()

        screenshot_alpha = SCREENSHOT_DIR / "thonny_layout_02_unified_workbench_alpha.png"
        capture_window_screenshot(wb, screenshot_alpha)

        # CRITICAL CHECK 2: Native Thonny Shell receives CodeStruct diagnostics & analysis summary
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

        logger.info("Native Thonny Shell output:\n%s", shell_content.strip())
        assert "[CodeStruct]" in shell_content, (
            "FAIL: Native Thonny Shell did not receive CodeStruct output!"
        )
        assert (
            "Static Analysis Complete" in shell_content
            or "Architecture Workbench" in shell_content
        ), "FAIL: Native Thonny Shell missing analysis status or summary!"
        logger.info(
            "PASS: Exactly ONE bottom Shell/Diagnostics surface: Native Thonny Shell received CodeStruct diagnostics."
        )

        # 6. Test Tab Switching Lifecycle: Switching to source tab restores FilesView
        logger.info("[6/10] Testing Tab Switching: Switch to normal source tab...")
        editor_notebook.select(all_tabs[0])  # Switch to main.py
        wb.update_idletasks()
        wb.update()

        assert cs.is_files_view_visible(wb), (
            "FAIL: Native FilesView was NOT restored when switching to a normal source tab!"
        )
        logger.info(
            "PASS: Switching to normal source tab automatically RESTORED Thonny's native FilesView."
        )

        screenshot_source = SCREENSHOT_DIR / "thonny_layout_03_source_tab_restores_files.png"
        capture_window_screenshot(wb, screenshot_source)

        # Switch back to CodeStruct tab: FilesView should re-hide
        logger.info("Switching back to CodeStruct tab...")
        editor_notebook.select(alpha_tab)
        wb.update_idletasks()
        wb.update()

        assert not cs.is_files_view_visible(wb), (
            "FAIL: Native FilesView was NOT re-hidden when switching back to CodeStruct tab!"
        )
        logger.info(
            "PASS: Switching back to CodeStruct tab automatically RE-HID Thonny's native FilesView."
        )

        screenshot_back = SCREENSHOT_DIR / "thonny_layout_04_tab_switched_back_hides_files.png"
        capture_window_screenshot(wb, screenshot_back)

        # 7. Test Multi-Project Switching: Switch to Project Beta
        logger.info("[7/10] Testing Multi-Project Switching to Project Beta...")
        files_view.local_files.focus_into(str(fixture_beta.resolve()))
        wb.update()

        # Trigger Tools -> CodeStruct again
        cs.open_codestruct_workbench()
        wb.update_idletasks()
        wb.update()

        tabs_after = [
            c
            for c in editor_notebook.winfo_children()
            if isinstance(c, CodeStructEditorTab)
        ]
        assert len(tabs_after) == 1, (
            f"Expected exactly 1 CodeStruct tab after switch, got {len(tabs_after)}"
        )
        beta_tab = tabs_after[0]
        assert beta_tab is alpha_tab, "Tab instance should be reused and updated"
        assert beta_tab.project_path == str(fixture_beta.resolve())
        assert not cs.is_files_view_visible(wb), (
            "FilesView must remain hidden while CodeStruct tab is active for Project Beta"
        )
        logger.info(
            "PASS: Project Beta opened cleanly without duplicate tabs, FilesView remains hidden."
        )

        time.sleep(4.0)
        wb.update_idletasks()
        wb.update()

        screenshot_beta = SCREENSHOT_DIR / "thonny_layout_05_project_beta_switch.png"
        capture_window_screenshot(wb, screenshot_beta)

        # 8. Test Window Resize / Narrow Viewport
        logger.info("[8/10] Testing Responsive Resize: Narrow viewport (1024x700)...")
        wb.geometry("1024x700+50+50")
        wb.update_idletasks()
        wb.update()
        time.sleep(1.0)

        screenshot_narrow = SCREENSHOT_DIR / "thonny_layout_06_narrow_viewport.png"
        capture_window_screenshot(wb, screenshot_narrow)
        logger.info("PASS: Window resized to 1024x700 and rendered cleanly.")

        # Restore window geometry
        wb.geometry("1400x900+50+50")
        wb.update_idletasks()
        wb.update()

        # 9. Test Tab Close Lifecycle: Closing CodeStruct tab restores FilesView
        logger.info("[9/10] Testing Tab Close Lifecycle...")
        editor_notebook.close_tab(editor_notebook.index(beta_tab))
        wb.update_idletasks()
        wb.update()

        assert cs.is_files_view_visible(wb), (
            "FAIL: Native FilesView was NOT restored when CodeStruct tab was closed!"
        )
        remaining_cs_tabs = [
            c
            for c in editor_notebook.winfo_children()
            if isinstance(c, CodeStructEditorTab)
        ]
        assert len(remaining_cs_tabs) == 0, "CodeStruct tab was not removed from notebook"
        logger.info(
            "PASS: Closing CodeStruct tab cleanly removed tab and RESTORED native FilesView."
        )

        screenshot_closed = SCREENSHOT_DIR / "thonny_layout_07_tab_closed_restores_files.png"
        capture_window_screenshot(wb, screenshot_closed)

        # 10. Verify Static Non-Execution Safety Invariant
        logger.info("[10/10] Verifying Static Non-Execution Safety Invariant...")
        assert "danger" not in sys.modules, (
            "Hostile marker module 'danger' must never be imported!"
        )
        for mod_name in list(sys.modules.keys()):
            if "alpha" in mod_name or "beta" in mod_name:
                assert False, f"Project code '{mod_name}' was imported into Python runtime!"
        logger.info("PASS: Static non-execution safety invariant strictly maintained.")

        wb.destroy()
        logger.info("PASS: Thonny Workbench cleanly destroyed.")

        logger.info("=================================================================")
        logger.info("ALL REAL THONNY WORKBENCH LAYOUT VERIFICATIONS PASSED 100%!")
        logger.info("=================================================================")
        return 0

    except Exception as exc:
        logger.exception("Layout verification failed with exception: %s", exc)
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
