"""
Comprehensive unit and integration tests for Thonny CodeStruct adapter plugin.
Uses constrained autospec mocks of real Thonny classes to prevent API mismatches.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, create_autospec, patch

# Add Thonny and plugin to sys.path
sys.path.insert(0, r"d:\REP\thonny")
plugin_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(plugin_root))

import thonnycontrib.codestruct as cs
from thonny.editors import Editor, EditorNotebook
from thonny.workbench import Workbench
from thonnycontrib.codestruct import (
    CodeStructAnalysisWorker,
    ConfigurationError,
    analyze_current_project,
    build_viewer_url,
    get_unsaved_project_files,
    is_loopback_url,
    on_workbench_shutdown,
    parse_root_mappings,
    resolve_local_folder_to_project,
)


class TestCodeStructPlugin(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        src_fixtures = Path(__file__).resolve().parent / "fixtures"
        self.fixtures_dir = Path(self._temp_dir.name) / "fixtures"
        shutil.copytree(src_fixtures, self.fixtures_dir)
        self.root_a = self.fixtures_dir / "project_a"
        self.root_a.mkdir(parents=True, exist_ok=True)
        self.sub_a = self.root_a / "pkg" / "sub"
        self.sub_a.mkdir(parents=True, exist_ok=True)

        self.root_b = self.fixtures_dir / "project_b"
        self.root_b.mkdir(parents=True, exist_ok=True)

        # Reset global adapter state before each test
        cs._active_operation = None
        cs._active_worker = None
        cs._is_shutting_down = False
        cs._nav_session_token = None
        cs._nav_registered_file = None
        cs._nav_registered_file_resolved = None
        cs._nav_poll_active = False
        cs._nav_poll_generation = 0
        cs._nav_poll_in_flight = False
        cs._nav_queue = queue.Queue()

    def tearDown(self):
        # Reset global adapter state after each test
        cs._active_operation = None
        cs._active_worker = None
        cs._is_shutting_down = False
        cs._nav_session_token = None
        cs._nav_registered_file = None
        cs._nav_registered_file_resolved = None
        cs._nav_poll_active = False
        cs._nav_poll_generation = 0
        cs._nav_poll_in_flight = False
        cs._nav_queue = queue.Queue()
        try:
            self._temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. Root Mapping Parsing & Validation Tests
    # -------------------------------------------------------------------------
    def test_parse_root_mappings_valid(self):
        raw = f"proj_a={self.root_a};proj_b={self.root_b}"
        roots = parse_root_mappings(raw)
        self.assertEqual(len(roots), 2)
        self.assertEqual(roots["proj_a"], self.root_a.resolve())
        self.assertEqual(roots["proj_b"], self.root_b.resolve())

    def test_parse_root_mappings_missing_or_empty(self):
        roots = parse_root_mappings("")
        self.assertEqual(roots, {})

    def test_parse_root_mappings_invalid_syntax_missing_equals(self):
        raw = f"{self.root_a}"
        with self.assertRaises(ConfigurationError) as ctx:
            parse_root_mappings(raw)
        self.assertIn("Invalid mapping entry", str(ctx.exception))

    def test_parse_root_mappings_nonexistent_directory(self):
        raw = r"bad_root=C:\nonexistent_directory_codestruct_xyz"
        with self.assertRaises(ConfigurationError) as ctx:
            parse_root_mappings(raw)
        self.assertIn("does not exist or is inaccessible", str(ctx.exception))

    def test_parse_root_mappings_conflicting_duplicate_root_id(self):
        raw = f"dup_id={self.root_a};dup_id={self.root_b}"
        with self.assertRaises(ConfigurationError) as ctx:
            parse_root_mappings(raw)
        self.assertIn("Conflicting mapping", str(ctx.exception))
        self.assertIn("dup_id", str(ctx.exception))

    def test_parse_root_mappings_conflicting_duplicate_directory(self):
        raw = f"root_1={self.root_a};root_2={self.root_a}"
        with self.assertRaises(ConfigurationError) as ctx:
            parse_root_mappings(raw)
        self.assertIn("Conflicting mapping", str(ctx.exception))
        self.assertIn("multiple root IDs", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 2. Local Folder Resolution & Prefix-Collision Tests
    # -------------------------------------------------------------------------
    def test_resolve_exact_and_nested_roots(self):
        roots = {"proj_a": self.root_a.resolve()}

        # Exact root match -> (root_id, ".")
        match = resolve_local_folder_to_project(self.root_a, roots)
        self.assertEqual(match, ("proj_a", "."))

        # Nested folder match -> (root_id, "pkg/sub")
        match = resolve_local_folder_to_project(self.sub_a, roots)
        self.assertEqual(match, ("proj_a", "pkg/sub"))

    def test_resolve_overlapping_roots_selects_most_specific(self):
        roots = {
            "root_broad": self.root_a.resolve(),
            "root_specific": self.sub_a.resolve(),
        }
        # Nested target should match the more specific root
        match = resolve_local_folder_to_project(self.sub_a, roots)
        self.assertEqual(match, ("root_specific", "."))

    def test_prefix_collision_prevention(self):
        # Create a sibling folder that shares a string prefix: "project_a_extra"
        sibling_dir = self.fixtures_dir / "project_a_extra"
        sibling_dir.mkdir(parents=True, exist_ok=True)
        roots = {"proj_a": self.root_a.resolve()}

        # Sibling must NOT match proj_a
        match = resolve_local_folder_to_project(sibling_dir, roots)
        self.assertIsNone(match)

    def test_unauthorized_folder_no_fallback_to_server(self):
        unauth_dir = self.fixtures_dir / "unauthorized_folder"
        unauth_dir.mkdir(parents=True, exist_ok=True)
        roots = {"proj_a": self.root_a.resolve()}

        match = resolve_local_folder_to_project(unauth_dir, roots)
        self.assertIsNone(match)

    # -------------------------------------------------------------------------
    # 3. Loopback URL & Safe Viewer URL Construction Tests
    # -------------------------------------------------------------------------
    def test_is_loopback_url(self):
        self.assertTrue(is_loopback_url("http://localhost:8000"))
        self.assertTrue(is_loopback_url("http://127.0.0.1:5173"))
        self.assertTrue(is_loopback_url("http://127.0.0.2:3000"))
        self.assertTrue(is_loopback_url("http://[::1]:5173/app"))
        self.assertTrue(is_loopback_url("https://127.0.0.1:8000/"))

        self.assertFalse(is_loopback_url("http://example.com"))
        self.assertFalse(is_loopback_url("http://192.168.1.5:8000"))
        self.assertFalse(is_loopback_url("ftp://localhost"))
        self.assertFalse(is_loopback_url(""))
        self.assertFalse(is_loopback_url(None))

    def test_build_viewer_url_preserves_path_params_fragment_and_encodes_id(self):
        # 1. Base URL with path, other params, and fragment
        base_1 = "http://127.0.0.1:5173/viewer?theme=dark#overview"
        url_1 = build_viewer_url(base_1, "ana_123")
        self.assertEqual(
            url_1,
            "http://127.0.0.1:5173/viewer?theme=dark&analysis_id=ana_123#overview",
        )

        # 2. Replacing existing analysis_id
        base_2 = "http://localhost:5173/?analysis_id=old_id&mode=fast"
        url_2 = build_viewer_url(base_2, "ana_new")
        self.assertEqual(url_2, "http://localhost:5173/?mode=fast&analysis_id=ana_new")

        # 3. Safe URL encoding of analysis ID with special characters
        base_3 = "http://127.0.0.1:5173"
        url_3 = build_viewer_url(base_3, "ana_test/sub&id=1")
        self.assertEqual(
            url_3, "http://127.0.0.1:5173?analysis_id=ana_test%2Fsub%26id%3D1"
        )

    # -------------------------------------------------------------------------
    # 4. Background Worker, Terminal States, Timeouts & Browser Launch Tests
    # -------------------------------------------------------------------------
    @patch("webbrowser.open")
    @patch("urllib.request.urlopen")
    def test_worker_submission_success(self, mock_urlopen, mock_browser):
        mock_browser.return_value = True
        submit_resp = MagicMock()
        submit_resp.read.return_value = json.dumps(
            {
                "analysis_id": "ana_abc123",
                "state": "running",
                "terminal": False,
            }
        ).encode("utf-8")
        mock_urlopen.return_value = MagicMock(
            __enter__=MagicMock(return_value=submit_resp)
        )

        evt_queue = queue.Queue()
        worker = CodeStructAnalysisWorker(
            "root_a",
            "pkg/sub",
            backend_url="http://127.0.0.1:8000",
            frontend_url="http://127.0.0.1:5173",
            event_queue=evt_queue,
            timeout_seconds=5.0,
        )
        worker.run()

        event_type, payload = evt_queue.get_nowait()
        self.assertEqual(event_type, "SUCCESS")
        aid, vurl, launched = payload
        self.assertEqual(aid, "ana_abc123")
        self.assertEqual(vurl, "http://127.0.0.1:5173?analysis_id=ana_abc123")
        self.assertTrue(launched)
        mock_browser.assert_called_once_with(
            "http://127.0.0.1:5173?analysis_id=ana_abc123"
        )

    @patch("webbrowser.open")
    @patch("urllib.request.urlopen")
    def test_worker_browser_launch_failure_handling(self, mock_urlopen, mock_browser):
        # Browser launch fails (returns False)
        mock_browser.return_value = False
        submit_resp = MagicMock()
        submit_resp.read.return_value = json.dumps(
            {
                "analysis_id": "ana_abc123",
                "state": "queued",
            }
        ).encode("utf-8")
        mock_urlopen.return_value = MagicMock(
            __enter__=MagicMock(return_value=submit_resp)
        )

        evt_queue = queue.Queue()
        worker = CodeStructAnalysisWorker(
            "root_a",
            ".",
            event_queue=evt_queue,
        )
        worker.run()

        event_type, payload = evt_queue.get_nowait()
        self.assertEqual(event_type, "SUCCESS")
        aid, vurl, launched = payload
        self.assertEqual(aid, "ana_abc123")
        self.assertFalse(launched)  # Accurately records browser launch failure

    @patch("urllib.request.urlopen")
    def test_worker_terminal_failed_state(self, mock_urlopen):
        submit_resp = MagicMock()
        submit_resp.read.return_value = json.dumps(
            {
                "analysis_id": "ana_fail",
                "state": "failed",
            }
        ).encode("utf-8")
        mock_urlopen.return_value = MagicMock(
            __enter__=MagicMock(return_value=submit_resp)
        )

        evt_queue = queue.Queue()
        worker = CodeStructAnalysisWorker(
            "root_a",
            ".",
            event_queue=evt_queue,
        )
        worker.run()

        event_type, payload = evt_queue.get_nowait()
        self.assertEqual(event_type, "ERROR")
        self.assertIn(
            "Analysis terminated immediately with state 'failed'", str(payload)
        )

    @patch("urllib.request.urlopen")
    def test_worker_malformed_response_missing_analysis_id(self, mock_urlopen):
        submit_resp = MagicMock()
        submit_resp.read.return_value = json.dumps(
            {
                "state": "queued",
            }
        ).encode("utf-8")
        mock_urlopen.return_value = MagicMock(
            __enter__=MagicMock(return_value=submit_resp)
        )

        evt_queue = queue.Queue()
        worker = CodeStructAnalysisWorker(
            "root_a",
            ".",
            event_queue=evt_queue,
        )
        worker.run()

        event_type, payload = evt_queue.get_nowait()
        self.assertEqual(event_type, "ERROR")
        self.assertIn("Server response missing 'analysis_id'", str(payload))

    # -------------------------------------------------------------------------
    # 5. Constrained Autospec Mocking & Thonny Status API Regression Tests
    # -------------------------------------------------------------------------
    def test_workbench_status_api_contract(self):
        wb_mock = create_autospec(Workbench, instance=True)

        # Verify Workbench contract: set_status_message exists, set_status does NOT
        self.assertTrue(hasattr(wb_mock, "set_status_message"))
        self.assertFalse(hasattr(wb_mock, "set_status"))

        # Verify _set_status_message calls the verified set_status_message API
        cs._set_status_message(wb_mock, "Test status message")
        wb_mock.set_status_message.assert_called_once_with("Test status message")

    def test_get_unsaved_project_files_with_constrained_mocks(self):
        file_in_proj = self.root_a / "main.py"
        file_in_proj.write_text("print('test')", encoding="utf-8")

        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock

        editor_1 = create_autospec(Editor, instance=True)
        editor_1.is_modified.return_value = True
        editor_1.is_remote.return_value = False
        editor_1.get_target_path.return_value = str(file_in_proj)

        editor_unmodified = create_autospec(Editor, instance=True)
        editor_unmodified.is_modified.return_value = False
        editor_unmodified.is_remote.return_value = False
        editor_unmodified.get_target_path.return_value = str(self.root_a / "other.py")

        editor_remote = create_autospec(Editor, instance=True)
        editor_remote.is_modified.return_value = True
        editor_remote.is_remote.return_value = True
        editor_remote.get_target_path.return_value = "/remote/device/main.py"

        notebook_mock.get_all_editors.return_value = [
            editor_1,
            editor_unmodified,
            editor_remote,
        ]

        with patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock):
            modified = get_unsaved_project_files(self.root_a)
            self.assertEqual(len(modified), 1)
            self.assertEqual(modified[0], str(file_in_proj.resolve()))

    # -------------------------------------------------------------------------
    # 6. Operation Lifecycle, Concurrency, Setup Recovery & Shutdown Tests
    # -------------------------------------------------------------------------
    def test_duplicate_click_suppression(self):
        cs._active_operation = "root_a:."
        wb_mock = create_autospec(Workbench, instance=True)

        with patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock):
            analyze_current_project()
            wb_mock.set_status_message.assert_called_with(
                "CodeStruct: Operation already in progress."
            )

    def test_setup_failure_restores_active_operation_state(self):
        wb_mock = create_autospec(Workbench, instance=True)
        wb_mock.get_editor_notebook.return_value = None

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch("tkinter.messagebox.showinfo"),
        ):
            analyze_current_project()
            self.assertIsNone(cs._active_operation)

        # Exception during setup recovers state
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        notebook_mock.get_current_editor.side_effect = RuntimeError("Editor crash")

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch("tkinter.messagebox.showerror"),
        ):
            analyze_current_project()
            self.assertIsNone(cs._active_operation)

    # -------------------------------------------------------------------------
    # 7. Active Editor Validation Tests (No editor, remote, untitled, modified, etc.)
    # -------------------------------------------------------------------------
    def test_analyze_no_active_editor(self):
        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        notebook_mock.get_current_editor.return_value = None

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch("tkinter.messagebox.showinfo") as mock_showinfo,
        ):
            analyze_current_project()
            mock_showinfo.assert_called_once()
            self.assertIn(
                "No Python file is currently open", mock_showinfo.call_args[0][1]
            )
            self.assertIsNone(cs._active_operation)

    def test_analyze_remote_editor_rejected(self):
        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        editor = create_autospec(Editor, instance=True)
        editor.is_remote.return_value = True
        notebook_mock.get_current_editor.return_value = editor

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch("tkinter.messagebox.showinfo") as mock_showinfo,
        ):
            analyze_current_project()
            mock_showinfo.assert_called_once()
            self.assertIn("Remote File Not Supported", mock_showinfo.call_args[0][0])
            self.assertIsNone(cs._active_operation)

    def test_analyze_untitled_editor_rejected(self):
        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        editor = create_autospec(Editor, instance=True)
        editor.is_remote.return_value = False
        editor.is_untitled.return_value = True
        editor.get_target_path.return_value = None
        notebook_mock.get_current_editor.return_value = editor

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch("tkinter.messagebox.showinfo") as mock_showinfo,
        ):
            analyze_current_project()
            mock_showinfo.assert_called_once()
            self.assertIn(
                "Please save the file before analyzing", mock_showinfo.call_args[0][1]
            )
            self.assertIsNone(cs._active_operation)

    def test_analyze_modified_editor_rejected(self):
        py_file = self.root_a / "active.py"
        py_file.write_text("x = 1\n", encoding="utf-8")

        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        editor = create_autospec(Editor, instance=True)
        editor.is_remote.return_value = False
        editor.is_untitled.return_value = False
        editor.is_modified.return_value = True
        editor.get_target_path.return_value = str(py_file)
        notebook_mock.get_current_editor.return_value = editor

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch("tkinter.messagebox.showinfo") as mock_showinfo,
        ):
            analyze_current_project()
            mock_showinfo.assert_called_once()
            self.assertIn(
                "Please save your changes before analyzing",
                mock_showinfo.call_args[0][1],
            )
            self.assertIsNone(cs._active_operation)

    def test_analyze_unsupported_extension_rejected(self):
        txt_file = self.root_a / "notes.txt"
        txt_file.write_text("Hello", encoding="utf-8")

        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        editor = create_autospec(Editor, instance=True)
        editor.is_remote.return_value = False
        editor.is_untitled.return_value = False
        editor.is_modified.return_value = False
        editor.get_target_path.return_value = str(txt_file)
        notebook_mock.get_current_editor.return_value = editor

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch("tkinter.messagebox.showinfo") as mock_showinfo,
        ):
            analyze_current_project()
            mock_showinfo.assert_called_once()
            self.assertIn(
                "Only Python files (.py or .pyw) can be analyzed",
                mock_showinfo.call_args[0][1],
            )
            self.assertIsNone(cs._active_operation)

    def test_analyze_nonexistent_file_rejected(self):
        missing_file = self.root_a / "does_not_exist.py"

        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        editor = create_autospec(Editor, instance=True)
        editor.is_remote.return_value = False
        editor.is_untitled.return_value = False
        editor.is_modified.return_value = False
        editor.get_target_path.return_value = str(missing_file)
        notebook_mock.get_current_editor.return_value = editor

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch("tkinter.messagebox.showerror") as mock_showerror,
        ):
            analyze_current_project()
            mock_showerror.assert_called_once()
            self.assertIn("cannot be accessed on disk", mock_showerror.call_args[0][1])
            self.assertIsNone(cs._active_operation)

    def test_analyze_symlink_file_rejected(self):
        real_file = self.root_a / "real_script.py"
        real_file.write_text("a = 1", encoding="utf-8")

        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        editor = create_autospec(Editor, instance=True)
        editor.is_remote.return_value = False
        editor.is_untitled.return_value = False
        editor.is_modified.return_value = False
        editor.get_target_path.return_value = str(real_file)
        notebook_mock.get_current_editor.return_value = editor

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch.object(Path, "is_symlink", return_value=True),
            patch("tkinter.messagebox.showerror") as mock_showerror,
        ):
            analyze_current_project()
            mock_showerror.assert_called_once()
            self.assertIn("Symlinks Not Supported", mock_showerror.call_args[0][0])
            self.assertIsNone(cs._active_operation)

    def test_analyze_non_loopback_backend_url_rejected(self):
        py_file = self.root_a / "valid.py"
        py_file.write_text("x = 42\n", encoding="utf-8")

        wb_mock = create_autospec(Workbench, instance=True)
        notebook_mock = create_autospec(EditorNotebook, instance=True)
        wb_mock.get_editor_notebook.return_value = notebook_mock
        editor = create_autospec(Editor, instance=True)
        editor.is_remote.return_value = False
        editor.is_untitled.return_value = False
        editor.is_modified.return_value = False
        editor.get_target_path.return_value = str(py_file)
        notebook_mock.get_current_editor.return_value = editor

        with (
            patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock),
            patch.dict(os.environ, {"CODESTRUCT_BACKEND_URL": "http://evil.com:8000"}),
            patch("tkinter.messagebox.showerror") as mock_showerror,
        ):
            analyze_current_project()
            mock_showerror.assert_called_once()
            self.assertIn(
                "Security Configuration Error", mock_showerror.call_args[0][0]
            )
            self.assertIsNone(cs._active_operation)

    def test_worker_file_registration_and_submission(self):
        py_file = self.root_a / "module_z.py"
        py_file.write_text("print('hello')", encoding="utf-8")

        reg_resp = MagicMock()
        reg_resp.read.return_value = json.dumps(
            {
                "root_id": "editor_12345678",
                "relative_path": "module_z.py",
            }
        ).encode("utf-8")

        sub_resp = MagicMock()
        sub_resp.read.return_value = json.dumps(
            {
                "analysis_id": "ana_editor_99",
                "state": "running",
            }
        ).encode("utf-8")

        mock_responses = [reg_resp, sub_resp]

        def fake_urlopen(req, timeout=10.0):
            cm = MagicMock()
            cm.__enter__.return_value = mock_responses.pop(0)
            return cm

        evt_queue = queue.Queue()
        worker = CodeStructAnalysisWorker(
            file_path=str(py_file),
            event_queue=evt_queue,
        )

        with (
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
            patch("webbrowser.open", return_value=True),
        ):
            worker.run()

        event_type, payload = evt_queue.get_nowait()
        self.assertEqual(event_type, "SUCCESS")
        aid, vurl, launched = payload
        self.assertEqual(aid, "ana_editor_99")
        self.assertEqual(vurl, "http://127.0.0.1:5173?analysis_id=ana_editor_99")
        self.assertTrue(launched)

    @patch("webbrowser.open")
    @patch("urllib.request.urlopen")
    def test_active_file_registration_two_step_contract_and_stale_param_prevention(
        self, mock_urlopen, mock_browser
    ):
        mock_browser.return_value = True
        py_file = self.root_a / "selected_active.py"
        py_file.write_text("def active_func(): pass\n", encoding="utf-8")

        captured_requests: list[urllib.request.Request] = []

        def fake_urlopen(req, timeout=10.0):
            captured_requests.append(req)
            resp = MagicMock()
            if req.full_url.endswith("/api/v1/editor/selection"):
                resp.read.return_value = json.dumps(
                    {
                        "api_version": "v1",
                        "request_id": "req_1",
                        "capability_id": "cap_tested_capability_xyz",
                        "root_id": "cap_tested_capability_xyz",
                        "relative_path": "selected_active.py",
                        "display_name": "selected_active.py",
                    }
                ).encode("utf-8")
            elif req.full_url.endswith("/api/v1/analyses"):
                resp.read.return_value = json.dumps(
                    {
                        "analysis_id": "ana_tested_456",
                        "state": "running",
                    }
                ).encode("utf-8")
            cm = MagicMock()
            cm.__enter__.return_value = resp
            return cm

        mock_urlopen.side_effect = fake_urlopen

        evt_queue = queue.Queue()
        # Pass stale constructor parameters to ensure they are ignored when file_path is supplied
        worker = CodeStructAnalysisWorker(
            root_id="stale_demo_root",
            relative_path="stale_parent_path",
            file_path=str(py_file),
            backend_url="http://127.0.0.1:8000",
            frontend_url="http://127.0.0.1:5173",
            event_queue=evt_queue,
        )
        worker.run()

        # Verify exactly two requests were sent in order
        self.assertEqual(len(captured_requests), 2)

        # 1. First request: /api/v1/editor/selection
        req1 = captured_requests[0]
        self.assertTrue(req1.full_url.endswith("/api/v1/editor/selection"))
        self.assertEqual(req1.get_method(), "POST")
        body1 = json.loads(req1.data.decode("utf-8"))
        self.assertEqual(body1, {"file_path": str(py_file)})
        self.assertNotIn("stale_demo_root", str(body1))
        self.assertNotIn("stale_parent_path", str(body1))

        # 2. Second request: /api/v1/analyses using capability and relative_path from first request
        req2 = captured_requests[1]
        self.assertTrue(req2.full_url.endswith("/api/v1/analyses"))
        self.assertEqual(req2.get_method(), "POST")
        body2 = json.loads(req2.data.decode("utf-8"))
        self.assertIn("project", body2)
        project_field = body2["project"]
        self.assertEqual(project_field["root_id"], "cap_tested_capability_xyz")
        self.assertEqual(
            project_field.get("capability_id"), "cap_tested_capability_xyz"
        )
        self.assertEqual(project_field["relative_path"], "selected_active.py")
        self.assertNotIn("stale_demo_root", str(body2))
        self.assertNotIn("stale_parent_path", str(body2))

        # 3. Viewer was opened with exact analysis_id and session_token
        mock_browser.assert_called_once_with(
            "http://127.0.0.1:5173?analysis_id=ana_tested_456&session_token=cap_tested_capability_xyz"
        )
        event_type, payload = evt_queue.get_nowait()
        self.assertEqual(event_type, "SUCCESS")
        self.assertEqual(payload[0], "ana_tested_456")

    @patch("webbrowser.open")
    @patch("urllib.request.urlopen")
    def test_viewer_launch_preserves_url_components_and_failure_guards(
        self, mock_urlopen, mock_browser
    ):
        mock_browser.return_value = True
        py_file = self.root_a / "target_view.py"
        py_file.write_text("x = 1\n", encoding="utf-8")

        # Test A: Complex base URL with path, query params, fragment, and special chars in analysis_id
        def fake_success(req, timeout=10.0):
            resp = MagicMock()
            if req.full_url.endswith("/api/v1/editor/selection"):
                resp.read.return_value = json.dumps(
                    {"capability_id": "cap_ok", "relative_path": "target_view.py"}
                ).encode("utf-8")
            else:
                resp.read.return_value = json.dumps(
                    {"analysis_id": "ana_custom/123&test=1", "state": "queued"}
                ).encode("utf-8")
            cm = MagicMock()
            cm.__enter__.return_value = resp
            return cm

        mock_urlopen.side_effect = fake_success
        evt_queue = queue.Queue()
        worker = CodeStructAnalysisWorker(
            file_path=str(py_file),
            frontend_url="http://127.0.0.1:5173/viewer?theme=dark&tab=classes#overview",
            event_queue=evt_queue,
        )
        worker.run()
        mock_browser.assert_called_once_with(
            "http://127.0.0.1:5173/viewer?theme=dark&tab=classes&analysis_id=ana_custom%2F123%26test%3D1&session_token=cap_ok#overview"
        )
        mock_browser.reset_mock()

        # Test B: Registration HTTPError -> Browser must NOT be opened
        def fake_reg_err(req, timeout=10.0):
            fp = MagicMock()
            fp.read.return_value = (
                b'{"error": {"code": "PROJECT_UNAUTHORIZED", "message": "Denied"}}'
            )
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, fp)

        mock_urlopen.side_effect = fake_reg_err
        q_err = queue.Queue()
        worker_err = CodeStructAnalysisWorker(file_path=str(py_file), event_queue=q_err)
        worker_err.run()
        mock_browser.assert_not_called()
        evt_type, payload = q_err.get_nowait()
        self.assertEqual(evt_type, "ERROR")
        self.assertIn("Editor file registration rejected: Denied", payload)

        # Test C: Analysis submission HTTPError -> Browser must NOT be opened
        def fake_sub_err(req, timeout=10.0):
            if req.full_url.endswith("/api/v1/editor/selection"):
                resp = MagicMock()
                resp.read.return_value = json.dumps(
                    {"capability_id": "cap_ok", "relative_path": "target_view.py"}
                ).encode("utf-8")
                cm = MagicMock()
                cm.__enter__.return_value = resp
                return cm
            fp = MagicMock()
            fp.read.return_value = (
                b'{"error": {"code": "INTERNAL_ERROR", "message": "Crash"}}'
            )
            raise urllib.error.HTTPError(
                req.full_url, 500, "Internal Server Error", {}, fp
            )

        mock_urlopen.side_effect = fake_sub_err
        q_sub_err = queue.Queue()
        worker_sub_err = CodeStructAnalysisWorker(
            file_path=str(py_file), event_queue=q_sub_err
        )
        worker_sub_err.run()
        mock_browser.assert_not_called()
        evt_type, payload = q_sub_err.get_nowait()
        self.assertEqual(evt_type, "ERROR")
        self.assertIn("Analysis submission rejected: Crash", payload)

        # Test D: Missing analysis_id in response -> Browser must NOT be opened
        def fake_missing_id(req, timeout=10.0):
            resp = MagicMock()
            if req.full_url.endswith("/api/v1/editor/selection"):
                resp.read.return_value = json.dumps(
                    {"capability_id": "cap_ok", "relative_path": "target_view.py"}
                ).encode("utf-8")
            else:
                resp.read.return_value = json.dumps({"state": "queued"}).encode("utf-8")
            cm = MagicMock()
            cm.__enter__.return_value = resp
            return cm

        mock_urlopen.side_effect = fake_missing_id
        q_no_id = queue.Queue()
        worker_no_id = CodeStructAnalysisWorker(
            file_path=str(py_file), event_queue=q_no_id
        )
        worker_no_id.run()
        mock_browser.assert_not_called()
        evt_type, payload = q_no_id.get_nowait()
        self.assertEqual(evt_type, "ERROR")
        self.assertIn("missing 'analysis_id'", payload)

    def test_child_destroy_event_does_not_trigger_shutdown(self):
        wb_mock = create_autospec(Workbench, instance=True)
        child_dialog = MagicMock()  # Child dialog widget

        event = MagicMock()
        event.widget = child_dialog

        with patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock):
            on_workbench_shutdown(event)
            # Plugin must NOT shut down because event was for a child widget
            self.assertFalse(cs._is_shutting_down)

    def test_workbench_shutdown_cancels_worker_and_suppresses_ui(self):
        wb_mock = create_autospec(Workbench, instance=True)
        mock_worker = MagicMock()
        cs._active_worker = mock_worker
        cs._active_operation = "root_a:."

        event = MagicMock()
        event.widget = wb_mock

        with patch("thonnycontrib.codestruct.get_workbench", return_value=wb_mock):
            on_workbench_shutdown(event)

            self.assertTrue(cs._is_shutting_down)
            mock_worker.cancel.assert_called_once()
            self.assertIsNone(cs._active_operation)
            self.assertIsNone(cs._active_worker)


class TestPluginNavigation(unittest.TestCase):
    def setUp(self):
        cs._nav_poll_active = False
        cs._nav_session_token = None
        cs._nav_registered_file = None
        cs._nav_registered_file_resolved = None
        cs._nav_poll_generation = 0
        cs._nav_poll_in_flight = False
        cs._nav_queue = queue.Queue()

    def tearDown(self):
        cs._is_shutting_down = False
        cs._nav_poll_active = False
        cs._nav_session_token = None
        cs._nav_registered_file = None
        cs._nav_registered_file_resolved = None
        cs._nav_poll_generation = 0
        cs._nav_poll_in_flight = False
        cs._nav_queue = queue.Queue()

    def test_build_viewer_url_with_session_token(self):
        url = build_viewer_url(
            "http://127.0.0.1:5173", "ana_test", session_token="cap_token_123"
        )
        self.assertIn("analysis_id=ana_test", url)
        self.assertIn("session_token=cap_token_123", url)

    def test_worker_includes_session_token_in_viewer_url(self):
        worker = CodeStructAnalysisWorker(
            file_path="sample.py",
            backend_url="http://127.0.0.1:8000",
            frontend_url="http://127.0.0.1:5173",
            event_queue=queue.Queue(),
        )
        worker.root_id = "cap_session_test_999"
        session_token = (
            worker.root_id
            if worker.root_id and worker.root_id.startswith("cap_")
            else None
        )
        viewer_url = build_viewer_url(worker.frontend_url, "ana_123", session_token)
        self.assertIn("analysis_id=ana_123", viewer_url)
        self.assertIn("session_token=cap_session_test_999", viewer_url)

    def test_two_roots_with_same_filename_opens_only_session_bound_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root1 = Path(temp_dir) / "root1"
            root2 = Path(temp_dir) / "root2"
            root1.mkdir()
            root2.mkdir()
            file1 = root1 / "worker.py"
            file2 = root2 / "worker.py"
            file1.write_text("x = 1", encoding="utf-8")
            file2.write_text("x = 2", encoding="utf-8")

            # Session is bound specifically to file2 in root2
            sess_token = "cap_session_root2"
            cs._nav_session_token = sess_token
            cs._nav_registered_file = file2.resolve()

            wb = MagicMock()
            editor_notebook = MagicMock()
            wb.get_editor_notebook.return_value = editor_notebook

            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token=sess_token,
                    command_id="nav_1",
                    relative_path="worker.py",
                    line=10,
                    column=3,
                )

                # Verified: Opened root2/worker.py, NEVER root1/worker.py
                editor_notebook.show_file_at_line.assert_called_once_with(
                    str(file2.resolve()), 10, 2
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000", sess_token, "nav_1", status="delivered"
                )

    def test_execute_navigate_exact_file_and_cursor_offset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "app.py"
            f.write_text("print('hello')", encoding="utf-8")

            sess_token = "cap_test_cursor"
            cs._nav_session_token = sess_token
            cs._nav_registered_file = f.resolve()

            wb = MagicMock()
            editor_notebook = MagicMock()
            wb.get_editor_notebook.return_value = editor_notebook

            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                # 1-indexed column 5 should map to 0-indexed col_offset 4
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token=sess_token,
                    command_id="nav_2",
                    relative_path="app.py",
                    line=42,
                    column=5,
                )
                editor_notebook.show_file_at_line.assert_called_once_with(
                    str(f.resolve()), 42, 4
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000", sess_token, "nav_2", status="delivered"
                )

    def test_execute_navigate_fallback_to_select_line(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "app.py"
            f.write_text("print('hello')", encoding="utf-8")

            sess_token = "cap_fallback"
            cs._nav_session_token = sess_token
            cs._nav_registered_file = f.resolve()

            wb = MagicMock()
            editor_notebook = MagicMock(spec=["show_file"])  # no show_file_at_line
            editor = MagicMock()
            editor_notebook.show_file.return_value = editor
            wb.get_editor_notebook.return_value = editor_notebook

            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token=sess_token,
                    command_id="nav_3",
                    relative_path="app.py",
                    line=7,
                    column=1,
                )
                editor_notebook.show_file.assert_called_once_with(str(f.resolve()))
                editor.select_line.assert_called_once_with(7, 0)
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000", sess_token, "nav_3", status="delivered"
                )

    def test_execute_navigate_session_mismatch_reports_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "app.py"
            f.write_text("print('hello')", encoding="utf-8")

            cs._nav_session_token = "cap_session_expected"
            cs._nav_registered_file = f.resolve()

            wb = MagicMock()
            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token="cap_session_wrong",
                    command_id="nav_bad_sess",
                    relative_path="app.py",
                    line=1,
                    column=1,
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000",
                    "cap_session_wrong",
                    "nav_bad_sess",
                    status="failed",
                    reason="session_mismatch",
                )

    def test_execute_navigate_scope_mismatch_reports_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "app.py"
            f.write_text("print('hello')", encoding="utf-8")

            cs._nav_session_token = "cap_scope_test"
            cs._nav_registered_file = f.resolve()

            wb = MagicMock()
            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token="cap_scope_test",
                    command_id="nav_scope_bad",
                    relative_path="other_file.py",
                    line=1,
                    column=1,
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000",
                    "cap_scope_test",
                    "nav_scope_bad",
                    status="failed",
                    reason="scope_mismatch",
                )

    def test_execute_navigate_traversal_reports_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "app.py"
            f.write_text("print('hello')", encoding="utf-8")

            cs._nav_session_token = "cap_trav"
            cs._nav_registered_file = f.resolve()

            wb = MagicMock()
            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token="cap_trav",
                    command_id="nav_trav",
                    relative_path="../app.py",
                    line=1,
                    column=1,
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000",
                    "cap_trav",
                    "nav_trav",
                    status="failed",
                    reason="traversal_rejected",
                )

    def test_execute_navigate_missing_file_reports_failure(self):
        nonexistent = Path("C:/definitely_missing/file_does_not_exist.py")
        cs._nav_session_token = "cap_missing"
        cs._nav_registered_file = nonexistent

        wb = MagicMock()
        with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
            cs._execute_navigate(
                wb=wb,
                backend_url="http://127.0.0.1:8000",
                session_token="cap_missing",
                command_id="nav_missing",
                relative_path="file_does_not_exist.py",
                line=1,
                column=1,
            )
            mock_ack.assert_called_once_with(
                "http://127.0.0.1:8000",
                "cap_missing",
                "nav_missing",
                status="failed",
                reason="file_inaccessible",
            )

    def test_poll_navigate_stops_on_expired_session_403(self):
        wb = MagicMock()
        wb.winfo_exists.return_value = True
        cs._nav_poll_active = True
        cs._nav_session_token = "cap_expired"
        cs._nav_poll_generation = 1

        err = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/v1/editor/navigate/pending",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None,
        )

        with patch("urllib.request.urlopen", side_effect=err):
            cs._poll_navigate(wb, "http://127.0.0.1:8000", "cap_expired", generation=1)
            time.sleep(0.1)
            # Main-thread poll cycle drains the STOP message
            cs._poll_navigate(wb, "http://127.0.0.1:8000", "cap_expired", generation=1)

        self.assertFalse(cs._nav_poll_active, "Poller must stop on HTTP 403")

    def test_start_navigation_polling_increments_generation_and_switches_session(self):
        wb = MagicMock()
        cs._nav_session_token = "cap_session_a"
        cs._nav_poll_active = False
        cs._nav_poll_generation = 0

        with patch("thonnycontrib.codestruct._poll_navigate") as mock_poll:
            cs._start_navigation_polling(wb, "http://127.0.0.1:8000")
            self.assertEqual(cs._nav_poll_generation, 1)
            self.assertTrue(cs._nav_poll_active)
            mock_poll.assert_called_once_with(
                wb, "http://127.0.0.1:8000", "cap_session_a", 1
            )

        # Now switch to session B
        cs._nav_session_token = "cap_session_b"
        with patch("thonnycontrib.codestruct._poll_navigate") as mock_poll_b:
            cs._start_navigation_polling(wb, "http://127.0.0.1:8000")
            self.assertEqual(cs._nav_poll_generation, 2)
            self.assertTrue(cs._nav_poll_active)
            mock_poll_b.assert_called_once_with(
                wb, "http://127.0.0.1:8000", "cap_session_b", 2
            )

    def test_stale_poll_cycle_discarded_after_generation_switch(self):
        wb = MagicMock()
        wb.winfo_exists.return_value = True
        cs._nav_session_token = "cap_session_b"
        cs._nav_poll_generation = 2
        cs._nav_poll_active = True

        # Call with stale generation 1
        with patch("urllib.request.urlopen") as mock_urlopen:
            cs._poll_navigate(
                wb, "http://127.0.0.1:8000", "cap_session_a", generation=1
            )
            time.sleep(0.05)
            mock_urlopen.assert_not_called()

    def test_execute_navigate_stale_generation_rejected(self):
        cs._nav_session_token = "cap_stale_test"
        cs._nav_poll_generation = 2
        cs._nav_registered_file = Path("C:/test/app.py")

        wb = MagicMock()
        with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
            cs._execute_navigate(
                wb=wb,
                backend_url="http://127.0.0.1:8000",
                session_token="cap_stale_test",
                command_id="nav_stale",
                relative_path="app.py",
                line=1,
                column=1,
                generation=1,
            )
            mock_ack.assert_called_once_with(
                "http://127.0.0.1:8000",
                "cap_stale_test",
                "nav_stale",
                status="failed",
                reason="stale_session",
            )

    def test_execute_navigate_path_identity_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_a = Path(temp_dir) / "app.py"
            file_a.write_text("print('hello a')", encoding="utf-8")
            file_b = Path(temp_dir) / "other.py"
            file_b.write_text("print('hello b')", encoding="utf-8")

            cs._nav_session_token = "cap_identity"
            cs._nav_poll_generation = 1
            cs._nav_registered_file = file_a
            # Simulate a swap where registered file resolved is different
            cs._nav_registered_file_resolved = file_b.resolve()

            wb = MagicMock()
            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token="cap_identity",
                    command_id="nav_ident",
                    relative_path="app.py",
                    line=1,
                    column=1,
                    generation=1,
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000",
                    "cap_identity",
                    "nav_ident",
                    status="failed",
                    reason="path_identity_mismatch",
                )

    def test_execute_navigate_pre_resolve_link_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_f = Path(temp_dir) / "target.py"
            target_f.write_text("print('target')", encoding="utf-8")
            link_f = Path(temp_dir) / "link.py"
            try:
                os.symlink(target_f, link_f)
            except (OSError, NotImplementedError):
                self.skipTest(
                    "Symlink creation not supported on this platform/permissions"
                )

            cs._nav_session_token = "cap_link"
            cs._nav_poll_generation = 1
            cs._nav_registered_file = link_f
            cs._nav_registered_file_resolved = target_f.resolve()

            wb = MagicMock()
            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token="cap_link",
                    command_id="nav_link",
                    relative_path="link.py",
                    line=1,
                    column=1,
                    generation=1,
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000",
                    "cap_link",
                    "nav_link",
                    status="failed",
                    reason="symlink_rejected",
                )

    def test_execute_navigate_cursor_unavailable_reports_failed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "app.py"
            f.write_text("print('hello')", encoding="utf-8")

            cs._nav_session_token = "cap_cursor"
            cs._nav_poll_generation = 1
            cs._nav_registered_file = f
            cs._nav_registered_file_resolved = f.resolve()

            # Workbench with open_file only (no cursor placement API)
            wb = MagicMock(spec=["open_file", "set_status_message", "winfo_exists"])
            wb.open_file.return_value = None

            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token="cap_cursor",
                    command_id="nav_cursor",
                    relative_path="app.py",
                    line=5,
                    column=3,
                    generation=1,
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000",
                    "cap_cursor",
                    "nav_cursor",
                    status="failed",
                    reason="cursor_unavailable",
                )

    def test_execute_navigate_exception_reports_safe_reason(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "app.py"
            f.write_text("print('hello')", encoding="utf-8")

            cs._nav_session_token = "cap_err"
            cs._nav_poll_generation = 1
            cs._nav_registered_file = f
            cs._nav_registered_file_resolved = f.resolve()

            wb = MagicMock()
            wb.get_editor_notebook.side_effect = RuntimeError(
                "Internal widget failure in C:/secret/path"
            )

            with patch("thonnycontrib.codestruct._acknowledge_navigate") as mock_ack:
                cs._execute_navigate(
                    wb=wb,
                    backend_url="http://127.0.0.1:8000",
                    session_token="cap_err",
                    command_id="nav_err",
                    relative_path="app.py",
                    line=1,
                    column=1,
                    generation=1,
                )
                mock_ack.assert_called_once_with(
                    "http://127.0.0.1:8000",
                    "cap_err",
                    "nav_err",
                    status="failed",
                    reason="navigation_error",
                )

    def test_poll_navigate_stale_stop_ignored_and_new_session_remains_active(self):
        wb = MagicMock()
        wb.winfo_exists.return_value = True

        cs._is_shutting_down = False
        cs._nav_session_token = "cap_new_session"
        cs._nav_poll_generation = 2
        cs._nav_poll_active = True
        cs._nav_poll_in_flight = True

        # Queue a STOP from generation 1 (e.g. old session 403 or URLError)
        cs._nav_queue = queue.Queue()
        cs._nav_queue.put(("STOP", 1))

        cs._poll_navigate(wb, "http://127.0.0.1:8000", "cap_new_session", generation=2)

        self.assertTrue(
            cs._nav_poll_active,
            "New session poller must remain active when encountering a stale STOP from gen 1",
        )

    def test_poll_navigate_stale_navigate_discarded_and_new_session_navigates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_v2 = Path(temp_dir) / "app.py"
            file_v2.write_text("print('version 2')", encoding="utf-8")

            wb = MagicMock()
            wb.winfo_exists.return_value = True

            cs._is_shutting_down = False
            cs._nav_session_token = "cap_session_2"
            cs._nav_poll_generation = 2
            cs._nav_poll_active = True
            cs._nav_registered_file = file_v2
            cs._nav_registered_file_resolved = file_v2.resolve()

            # Enqueue stale NAVIGATE from gen 1 and valid NAVIGATE from gen 2
            cs._nav_queue = queue.Queue()
            cs._nav_queue.put(
                ("NAVIGATE", ("cmd_old", "app.py", 1, 1, 1, "cap_session_1"))
            )
            cs._nav_queue.put(
                ("NAVIGATE", ("cmd_new", "app.py", 1, 1, 2, "cap_session_2"))
            )

            with patch("thonnycontrib.codestruct._execute_navigate") as mock_exec:
                cs._poll_navigate(
                    wb, "http://127.0.0.1:8000", "cap_session_2", generation=2
                )
                # Should only execute the NAVIGATE matching generation 2 and session 2
                mock_exec.assert_called_once_with(
                    wb,
                    "http://127.0.0.1:8000",
                    "cap_session_2",
                    "cmd_new",
                    "app.py",
                    1,
                    1,
                    2,
                )

    def test_in_flight_old_http_error_does_not_disable_new_generation(self):
        wb = MagicMock()
        wb.winfo_exists.return_value = True

        cs._is_shutting_down = False
        cs._nav_session_token = "cap_session_1"
        cs._nav_poll_generation = 1
        cs._nav_poll_active = True
        cs._nav_poll_in_flight = False

        # Simulate in-flight HTTP request for gen 1 raising 403
        err = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/v1/editor/navigate/pending",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None,
        )

        def slow_urlopen(req, *args, **kwargs):
            if cs._nav_poll_generation == 1:
                # While the request is in flight for generation 1, the user initiates session 2!
                cs._nav_session_token = "cap_session_2"
                cs._nav_poll_generation = 2
                cs._nav_poll_active = True
                raise err
            resp_mock = MagicMock()
            resp_mock.read.return_value = b'{"has_command": false}'
            resp_mock.__enter__.return_value = resp_mock
            return resp_mock

        with patch("urllib.request.urlopen", side_effect=slow_urlopen):
            # Gen 1 poller runs and hits error
            cs._poll_navigate(
                wb, "http://127.0.0.1:8000", "cap_session_1", generation=1
            )
            time.sleep(0.1)

            # Gen 2 poller now runs its cycle and drains the queue
            cs._poll_navigate(
                wb, "http://127.0.0.1:8000", "cap_session_2", generation=2
            )

            self.assertTrue(
                cs._nav_poll_active,
                "Poller for generation 2 must stay active despite generation 1 HTTP 403",
            )


if __name__ == "__main__":
    unittest.main()
