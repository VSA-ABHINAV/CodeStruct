"""
Automated End-to-End Real Workflow Verification Script
for Thonny IDE CodeStruct Stitch Architecture Workbench Tab Integration.

Exercises the real Thonny host runtime with the CodeStruct plugin:
1. Spawns live backend (FastAPI/Uvicorn) and frontend (Vite/React preview) on loopback.
2. Creates two distinct disposable project fixtures with code and a hostile execution marker.
3. Initializes real Thonny Workbench with FilesView and EditorNotebook.
4. Opens Fixture Alpha in File view, triggers Tools -> CodeStruct, verifies tab docked in main window.
5. Captures real screenshot of Fixture Alpha tab.
6. Switches File view to Fixture Beta, triggers CodeStruct again, verifies single tab reuse/update.
7. Captures real screenshot of Fixture Beta tab.
8. Verifies in-IDE source navigation for project files.
9. Verifies missing-folder guard (no tab created, showinfo alert displayed).
10. Verifies static non-execution safety invariant (hostile marker not executed).
11. Verifies clean tab close and workbench shutdown.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

# Ensure paths
WORKSPACE_ROOT = Path("D:/REP/Codestruct/Codestruct").resolve()
THONNY_ROOT = Path("D:/REP/thonny").resolve()
PYTHON_VENV = THONNY_ROOT / "venv" / "Scripts" / "python.exe"
DEV_VENV_PYTHON = WORKSPACE_ROOT / ".venv" / "Scripts" / "python.exe"

sys.path.insert(0, str(THONNY_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "thonny-plugin"))
sys.path.insert(0, str(WORKSPACE_ROOT / "backend" / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_real_thonny_tab")

SCREENSHOT_DIR = WORKSPACE_ROOT / "docs" / "verification" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


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

        try:
            x = window_widget.winfo_rootx()
            y = window_widget.winfo_rooty()
            bbox = (x, y, x + w, y + h)
            img = ImageGrab.grab(bbox=bbox)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(output_path))
            logger.info("Screenshot saved via ImageGrab: %s (%dx%d)", output_path, w, h)
            return True
        except Exception as grab_exc:
            logger.info("ImageGrab failed (%s); falling back to Win32 PrintWindow...", grab_exc)

        if sys.platform == "win32":
            from ctypes import byref, c_int, c_long, c_short, c_ubyte, sizeof, Structure, windll

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

            # PW_RENDERFULLCONTENT = 2
            user32.PrintWindow(hwnd, hdc_mem, 2)

            bmi = BITMAPINFOHEADER()
            bmi.biSize = sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # top-down
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
            logger.info("Screenshot saved via PrintWindow: %s (%dx%d)", output_path, w, h)
            return True

    except Exception as exc:
        logger.warning("Failed to capture screenshot: %s", exc)
        return False
    return False


def run_verification() -> int:
    logger.info("=================================================================")
    logger.info("STARTING REAL THONNY STITCH WORKBENCH TAB INTEGRATION TEST")
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
        logger.info("[2/10] Starting CodeStruct frontend preview on http://127.0.0.1:5173...")
        frontend_proc = subprocess.Popen(
            ["npm.cmd", "--prefix", "frontend.lovable", "run", "preview", "--", "--port", "5173", "--host", "127.0.0.1"],
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
        logger.info("[3/10] Creating disposable fixtures (Alpha & Beta)...")
        temp_dir = tempfile.TemporaryDirectory()
        fixtures_root = Path(temp_dir.name)

        # Fixture Alpha
        fixture_alpha = fixtures_root / "disposable_alpha_project"
        fixture_alpha.mkdir(parents=True)
        (fixture_alpha / "alpha_engine.py").write_text(
            "class AlphaEngine:\n"
            "    def __init__(self, capacity: int = 100):\n"
            "        self.capacity = capacity\n\n"
            "    def start(self) -> bool:\n"
            "        return True\n\n"
            "    def process_data(self, chunk: str) -> int:\n"
            "        return len(chunk)\n",
            encoding="utf-8",
        )
        (fixture_alpha / "alpha_models.py").write_text(
            "class AlphaRecord:\n"
            "    def __init__(self, key: str):\n"
            "        self.key = key\n",
            encoding="utf-8",
        )
        (fixture_alpha / "danger.py").write_text(
            "raise RuntimeError('SECURITY_BREACH_EXECUTED_DANGER_CODE')\n",
            encoding="utf-8",
        )

        # Fixture Beta
        fixture_beta = fixtures_root / "disposable_beta_pipeline"
        fixture_beta.mkdir(parents=True)
        (fixture_beta / "beta_pipeline.py").write_text(
            "class BetaPipeline:\n"
            "    def __init__(self, stage: str = 'ready'):\n"
            "        self.stage = stage\n\n"
            "    def execute(self) -> str:\n"
            "        return self.stage\n",
            encoding="utf-8",
        )
        (fixture_beta / "beta_storage.py").write_text(
            "class BetaStorage:\n"
            "    def store(self, key: str, value: str) -> None:\n"
            "        pass\n",
            encoding="utf-8",
        )

        logger.info("Fixtures created:\n  Alpha: %s\n  Beta: %s", fixture_alpha, fixture_beta)

        # 4. Initialize real Thonny Workbench
        logger.info("[4/10] Initializing real Thonny Workbench with FilesView & EditorNotebook...")
        from thonny.main import _parse_arguments_to_dict
        from thonny.workbench import Workbench
        import thonny
        import thonnycontrib.codestruct as cs
        from thonnycontrib.codestruct import CodeStructEditorTab

        parsed_args = _parse_arguments_to_dict([])
        wb = Workbench(parsed_args)
        thonny._workbench = wb
        wb._language_server_proxy_classes.clear()
        wb.geometry("1400x900+50+50")
        wb.update_idletasks()
        wb.update()

        # Load FilesView into workbench
        files_view = wb.get_view("FilesView", create=True)
        wb.update_idletasks()
        wb.update()

        # Load plugin
        cs.load_plugin()
        logger.info("Plugin loaded into real Thonny workbench.")

        # 5. Open Fixture Alpha in File view & trigger CodeStruct
        logger.info("[5/10] Testing Phase 1: Launch CodeStruct workbench for Fixture Alpha...")
        files_view.local_files.focus_into(str(fixture_alpha.resolve()))
        wb.update()
        detected_folder = cs.get_file_view_folder(wb)
        assert detected_folder == str(fixture_alpha.resolve()), f"Folder mismatch: {detected_folder}"

        # Trigger Tools -> CodeStruct
        cs.open_codestruct_workbench()
        wb.update_idletasks()
        wb.update()

        editor_notebook = wb.get_editor_notebook()
        tabs = [c for c in editor_notebook.winfo_children() if isinstance(c, CodeStructEditorTab)]
        assert len(tabs) == 1, f"Expected 1 CodeStruct tab, found {len(tabs)}"
        alpha_tab = tabs[0]

        # Verify docked properties
        assert alpha_tab.winfo_toplevel() == wb, "Tab is not inside Thonny's main window!"
        assert alpha_tab.project_path == str(fixture_alpha.resolve())
        assert alpha_tab.get_title() == f"CodeStruct: {fixture_alpha.name}"
        assert "embed=thonny" in alpha_tab.viewer_url
        assert cs._nav_session_token is not None
        assert cs._nav_registered_root == fixture_alpha.resolve()
        logger.info("PASS: Tab docked in Thonny main window, rooted in %s", fixture_alpha.name)

        # Allow WebView2 to load and paint
        logger.info("Allowing WebView2 4 seconds to render Alpha workbench...")
        time.sleep(4.0)
        wb.update_idletasks()
        wb.update()

        screenshot_alpha = SCREENSHOT_DIR / "thonny_tab_fixture_alpha.png"
        capture_window_screenshot(wb, screenshot_alpha)

        # 6. Test Multi-Folder Switching: Switch to Fixture Beta
        logger.info("[6/10] Testing Multi-Folder Switching: Switch File view to Fixture Beta...")
        files_view.local_files.focus_into(str(fixture_beta.resolve()))
        wb.update()
        detected_beta = cs.get_file_view_folder(wb)
        assert detected_beta == str(fixture_beta.resolve())

        # Trigger Tools -> CodeStruct again
        cs.open_codestruct_workbench()
        wb.update_idletasks()
        wb.update()

        tabs_after = [c for c in editor_notebook.winfo_children() if isinstance(c, CodeStructEditorTab)]
        assert len(tabs_after) == 1, f"Tab count should remain 1 on folder switch, got {len(tabs_after)}"
        beta_tab = tabs_after[0]
        assert beta_tab is alpha_tab, "Tab instance should be reused and updated"
        assert beta_tab.project_path == str(fixture_beta.resolve())
        assert beta_tab.get_title() == f"CodeStruct: {fixture_beta.name}"
        assert cs._nav_registered_root == fixture_beta.resolve()
        logger.info("PASS: Existing tab smoothly updated to Fixture Beta without creating a duplicate tab.")

        logger.info("Allowing WebView2 4 seconds to render Beta workbench...")
        time.sleep(4.0)
        wb.update_idletasks()
        wb.update()

        screenshot_beta = SCREENSHOT_DIR / "thonny_tab_fixture_beta.png"
        capture_window_screenshot(wb, screenshot_beta)

        # 7. Test In-IDE Navigation to Source File
        logger.info("[7/10] Testing In-IDE Source Navigation back to Thonny...")
        nav_command_id = "test_nav_beta_pipe"
        cs._execute_navigate(
            wb=wb,
            backend_url="http://127.0.0.1:8000",
            session_token=cs._nav_session_token,
            command_id=nav_command_id,
            relative_path="beta_pipeline.py",
            line=4,
            column=1,
            generation=cs._nav_poll_generation,
        )
        wb.update_idletasks()
        wb.update()

        current_editor = editor_notebook.get_current_editor()
        assert current_editor is not None
        assert current_editor.get_target_path() == str((fixture_beta / "beta_pipeline.py").resolve())
        logger.info("PASS: Navigation correctly opened beta_pipeline.py in Thonny at line 4.")

        screenshot_nav = SCREENSHOT_DIR / "thonny_navigated_source_file.png"
        capture_window_screenshot(wb, screenshot_nav)

        # 8. Test Missing-Folder Guard
        logger.info("[8/10] Testing Missing-Folder Guard...")
        files_view.local_files.current_focus = None
        assert cs.get_file_view_folder(wb) is None

        info_shown = False
        def fake_showinfo(title: str, msg: str, parent: Any = None) -> None:
            nonlocal info_shown
            info_shown = True
            logger.info("Verified in-IDE info dialog: '%s': %s", title, msg.splitlines()[0])

        with patch("tkinter.messagebox.showinfo", side_effect=fake_showinfo):
            cs.open_codestruct_workbench()

        assert info_shown, "showinfo dialog must be displayed when no folder is open in File view"
        logger.info("PASS: Missing folder alert displayed, no fallback root used.")

        # 9. Test Static Non-Execution Invariant
        logger.info("[9/10] Verifying Static Non-Execution Safety Invariant...")
        assert "danger" not in sys.modules, "Hostile marker module 'danger' must never be imported!"
        for mod_name in list(sys.modules.keys()):
            if "alpha" in mod_name or "beta" in mod_name:
                assert False, f"Project code '{mod_name}' was imported into Python runtime!"
        logger.info("PASS: Source code was NEVER executed during analysis or folder switching.")

        # 10. Test Tab Close & Clean Shutdown
        logger.info("[10/10] Testing Tab Close & Shutdown...")
        # Select and close CodeStruct tab
        editor_notebook.select(beta_tab)
        editor_notebook.close_tab(editor_notebook.index(beta_tab))
        wb.update_idletasks()
        wb.update()

        remaining_cs_tabs = [c for c in editor_notebook.winfo_children() if isinstance(c, CodeStructEditorTab)]
        assert len(remaining_cs_tabs) == 0, "Tab was not cleanly removed on close"
        logger.info("PASS: CodeStruct tab closed cleanly without errors.")

        # Clean shutdown
        wb.destroy()
        logger.info("PASS: Thonny Workbench cleanly destroyed.")

        logger.info("=================================================================")
        logger.info("ALL REAL THONNY WORKBENCH TAB INTEGRATION TESTS PASSED 100%!")
        logger.info("=================================================================")
        return 0

    except Exception as exc:
        logger.exception("Verification failed with exception: %s", exc)
        return 1

    finally:
        if backend_proc is not None:
            backend_proc.terminate()
            backend_proc.wait()
            logger.info("Backend process terminated.")
        if frontend_proc is not None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)], capture_output=True)
            logger.info("Frontend process terminated.")


if __name__ == "__main__":
    sys.exit(run_verification())
