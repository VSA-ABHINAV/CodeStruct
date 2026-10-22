"""
CodeStruct integration plugin for Thonny IDE.
Enables analyzing Python projects directly from Thonny and viewing results in CodeStruct.
"""

from __future__ import annotations

import ast
import ipaddress
import json
import logging
import os
import queue
import stat as _stat_module
import tempfile
import threading
import time
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import ttk
from typing import Any, Optional, Tuple

try:
    from thonny import get_workbench as _thonny_get_workbench

    def get_workbench() -> Any:
        try:
            return _thonny_get_workbench()
        except (AssertionError, Exception):
            return None
except ImportError:
    # Allow importing and testing outside of full Thonny runtime
    def get_workbench() -> Any:
        return None


try:
    from thonny.codeview import CodeViewText
    from thonny.editors import Editor
except ImportError:

    class Editor(ttk.Frame):  # type: ignore[no-redef]
        pass

    class CodeViewText:  # type: ignore[no-redef]
        def __init__(self, master: Any) -> None:
            self.master = master


try:
    import tkwry
except ImportError:
    tkwry = None


logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_FRONTEND_URL = "http://127.0.0.1:5173"

# Concurrency and lifecycle state
_active_operation: Optional[str] = None
_active_worker: Optional[CodeStructAnalysisWorker] = None
_is_shutting_down: bool = False
_state_lock = threading.Lock()

# Navigation polling state
# Set to the capability_id after a successful analysis so the poll loop can
# identify which pending navigate command belongs to this Thonny session.
_nav_session_token: Optional[str] = None
_nav_registered_root: Optional[Path] = None
_nav_registered_file: Optional[Path] = None
_nav_registered_file_resolved: Optional[Path] = None
_nav_poll_active: bool = False
_nav_poll_generation: int = 0
_NAV_POLL_INTERVAL_MS: int = 500  # milliseconds between poll requests
_nav_queue: queue.Queue[Tuple[str, Any]] = queue.Queue()
_nav_poll_in_flight: bool = False


def _is_reparse_stat(stat_result: os.stat_result) -> bool:
    flag = getattr(_stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(flag and attributes & flag)


def _is_link_or_reparse(path: Path, stat_result: os.stat_result | None = None) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        return _is_reparse_stat(stat_result or path.lstat())
    except OSError:
        return False


def _has_link_component(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:] if path.anchor else path.parts:
        current = current / part
        try:
            if _is_link_or_reparse(current, current.lstat()):
                return True
        except OSError:
            return False
    return False


class ConfigurationError(Exception):
    """Raised when CodeStruct root mapping or URL configuration is invalid."""

    pass


def _set_status_message(wb: Any, message: str) -> None:
    """Set status message on Thonny Workbench using verified set_status_message API."""
    if wb is None:
        return
    if hasattr(wb, "set_status_message"):
        wb.set_status_message(message)
    elif hasattr(wb, "set_status"):
        wb.set_status(message)
    else:
        logger.info("Thonny status: %s", message)


def is_loopback_url(url: str) -> bool:
    """Validate that the URL host is strictly a loopback address."""
    if not url or not isinstance(url, str):
        return False
    try:
        parts = urllib.parse.urlsplit(url.strip())
        if parts.scheme not in ("http", "https"):
            return False
        hostname = parts.hostname
        if not hostname:
            return False
        hostname = hostname.lower()
        if hostname in ("localhost", "127.0.0.1", "::1"):
            return True
        try:
            ip = ipaddress.ip_address(hostname.strip("[]"))
            return ip.is_loopback
        except ValueError:
            return False
    except Exception:
        return False


def build_viewer_url(
    base_url: str, analysis_id: str, session_token: Optional[str] = None
) -> str:
    """
    Construct viewer URL preserving configured path, query parameters, and fragment,
    while safely adding or replacing the encoded analysis_id parameter and session_token.
    """
    parts = urllib.parse.urlsplit(base_url.strip())
    existing_params = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    # Filter out existing analysis_id and session_token
    filtered_params = [
        (k, v) for k, v in existing_params if k not in ("analysis_id", "session_token")
    ]
    # Append the new analysis_id and optional session_token (safe url encoding handled by urlencode)
    filtered_params.append(("analysis_id", analysis_id))
    if session_token:
        filtered_params.append(("session_token", session_token))
    new_query = urllib.parse.urlencode(filtered_params)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


def build_workbench_viewer_url(
    base_url: str,
    analysis_id: str,
    project_id: str,
    session_token: Optional[str] = None,
) -> str:
    """
    Construct viewer URL for embedded Thonny editor tab workbench.
    Passes embed=thonny, analysis_id, project_id, and optional session_token.
    """
    parts = urllib.parse.urlsplit(base_url.strip())
    existing_params = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    filtered_params = [
        (k, v)
        for k, v in existing_params
        if k not in ("analysis_id", "session_token", "project_id", "embed")
    ]
    filtered_params.append(("embed", "thonny"))
    filtered_params.append(("analysis_id", analysis_id))
    filtered_params.append(("project_id", project_id))
    if session_token:
        filtered_params.append(("session_token", session_token))
    new_query = urllib.parse.urlencode(filtered_params)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


def parse_root_mappings(raw_str: Optional[str] = None) -> dict[str, Path]:
    """
    Parse and validate root mappings from raw configuration or environment.
    Format: 'root_id=absolute_path;root_id2=absolute_path2'

    Raises ConfigurationError if syntax is invalid, paths do not exist,
    or conflicting/ambiguous mappings are detected.
    """
    if raw_str is None:
        raw_str = (
            os.environ.get("CODESTRUCT_ROOT_MAPPINGS")
            or os.environ.get("CODESTRUCT_AUTHORIZED_ROOTS")
            or ""
        )
        if not raw_str:
            wb = get_workbench()
            if wb is not None and hasattr(wb, "get_option"):
                try:
                    raw_str = (
                        wb.get_option("codestruct.root_mappings", default="") or ""
                    )
                except Exception:
                    raw_str = ""

    raw_str = raw_str.strip()
    if not raw_str:
        return {}

    # Split by semicolon or newline
    delimiters = [";", "\n"]
    items = [raw_str]
    for d in delimiters:
        new_items: list[str] = []
        for it in items:
            new_items.extend(it.split(d))
        items = new_items

    root_mappings: dict[str, Path] = {}
    path_to_id: dict[str, str] = {}

    for raw_item in items:
        item = raw_item.strip()
        if not item:
            continue

        if "=" not in item:
            raise ConfigurationError(
                f"Invalid mapping entry '{item}'. Expected format 'root_id=/path/to/project'."
            )

        root_id, path_str = (p.strip() for p in item.split("=", 1))
        if not root_id:
            raise ConfigurationError(f"Missing root_id in mapping '{item}'.")
        if not path_str:
            raise ConfigurationError(f"Missing directory path for root '{root_id}'.")

        try:
            resolved_path = Path(path_str).resolve(strict=True)
        except (OSError, RuntimeError) as err:
            raise ConfigurationError(
                f"Configured directory for root '{root_id}' does not exist or is inaccessible: '{path_str}' ({err})"
            ) from err

        if not resolved_path.is_dir():
            raise ConfigurationError(
                f"Configured path for root '{root_id}' is not a directory: '{path_str}'"
            )

        # Check for conflicting duplicate root_id
        if root_id in root_mappings:
            existing_path = root_mappings[root_id]
            if existing_path != resolved_path:
                raise ConfigurationError(
                    f"Conflicting mapping: root_id '{root_id}' is mapped to distinct paths '{existing_path}' and '{resolved_path}'."
                )

        # Check for conflicting duplicate directory mapped to different root_id
        canonical_str = str(resolved_path)
        if canonical_str in path_to_id and path_to_id[canonical_str] != root_id:
            existing_id = path_to_id[canonical_str]
            raise ConfigurationError(
                f"Conflicting mapping: directory '{canonical_str}' is mapped to multiple root IDs: '{existing_id}' and '{root_id}'."
            )

        root_mappings[root_id] = resolved_path
        path_to_id[canonical_str] = root_id

    return root_mappings


def resolve_local_folder_to_project(
    folder: str | Path, root_mappings: dict[str, Path] | None = None
) -> Tuple[str, str] | None:
    """
    Map a user-selected local folder to (root_id, relative_path).
    Ensures strict path-component containment and selects the most specific (deepest) root.
    Returns None if the folder is outside all configured roots.
    """
    if root_mappings is None:
        root_mappings = parse_root_mappings()

    if not root_mappings:
        return None

    try:
        resolved_folder = Path(folder).resolve(strict=True)
    except (OSError, RuntimeError):
        return None

    if not resolved_folder.is_dir():
        return None

    best_match: Tuple[str, str, int] | None = None

    for root_id, root_path in root_mappings.items():
        try:
            resolved_root = root_path.resolve(strict=True)
        except (OSError, RuntimeError):
            continue

        try:
            rel = resolved_folder.relative_to(resolved_root)
            # Strict path-component containment confirmed
            rel_str = str(rel).replace("\\", "/")
            rel_path = "." if rel_str == "." else rel_str
            depth = len(resolved_root.parts)

            if best_match is None or depth > best_match[2]:
                best_match = (root_id, rel_path, depth)
        except ValueError:
            # Not a subpath
            continue

    if best_match is not None:
        return (best_match[0], best_match[1])

    return None


def get_unsaved_project_files(project_dir: Path) -> list[str]:
    """
    Identify open editor buffers in Thonny that have unsaved changes
    and belong to the target project directory.
    """
    wb = get_workbench()
    if wb is None:
        return []

    editor_notebook = getattr(wb, "get_editor_notebook", lambda: None)()
    if editor_notebook is None or not hasattr(editor_notebook, "get_all_editors"):
        return []

    modified_files: list[str] = []
    try:
        resolved_proj = project_dir.resolve(strict=True)
    except (OSError, RuntimeError):
        return []

    for editor in editor_notebook.get_all_editors():
        if not getattr(editor, "is_modified", lambda: False)():
            continue

        # Do not interpret remote-device filenames as local paths
        if getattr(editor, "is_remote", lambda: False)():
            continue

        target_path = getattr(editor, "get_target_path", lambda: None)()
        if not target_path:
            # Untitled or unassigned editor
            continue

        try:
            resolved_file = Path(target_path).resolve(strict=True)
            resolved_file.relative_to(resolved_proj)
            modified_files.append(str(resolved_file))
        except (ValueError, OSError, RuntimeError):
            continue

    return modified_files


class CodeStructAnalysisWorker:
    """
    Background worker thread executing HTTP analysis submission off the Tk main thread.
    Communicates results via a thread-safe event queue.
    """

    def __init__(
        self,
        root_id: Optional[str] = None,
        relative_path: Optional[str] = None,
        *,
        file_path: Optional[str] = None,
        backend_url: str = DEFAULT_BACKEND_URL,
        frontend_url: str = DEFAULT_FRONTEND_URL,
        event_queue: queue.Queue[Tuple[str, Any]],
        timeout_seconds: float = 10.0,
    ) -> None:
        self.root_id = root_id
        self.relative_path = relative_path
        self.file_path = file_path
        self.backend_url = backend_url.rstrip("/")
        self.frontend_url = frontend_url.rstrip("/")
        self.event_queue = event_queue
        self.timeout_seconds = timeout_seconds
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._cancelled:
                return

            analysis_id, state = self._submit()
            if self._cancelled:
                return

            if not analysis_id:
                self.event_queue.put(
                    ("ERROR", "Analysis submission returned an empty analysis ID.")
                )
                return

            if state in ("failed", "cancelled"):
                self.event_queue.put(
                    ("ERROR", f"Analysis terminated immediately with state '{state}'.")
                )
                return

            session_token = (
                self.root_id
                if self.root_id and self.root_id.startswith("cap_")
                else None
            )
            viewer_url = build_viewer_url(self.frontend_url, analysis_id, session_token)
            browser_launched = False
            try:
                browser_launched = bool(webbrowser.open(viewer_url))
            except Exception as b_err:
                logger.warning("Failed to open default web browser: %s", b_err)
                browser_launched = False

            if not self._cancelled:
                self.event_queue.put(
                    ("SUCCESS", (analysis_id, viewer_url, browser_launched))
                )

        except Exception as error:
            logger.exception("CodeStruct background worker error: %s", error)
            if not self._cancelled:
                self.event_queue.put(("ERROR", str(error)))

    def _register_editor_file(self, file_path: str) -> Tuple[str, str]:
        reg_url = f"{self.backend_url}/api/v1/editor/selection"
        payload = {"file_path": file_path}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            reg_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                root_id = resp_data.get("capability_id") or resp_data.get("root_id")
                rel_path = resp_data.get("relative_path")
                if not root_id or not rel_path:
                    raise RuntimeError(
                        "Editor registration response missing 'capability_id' or 'relative_path'."
                    )
                return root_id, rel_path
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                msg = (
                    err_json.get("error", {}).get("message")
                    or err_json.get("detail")
                    or err_json.get("message")
                    or f"HTTP {err.code}: {err.reason}"
                )
            except Exception:
                msg = f"HTTP {err.code}: {err.reason}"
            raise RuntimeError(f"Editor file registration rejected: {msg}") from err
        except urllib.error.URLError as err:
            raise RuntimeError(
                f"Could not connect to CodeStruct backend at {self.backend_url}.\n"
                "Please verify that the backend server is running."
            ) from err

    def _submit(self) -> Tuple[str, str]:
        if self.file_path:
            effective_root, effective_rel = self._register_editor_file(self.file_path)
            if self._cancelled:
                return "", "cancelled"
            self.root_id = effective_root
            self.relative_path = effective_rel
        else:
            if not self.root_id or not self.relative_path:
                raise RuntimeError(
                    "Worker requires either (root_id, relative_path) or file_path."
                )
            effective_root = self.root_id
            effective_rel = self.relative_path

        submit_url = f"{self.backend_url}/api/v1/analyses"
        project_payload: dict[str, str] = {
            "root_id": effective_root,
            "relative_path": effective_rel,
        }
        if effective_root.startswith("cap_"):
            project_payload["capability_id"] = effective_root

        payload = {
            "project": project_payload,
            "options": {
                "metrics": False,
            },
            "refresh": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            submit_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                analysis_id = resp_data.get("analysis_id")
                state = resp_data.get("state", "queued")
                if not analysis_id:
                    raise RuntimeError("Server response missing 'analysis_id'.")
                return analysis_id, state
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                msg = (
                    err_json.get("error", {}).get("message")
                    or err_json.get("detail")
                    or err_json.get("message")
                    or f"HTTP {err.code}: {err.reason}"
                )
            except Exception:
                msg = f"HTTP {err.code}: {err.reason}"
            raise RuntimeError(f"Analysis submission rejected: {msg}") from err
        except urllib.error.URLError as err:
            raise RuntimeError(
                f"Could not connect to CodeStruct backend at {self.backend_url}.\n"
                "Please verify that the backend server is running."
            ) from err


class DummyCodeViewText:
    """Mock text widget satisfying Thonny Editor internal expectations."""

    def __init__(self, master: Any) -> None:
        self.master = master
        self.indent_width = 4
        self.tab_width = 4

    def update_tab_stops(self) -> None:
        pass

    def event_generate(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set_read_only(self, ro: bool) -> None:
        pass

    def edit_modified(self, val: bool | None = None) -> bool:
        return False

    def index(self, idx: str) -> str:
        return "1.0"

    def see(self, idx: str) -> None:
        pass

    def bind(self, *args: Any, **kwargs: Any) -> str:
        return ""

    def focus_set(self) -> None:
        pass


class DummyCodeView:
    """Lightweight dummy CodeView satisfying Thonny Editor internal expectations."""

    def __init__(self, master: Any) -> None:
        self.master = master
        self.text = DummyCodeViewText(master)

    def set_gutter_visibility(self, visible: bool) -> None:
        pass

    def set_line_length_margin(self, margin: int) -> None:
        pass

    def grid_main_widgets(self) -> None:
        pass

    def set_file_type(self, ft: str) -> None:
        pass

    def set_content(self, c: str) -> None:
        pass

    def set_content_as_bytes(self, b: bytes, keep_undo: bool = False) -> bool:
        return True

    def get_content(self, up_to_end: bool = False) -> str:
        return ""

    def get_content_as_bytes(self) -> bytes:
        return b""

    def focus_set(self) -> None:
        pass

    def get_text_widget(self) -> Any:
        return self.text


class CodeStructProjectExplorerView(ttk.Frame):
    """Unified Project & Symbol Explorer for Thonny.

    Serves as the sole, persistent file and symbol explorer in Thonny across all
    editor tabs, when CodeStruct is closed, and across Thonny restarts. Displays
    the full folder/file tree with nested Python module, class, method, and function
    symbols and line numbers.
    """

    IGNORED_DIRS = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
        ".egg-info",
    }

    def __init__(self, master: Any = None) -> None:
        super().__init__(master)
        self.containing_notebook: Any = None
        self.view_id: str = "FilesView"
        self.wb = get_workbench()

        initial_dir: Optional[str] = None
        if self.wb and hasattr(self.wb, "get_option"):
            try:
                initial_dir = self.wb.get_option("file.last_browser_folder")
            except Exception:
                initial_dir = None
        if not initial_dir or not os.path.isdir(initial_dir):
            if self.wb and hasattr(self.wb, "get_option"):
                try:
                    work_dir = self.wb.get_option("run.working_directory")
                    if work_dir and os.path.isdir(work_dir):
                        initial_dir = work_dir
                except Exception:
                    pass
        if not initial_dir or not os.path.isdir(initial_dir):
            mappings = os.environ.get("CODESTRUCT_ROOT_MAPPINGS", "")
            if mappings:
                for item in mappings.split(";"):
                    if "=" in item:
                        _, mpath = item.split("=", 1)
                        if os.path.isdir(mpath):
                            initial_dir = mpath
                            break
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = str(Path.cwd())

        self.current_project_dir: Path = Path(initial_dir).resolve()
        self.search_filter: str = ""
        self.kind_filter: str = "all"
        self._tree_items: dict[str, dict[str, Any]] = {}
        self.filter_buttons: dict[str, Any] = {}

        self._build_ui()
        self.populate_tree()

    @property
    def local_files(self) -> Any:
        return self

    @property
    def current_focus(self) -> str:
        return str(self.current_project_dir)

    def get_tab_text(self) -> str:
        return "Project Explorer"

    def get_active_local_dir(self) -> str:
        return str(self.current_project_dir)

    def get_active_directory(self) -> str:
        return str(self.current_project_dir)

    def get_active_remote_dir(self) -> None:
        return None

    def is_active_browser(self) -> bool:
        return True

    def should_open_name_in_thonny(self, name: str) -> bool:
        return True

    def get_selected_path(self) -> Optional[str]:
        sel = self.tree.selection()
        if sel and sel[0] in self._tree_items:
            return self._tree_items[sel[0]].get("path")
        return str(self.current_project_dir)

    def get_selected_file(self) -> Optional[str]:
        sel = self.tree.selection()
        if sel and sel[0] in self._tree_items:
            item = self._tree_items[sel[0]]
            if item.get("type") in ("file", "class", "function", "method"):
                return item.get("path")
        return None

    def select_path_if_visible(self, path: str) -> None:
        if not path:
            return
        try:
            p = Path(path).resolve()
            for node_id, data in self._tree_items.items():
                node_path = data.get("path")
                if node_path and Path(node_path).resolve() == p:
                    self.tree.selection_set(node_id)
                    self.tree.see(node_id)
                    return
        except Exception:
            pass

    def check_update_focus(self) -> None:
        pass

    def on_show(self) -> None:
        self.populate_tree()

    def on_workbench_close(self) -> None:
        pass

    def on_backend_restart(self) -> None:
        pass

    def on_backend_terminate(self) -> None:
        pass

    def restore_split(self) -> None:
        pass

    def save_split(self) -> None:
        pass

    def refresh_tree(self) -> None:
        self.populate_tree()

    def _build_ui(self) -> None:
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill=tk.X, padx=4, pady=(4, 2))

        # Row 1: Folder display and buttons
        row1 = ttk.Frame(self.header_frame)
        row1.pack(fill=tk.X, pady=(0, 2))

        folder_name = self.current_project_dir.name or str(self.current_project_dir)
        self.folder_label = ttk.Label(
            row1,
            text=f"📁 {folder_name}",
            font=("Segoe UI", 9, "bold"),
            anchor=tk.W,
        )
        self.folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_switch = ttk.Button(
            row1,
            text="Open...",
            width=8,
            command=self.switch_project_folder,
        )
        self.btn_switch.pack(side=tk.RIGHT, padx=(2, 0))

        self.btn_refresh = ttk.Button(
            row1,
            text="🔄",
            width=3,
            command=self.populate_tree,
        )
        self.btn_refresh.pack(side=tk.RIGHT)

        # Row 2: Search Entry
        row2 = ttk.Frame(self.header_frame)
        row2.pack(fill=tk.X, pady=(2, 2))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self.search_entry = ttk.Entry(row2, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._set_search_placeholder()

        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)

        # Row 3: Filter Buttons
        row3 = ttk.Frame(self.header_frame)
        row3.pack(fill=tk.X, pady=(2, 4))

        def _make_filter_handler(k: str) -> Any:
            return lambda: self._set_kind_filter(k)

        self.filter_buttons = {}
        for k_id, k_label in [
            ("all", "All"),
            ("files", "Files"),
            ("class", "Classes"),
            ("function", "Functions"),
            ("method", "Methods"),
        ]:
            btn = tk.Button(
                row3,
                text=k_label,
                font=("Segoe UI", 7),
                relief=tk.FLAT,
                padx=3,
                pady=1,
                bg="#0d9488" if k_id == "all" else "#f1f5f9",
                fg="#ffffff" if k_id == "all" else "#334155",
                command=_make_filter_handler(k_id),
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.filter_buttons[k_id] = btn

        # Treeview with scrollbars
        tree_container = ttk.Frame(self)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_container,
            columns=("line",),
            selectmode="browse",
            show="tree headings",
        )
        self.tree.heading("#0", text="Project Symbols", anchor=tk.W)
        self.tree.heading("line", text="Line", anchor=tk.E)
        self.tree.column("#0", stretch=True, width=180)
        self.tree.column("line", width=45, anchor=tk.E)

        vsb = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(
            tree_container, orient=tk.HORIZONTAL, command=self.tree.xview
        )
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Return>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_context_menu)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)

    def _set_search_placeholder(self) -> None:
        if not self.search_var.get():
            self.search_entry.insert(0, "Filter files & symbols...")
            self.search_entry.configure(foreground="#94a3b8")

    def _on_search_focus_in(self, event: Any = None) -> None:
        if self.search_entry.get() == "Filter files & symbols...":
            self.search_entry.delete(0, tk.END)
            self.search_entry.configure(foreground="#0f172a")

    def _on_search_focus_out(self, event: Any = None) -> None:
        if not self.search_entry.get():
            self._set_search_placeholder()

    def _on_search_changed(self, *args: Any) -> None:
        if not hasattr(self, "tree"):
            return
        val = self.search_var.get()
        if val == "Filter files & symbols...":
            self.search_filter = ""
        else:
            self.search_filter = val.strip().lower()
        self.populate_tree()

    def _set_kind_filter(self, kid: str) -> None:
        self.kind_filter = kid
        for k, btn in self.filter_buttons.items():
            if k == kid:
                btn.configure(bg="#0d9488", fg="#ffffff")
            else:
                btn.configure(bg="#f1f5f9", fg="#334155")
        self.populate_tree()

    def switch_project_folder(self, new_dir: Optional[str] = None) -> None:
        wb = self.wb or get_workbench()
        if new_dir is None:
            new_dir = tkinter.filedialog.askdirectory(
                initialdir=str(self.current_project_dir),
                title="Select Project Folder",
                parent=wb,
            )
        if new_dir and os.path.isdir(new_dir):
            self.current_project_dir = Path(new_dir).resolve()
            if wb and hasattr(wb, "set_option"):
                try:
                    wb.set_option("file.last_browser_folder", str(self.current_project_dir))
                except Exception:
                    pass
            folder_name = (
                self.current_project_dir.name or str(self.current_project_dir)
            )
            self.folder_label.configure(text=f"📁 {folder_name}")
            self.populate_tree()

            if wb:
                editor_nb = getattr(wb, "get_editor_notebook", lambda: None)()
                if editor_nb:
                    for child in editor_nb.winfo_children():
                        if isinstance(child, CodeStructEditorTab):
                            wb.after(50, open_codestruct_workbench)
                            break

    def populate_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._tree_items.clear()

        if (
            not self.current_project_dir.exists()
            or not self.current_project_dir.is_dir()
        ):
            return

        root_id = self.tree.insert(
            "",
            tk.END,
            text=f"📁 {self.current_project_dir.name}",
            open=True,
            values=("",),
        )
        self._tree_items[root_id] = {
            "type": "dir",
            "path": str(self.current_project_dir),
            "line": None,
        }

        self._populate_dir(self.current_project_dir, root_id)

    def _populate_dir(self, dir_path: Path, parent_node_id: str) -> None:
        try:
            entries = sorted(
                os.scandir(dir_path),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except OSError:
            return

        for entry in entries:
            name = entry.name
            if name.startswith(".") or name in self.IGNORED_DIRS:
                continue

            entry_path = Path(entry.path)
            if entry.is_dir():
                dir_id = self.tree.insert(
                    parent_node_id,
                    tk.END,
                    text=f"📁 {name}",
                    open=False,
                    values=("",),
                )
                self._tree_items[dir_id] = {
                    "type": "dir",
                    "path": str(entry_path),
                    "line": None,
                    "loaded": False,
                }
                # Insert placeholder to display '+' expand button
                self.tree.insert(dir_id, tk.END, text="")
            else:
                is_python = name.endswith(".py") or name.endswith(".pyw")
                if (
                    self.kind_filter != "all"
                    and self.kind_filter != "files"
                    and not is_python
                ):
                    continue

                if self.search_filter and self.search_filter not in name.lower():
                    if not is_python:
                        continue

                file_icon = "🐍" if is_python else "📄"
                file_id = self.tree.insert(
                    parent_node_id,
                    tk.END,
                    text=f"{file_icon} {name}",
                    open=True,
                    values=("",),
                )
                self._tree_items[file_id] = {
                    "type": "file",
                    "path": str(entry_path),
                    "line": 1,
                }

                if is_python and self.kind_filter != "files":
                    self._populate_python_symbols(entry_path, file_id)

    def _populate_python_symbols(self, file_path: Path, parent_file_id: str) -> None:
        try:
            if file_path.stat().st_size > 1_000_000:
                return
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if self.kind_filter in ("all", "class", "method"):
                    if (
                        self.search_filter
                        and self.search_filter not in node.name.lower()
                    ):
                        method_matches = any(
                            isinstance(
                                m, (ast.FunctionDef, ast.AsyncFunctionDef)
                            )
                            and self.search_filter in m.name.lower()
                            for m in node.body
                        )
                        if not method_matches:
                            continue

                    class_id = self.tree.insert(
                        parent_file_id,
                        tk.END,
                        text=f"[C] {node.name}",
                        open=True,
                        values=(f"L{node.lineno}",),
                    )
                    self._tree_items[class_id] = {
                        "type": "class",
                        "path": str(file_path),
                        "line": node.lineno,
                        "name": node.name,
                    }

                    for item in node.body:
                        if isinstance(
                            item, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ):
                            if self.kind_filter in ("all", "method"):
                                if (
                                    self.search_filter
                                    and self.search_filter
                                    not in item.name.lower()
                                ):
                                    continue
                                meth_id = self.tree.insert(
                                    class_id,
                                    tk.END,
                                    text=f"[m] {item.name}()",
                                    values=(f"L{item.lineno}",),
                                )
                                self._tree_items[meth_id] = {
                                    "type": "method",
                                    "path": str(file_path),
                                    "line": item.lineno,
                                    "name": item.name,
                                }
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.kind_filter in ("all", "function"):
                    if (
                        self.search_filter
                        and self.search_filter not in node.name.lower()
                    ):
                        continue
                    func_id = self.tree.insert(
                        parent_file_id,
                        tk.END,
                        text=f"[f] {node.name}()",
                        values=(f"L{node.lineno}",),
                    )
                    self._tree_items[func_id] = {
                        "type": "function",
                        "path": str(file_path),
                        "line": node.lineno,
                        "name": node.name,
                    }

    def _on_tree_open(self, event: Any = None) -> None:
        item_id = self.tree.focus()
        if not item_id:
            sel = self.tree.selection()
            if sel:
                item_id = sel[0]
        if not item_id:
            return
        meta = self._tree_items.get(item_id)
        if meta and meta.get("type") == "dir" and not meta.get("loaded", True):
            self._load_dir_children(item_id, Path(meta["path"]))

    def _load_dir_children(self, node_id: str, dir_path: Path) -> None:
        meta = self._tree_items.get(node_id)
        if meta:
            meta["loaded"] = True
        for child in self.tree.get_children(node_id):
            self.tree.delete(child)
        self._populate_dir(dir_path, node_id)

    def _on_tree_double_click(self, event: Any = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]
        meta = self._tree_items.get(item_id)
        if not meta:
            return

        if meta.get("type") == "dir":
            is_open = self.tree.item(item_id, "open")
            if not is_open and not meta.get("loaded", True):
                self._load_dir_children(item_id, Path(meta["path"]))
            self.tree.item(item_id, open=not is_open)
            return

        path = meta.get("path")
        line = meta.get("line")
        wb = self.wb or get_workbench()
        if wb and path:
            editor_nb = getattr(wb, "get_editor_notebook", lambda: None)()
            if editor_nb:
                try:
                    if line and hasattr(editor_nb, "show_file_at_line"):
                        editor_nb.show_file_at_line(path, int(line))
                    elif hasattr(editor_nb, "show_file"):
                        editor_nb.show_file(path)
                except Exception as exc:
                    logger.debug("Failed opening file from explorer: %s", exc)

    def _on_tree_context_menu(self, event: Any) -> None:
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            meta = self._tree_items.get(item_id, {})
            menu = tk.Menu(self, tearoff=0)
            if meta.get("type") in ("file", "class", "function", "method"):
                menu.add_command(
                    label="Open in Editor",
                    command=self._on_tree_double_click,
                )
                if meta.get("line"):
                    menu.add_command(
                        label=f"Jump to Line {meta['line']}",
                        command=self._on_tree_double_click,
                    )
            menu.add_command(
                label="Switch Project Folder...",
                command=self.switch_project_folder,
            )
            menu.add_command(
                label="Refresh Tree",
                command=self.populate_tree,
            )
            menu.tk_popup(event.x_root, event.y_root)


def _integrate_persistent_explorer(wb: Any) -> None:
    """Register CodeStructProjectExplorerView as Thonny's sole, persistent file & symbol explorer."""
    if wb is None:
        return
    try:
        view_records = getattr(wb, "_view_records", None)
        if isinstance(view_records, dict) and "FilesView" in view_records:
            view_records["FilesView"]["class"] = CodeStructProjectExplorerView
            view_records["FilesView"]["label"] = "Project Explorer"

            if "instance" in view_records["FilesView"]:
                old_view = view_records["FilesView"]["instance"]
                if not isinstance(old_view, CodeStructProjectExplorerView):
                    containing_nb = getattr(old_view, "containing_notebook", None)
                    new_view = CodeStructProjectExplorerView(
                        getattr(wb, "_main_pw", wb)
                    )
                    new_view.containing_notebook = containing_nb
                    new_view.view_id = "FilesView"
                    view_records["FilesView"]["instance"] = new_view

                    if containing_nb is not None:
                        try:
                            tabs = containing_nb.tabs()
                            idx = -1
                            for i, tab in enumerate(tabs):
                                if containing_nb.nametowidget(tab) == old_view:
                                    idx = i
                                    break
                            containing_nb.forget(old_view)
                            if idx >= 0:
                                containing_nb.insert(
                                    idx, new_view, text="Project Explorer"
                                )
                            else:
                                containing_nb.add(new_view, text="Project Explorer")
                            containing_nb.select(new_view)
                        except Exception as nb_exc:
                            logger.debug(
                                "Could not swap explorer tab in notebook: %s",
                                nb_exc,
                            )

                    try:
                        old_view.destroy()
                    except Exception:
                        pass
        elif hasattr(wb, "add_view"):
            try:
                wb.add_view(
                    CodeStructProjectExplorerView,
                    "Project Explorer",
                    "nw",
                    visible_by_default=True,
                )
            except Exception:
                pass

        if hasattr(wb, "set_option"):
            try:
                wb.set_option("view.FilesView.visible", True)
                wb.set_option("view.filesview.visible", True)
            except Exception:
                pass

        if hasattr(wb, "get_variable"):
            for var_name in ("view.FilesView.visible", "view.filesview.visible"):
                try:
                    v = wb.get_variable(var_name)
                    if hasattr(v, "set"):
                        v.set(True)
                except Exception:
                    pass

        if hasattr(wb, "show_view"):
            try:
                wb.show_view("FilesView", set_focus=False)
            except Exception:
                pass
    except Exception as exc:
        logger.warning(
            "Could not integrate persistent CodeStruct Project Explorer: %s",
            exc,
        )


# FilesView visibility state tracking across tab lifecycle
_user_files_view_was_visible: Optional[bool] = None


def is_files_view_visible(wb: Any) -> bool:
    """Check if Thonny's persistent Project Explorer is currently visible in the UI."""
    if wb is None:
        return False
    try:
        if hasattr(wb, "get_view"):
            view = wb.get_view("FilesView", create=False)
            if view is not None:
                return getattr(view, "containing_notebook", None) is not None
    except Exception:
        pass
    return False


def _hide_files_pane(wb: Any) -> None:
    """No-op: CodeStructProjectExplorerView is persistent across all tabs and editor states."""
    pass


def _restore_files_pane(wb: Any) -> None:
    """No-op: CodeStructProjectExplorerView is persistent across all tabs and editor states."""
    pass


def _on_editor_tab_changed(wb: Any) -> None:
    """Hook invoked when Thonny EditorNotebook switches active tab."""
    pass


def _bind_editor_notebook_events(wb: Any) -> None:
    """Attach event listeners to Thonny's EditorNotebook for tab lifecycle management."""
    if wb is None:
        return
    try:
        editor_notebook = getattr(wb, "get_editor_notebook", lambda: None)()
        if editor_notebook is not None:
            if not getattr(editor_notebook, "_codestruct_tab_bound", False):
                editor_notebook.bind(
                    "<<NotebookTabChanged>>",
                    lambda event: _on_editor_tab_changed(wb),
                    add=True,
                )
                editor_notebook._codestruct_tab_bound = True
    except Exception as exc:
        logger.debug("Failed binding to editor notebook: %s", exc)


def print_to_thonny_shell(wb: Any, text: str, stream: str = "stdout") -> None:
    """Safely write text to Thonny's native ShellView on the Tk main thread."""
    if wb is None:
        return
    try:
        shell = wb.get_view("ShellView", create=False)
        if shell is None:
            shell = wb.get_view("ShellView", create=True)
        if shell is not None and hasattr(shell, "text"):
            st = shell.text
            if not text.endswith("\n"):
                text += "\n"
            tags = ("io", stream)
            if hasattr(st, "_insert_text_directly"):
                st._insert_text_directly(text, tags)
            elif hasattr(st, "insert"):
                st.insert("end", text, tags)
            if hasattr(st, "see"):
                st.see("end")
    except Exception as exc:
        logger.debug("Failed printing to Thonny shell: %s", exc)


class CodeStructEditorTab(Editor):
    """Real Thonny editor tab hosting the CodeStruct Stitch architecture workbench via WebView2."""

    def __init__(self, master: Any, viewer_url: str, project_path: str) -> None:
        ttk.Frame.__init__(self, master)
        self.master = master
        self.viewer_url = viewer_url
        self.project_path = str(Path(project_path).resolve())
        self._uri = f"codestruct://{self.project_path}"

        self._code_view: Any = DummyCodeView(self)
        self._dummy_text: Any = self._code_view.text

        self._webview: Any = None
        self._container: Any = None
        if tkwry is not None:
            try:
                self._container = tk.Frame(self)
                self._container.pack(fill="both", expand=True)
                webview_dir = (
                    Path(tempfile.gettempdir())
                    / f"codestruct_thonny_webview_{os.getpid()}"
                )
                webview_dir.mkdir(parents=True, exist_ok=True)
                self._webview = tkwry.WebView(
                    self._container,
                    url=viewer_url,
                    data_directory=str(webview_dir),
                )
                self._webview.pack(fill="both", expand=True)
            except Exception as exc:
                logger.warning("Could not initialize WebView2 in editor tab: %s", exc)
                self._webview = None
                if self._container is not None:
                    try:
                        self._container.destroy()
                    except Exception:
                        pass
                    self._container = None

        if self._webview is None:
            self._fallback_label = ttk.Label(
                self,
                text=f"CodeStruct Architecture Workbench\nProject: {self.project_path}\nURL: {viewer_url}",
                anchor="center",
                justify="center",
            )
            self._fallback_label.pack(fill="both", expand=True, padx=20, pady=20)

    def focus_set(self) -> None:
        if self._webview is not None:
            try:
                self._webview.focus_set()
                return
            except Exception:
                pass
        try:
            ttk.Frame.focus_set(self)
        except Exception:
            pass

    def is_focused(self) -> bool:
        try:
            focused = self.focus_get()
            return (
                focused == self
                or (self._container is not None and focused == self._container)
                or (self._webview is not None and focused == self._webview)
            )
        except Exception:
            return False

    def get_text_widget(self) -> Any:
        return self._dummy_text

    def get_long_description(self) -> str:
        return f"CodeStruct: {self.project_path}"

    def get_title(self) -> str:
        name = Path(self.project_path).name or self.project_path
        return f"CodeStruct: {name}"

    def get_uri(self) -> str:
        return self._uri

    def get_target_path(self) -> str:
        return self.project_path

    def is_local(self) -> bool:
        return False

    def is_remote(self) -> bool:
        return False

    def is_untitled(self) -> bool:
        return False

    def is_modified(self) -> bool:
        return False

    def save_file_enabled(self) -> bool:
        return False

    def check_for_external_changes(self) -> None:
        pass

    def update_appearance(self) -> None:
        pass

    def update_file_type(self) -> None:
        pass

    def get_content(self, up_to_end: bool = False) -> str:
        return ""

    def update_url(self, new_url: str, new_project_path: str) -> None:
        self.viewer_url = new_url
        self.project_path = str(Path(new_project_path).resolve())
        self._uri = f"codestruct://{self.project_path}"
        if self._webview is not None:
            try:
                self._webview.load_url(new_url)
            except Exception as exc:
                logger.warning("Failed to load URL in webview: %s", exc)
        elif hasattr(self, "_fallback_label"):
            self._fallback_label.config(
                text=f"CodeStruct Architecture Workbench\nProject: {self.project_path}\nURL: {new_url}"
            )

    def close(self) -> None:
        wb = get_workbench()
        _restore_files_pane(wb)
        if self._webview is not None:
            try:
                self._webview.destroy()
            except Exception:
                pass
            self._webview = None
        if getattr(self, "_container", None) is not None:
            try:
                self._container.destroy()
            except Exception:
                pass
            self._container = None
        try:
            ttk.Frame.destroy(self)
        except Exception:
            pass

    def destroy(self) -> None:
        wb = get_workbench()
        _restore_files_pane(wb)
        if self._webview is not None:
            try:
                self._webview.destroy()
            except Exception:
                pass
            self._webview = None
        if getattr(self, "_container", None) is not None:
            try:
                self._container.destroy()
            except Exception:
                pass
            self._container = None
        try:
            ttk.Frame.destroy(self)
        except Exception:
            pass


def get_file_view_folder(wb: Any) -> Optional[str]:
    """Retrieve the directory path currently open in Thonny's File view, if any."""
    if wb is None:
        return None
    try:
        files_view = None
        if hasattr(wb, "get_view"):
            files_view = wb.get_view("FilesView", create=False)
            if files_view is None:
                files_view = wb.get_view("FilesView", create=True)

        raw_path: Optional[str] = None
        if files_view is not None:
            # 1. Primary supported Thonny API: get_active_local_dir()
            if hasattr(files_view, "get_active_local_dir"):
                try:
                    res = files_view.get_active_local_dir()
                    if isinstance(res, str) and res.strip():
                        raw_path = res.strip()
                except Exception:
                    raw_path = None

            # 2. Direct local_files browser API: get_active_directory()
            if not raw_path and hasattr(files_view, "local_files"):
                local_files = files_view.local_files
                if hasattr(local_files, "get_active_directory"):
                    try:
                        res = local_files.get_active_directory()
                        if isinstance(res, str) and res.strip():
                            raw_path = res.strip()
                    except Exception:
                        pass

                # 3. Fallback: inspect current_focus if active directory was unset
                if not raw_path and hasattr(local_files, "current_focus"):
                    res = getattr(local_files, "current_focus", None)
                    if isinstance(res, str) and res.strip():
                        raw_path = res.strip()

        # 4. Fallback: active editor file in Thonny
        if not raw_path and hasattr(wb, "get_editor_notebook"):
            try:
                ed_nb = wb.get_editor_notebook()
                if ed_nb:
                    curr_ed = ed_nb.get_current_editor()
                    if curr_ed and hasattr(curr_ed, "get_filename"):
                        fn = curr_ed.get_filename()
                        if fn and isinstance(fn, str) and os.path.isfile(fn):
                            raw_path = str(Path(fn).parent)
            except Exception:
                pass

        # 5. Fallback: environment root mappings
        if not raw_path:
            mappings = os.environ.get("CODESTRUCT_ROOT_MAPPINGS", "")
            if mappings:
                for item in mappings.split(";"):
                    if "=" in item:
                        _, mpath = item.split("=", 1)
                        if os.path.isdir(mpath):
                            raw_path = mpath
                            break

        # 6. Fallback: Thonny's last browser folder option
        if not raw_path and hasattr(wb, "get_option"):
            try:
                opt = wb.get_option("file.last_browser_folder")
                if opt and isinstance(opt, str) and os.path.isdir(opt):
                    raw_path = opt
            except Exception:
                pass

        if raw_path and isinstance(raw_path, str) and raw_path.strip():
            p = Path(raw_path.strip())
            try:
                # If pointed at a file, determine the containing folder view/root
                if p.is_file():
                    p = p.parent
                if p.is_dir():
                    return str(p.resolve())
            except OSError:
                pass
    except Exception as exc:
        logger.debug("Could not read File view folder: %s", exc)
    return None


def _report_analysis_to_shell(
    wb: Any, backend_url: str, analysis_id: str, folder_name: str
) -> None:
    """Stream background analysis status and structured diagnostics into Thonny's native ShellView."""
    print_to_thonny_shell(
        wb,
        f"\n[CodeStruct] Architecture Workbench: {folder_name}\n"
        f"• Analysis ID: {analysis_id}\n"
        f"• Status: Analyzing project structure (zero execution AST parsing)...\n",
        stream="stdout",
    )

    def _worker() -> None:
        start_time = time.time()
        completed_data = None
        while time.time() - start_time < 30.0 and not _is_shutting_down:
            try:
                status_url = f"{backend_url.rstrip('/')}/api/v1/analyses/{urllib.parse.quote(analysis_id)}"
                req = urllib.request.Request(
                    status_url, headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if data.get("terminal"):
                    completed_data = data
                    break
            except Exception:
                pass
            time.sleep(0.4)

        if _is_shutting_down or completed_data is None:
            return

        state = completed_data.get("state")
        if state == "completed":
            nodes_by_kind: dict[str, int] = {}
            total_symbols = 0
            try:
                graph_url = f"{backend_url.rstrip('/')}/api/v1/analyses/{urllib.parse.quote(analysis_id)}/graph"
                req = urllib.request.Request(
                    graph_url, headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    gdata = json.loads(resp.read().decode("utf-8"))
                nodes = gdata.get("nodes", [])
                total_symbols = len(nodes)
                for n in nodes:
                    k = (n.get("kind") or "").lower()
                    nodes_by_kind[k] = nodes_by_kind.get(k, 0) + 1
            except Exception:
                pass

            diags: list[dict[str, Any]] = []
            try:
                diag_url = f"{backend_url.rstrip('/')}/api/v1/analyses/{urllib.parse.quote(analysis_id)}/diagnostics"
                req = urllib.request.Request(
                    diag_url, headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    resp_obj = json.loads(resp.read().decode("utf-8"))
                    if isinstance(resp_obj, dict):
                        diags = resp_obj.get("items", [])
                    elif isinstance(resp_obj, list):
                        diags = resp_obj
            except Exception:
                pass

            lines = [
                f"[CodeStruct] Static Analysis Complete: {folder_name}",
                f"• Discovered {total_symbols} AST symbols: "
                f"{nodes_by_kind.get('module', 0)} Module(s), "
                f"{nodes_by_kind.get('class', 0)} Class(es), "
                f"{nodes_by_kind.get('function', 0)} Function(s), "
                f"{nodes_by_kind.get('method', 0)} Method(s).",
                "• Top-to-bottom architecture graph synchronized. Zero execution invariant: project code was parsed, never executed.",
            ]
            if diags:
                lines.append(f"[CodeStruct] Diagnostics ({len(diags)}):")
                for d in diags[:20]:
                    loc = d.get("location") or {}
                    file_path = loc.get("path") or "project"
                    line_num = loc.get("start_line") or 1
                    col_num = loc.get("start_column") or 1
                    sev = (d.get("severity") or "info").upper()
                    code = d.get("code") or "DIAG"
                    msg = d.get("message") or ""
                    lines.append(
                        f'  File "{file_path}", line {line_num}, col {col_num}: [{sev}] {code} - {msg}'
                    )
                if len(diags) > 20:
                    lines.append(f"  ... and {len(diags) - 20} more diagnostic items.")
            else:
                lines.append(
                    "[CodeStruct] Diagnostics: Clean analysis (0 issues detected)."
                )

            report_text = "\n".join(lines) + "\n"
            try:
                wb.after(
                    0, lambda: print_to_thonny_shell(wb, report_text, stream="stdout")
                )
            except Exception:
                pass
        elif state == "failed":
            err_code = completed_data.get("error_code") or "ANALYSIS_FAILED"
            err_msg = completed_data.get("error_message") or "Unknown error"
            report_text = (
                f"[CodeStruct] Static Analysis Failed: [{err_code}] {err_msg}\n"
            )
            try:
                wb.after(
                    0, lambda: print_to_thonny_shell(wb, report_text, stream="stderr")
                )
            except Exception:
                pass

    t = threading.Thread(
        target=_worker, daemon=True, name="codestruct-analysis-reporter"
    )
    t.start()


def open_codestruct_workbench(event: Any = None) -> None:
    """Action invoked from Thonny Tools menu to open CodeStruct workbench as an editor tab."""
    wb = get_workbench()
    if wb is None:
        return

    # 1. Read current project directory from Thonny's File view
    folder = get_file_view_folder(wb)
    if not folder:
        tkinter.messagebox.showinfo(
            "No Folder Open in File View",
            "No project folder is currently open in Thonny's File view.\n\n"
            "Please open your project folder in Thonny's File view (View → Files) before launching CodeStruct.",
            parent=wb,
        )
        return

    folder_path = Path(folder)
    try:
        resolved_folder = folder_path.resolve(strict=True)
    except (OSError, RuntimeError) as err:
        tkinter.messagebox.showerror(
            "Folder Inaccessible",
            f"The selected project folder cannot be accessed on disk:\n\n{folder}\n({err})",
            parent=wb,
        )
        return

    if not resolved_folder.is_dir():
        tkinter.messagebox.showerror(
            "Invalid Directory",
            f"The selected path is not a directory:\n\n{resolved_folder}",
            parent=wb,
        )
        return

    if resolved_folder == Path(resolved_folder.anchor):
        tkinter.messagebox.showerror(
            "Drive Root Rejected",
            f"Cannot analyze a drive root directly:\n\n{resolved_folder}",
            parent=wb,
        )
        return

    if _has_link_component(resolved_folder) or _is_link_or_reparse(resolved_folder):
        tkinter.messagebox.showerror(
            "Symlinks Not Supported",
            f"CodeStruct does not support symlinks or reparse points for security reasons:\n\n{resolved_folder}",
            parent=wb,
        )
        return

    # 2. Validate URLs as loopback-only
    backend_url = os.environ.get("CODESTRUCT_BACKEND_URL", DEFAULT_BACKEND_URL)
    frontend_url = os.environ.get("CODESTRUCT_FRONTEND_URL", DEFAULT_FRONTEND_URL)

    if not is_loopback_url(backend_url):
        tkinter.messagebox.showerror(
            "Security Configuration Error",
            f"The configured backend URL is not a loopback address:\n  {backend_url}\n\n"
            "CodeStruct only permits loopback addresses (127.0.0.1, localhost, ::1).",
            parent=wb,
        )
        return

    if not is_loopback_url(frontend_url):
        tkinter.messagebox.showerror(
            "Security Configuration Error",
            f"The configured frontend viewer URL is not a loopback address:\n  {frontend_url}\n\n"
            "CodeStruct only permits loopback addresses (127.0.0.1, localhost, ::1).",
            parent=wb,
        )
        return

    _set_status_message(
        wb, f"CodeStruct: Registering project folder '{resolved_folder.name}'..."
    )

    # 3. Register folder with backend via POST /api/v1/host/register-folder
    try:
        reg_url = f"{backend_url.rstrip('/')}/api/v1/host/register-folder"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        host_token = os.environ.get("CODESTRUCT_HOST_TOKEN")
        if host_token:
            headers["X-CodeStruct-Host-Token"] = host_token

        payload = json.dumps({"path": str(resolved_folder)}).encode("utf-8")
        req = urllib.request.Request(
            reg_url, data=payload, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        root_id = data.get("root_id")
        analysis_id = data.get("analysis_id")
        if not root_id or not analysis_id:
            raise RuntimeError(
                "Backend registration response missing 'root_id' or 'analysis_id'."
            )
    except Exception as exc:
        logger.exception(
            "Failed to register project folder with CodeStruct backend: %s", exc
        )
        tkinter.messagebox.showerror(
            "Backend Connection Error",
            f"Could not register project folder with CodeStruct backend:\n\n{exc}",
            parent=wb,
        )
        _set_status_message(wb, "CodeStruct: Backend registration failed.")
        return

    # 4. Construct viewer URL with embed=thonny
    viewer_url = build_workbench_viewer_url(
        frontend_url,
        analysis_id=analysis_id,
        project_id=root_id,
        session_token=root_id,
    )

    editor_notebook = getattr(wb, "get_editor_notebook", lambda: None)()
    if editor_notebook is None:
        tkinter.messagebox.showerror(
            "Thonny Integration Error",
            "Thonny editor notebook is not available.",
            parent=wb,
        )
        return

    _bind_editor_notebook_events(wb)

    canonical_folder_str = str(resolved_folder)

    # 5. Ensure unified CodeStruct Project Explorer is active
    _integrate_persistent_explorer(wb)

    # 6. Open or update CodeStructEditorTab in editor_notebook
    existing_tab: Optional[CodeStructEditorTab] = None
    for child in editor_notebook.winfo_children():
        if isinstance(child, CodeStructEditorTab):
            existing_tab = child
            break

    if existing_tab is not None:
        if existing_tab.project_path == canonical_folder_str:
            editor_notebook.select(existing_tab)
            existing_tab.focus_set()
        else:
            existing_tab.update_url(viewer_url, canonical_folder_str)
            try:
                editor_notebook.tab(existing_tab, text=existing_tab.get_title())
            except Exception:
                pass
            editor_notebook.select(existing_tab)
            existing_tab.focus_set()
    else:
        new_tab = CodeStructEditorTab(editor_notebook, viewer_url, canonical_folder_str)
        editor_notebook.add(new_tab, text=new_tab.get_title())
        editor_notebook.select(new_tab)
        new_tab.focus_set()

    # 7. Bind navigation session to the registered root and start navigation polling
    global \
        _nav_session_token, \
        _nav_registered_root, \
        _nav_registered_file, \
        _nav_registered_file_resolved
    with _state_lock:
        _nav_session_token = root_id
        _nav_registered_root = resolved_folder
        _nav_registered_file = None
        _nav_registered_file_resolved = None

    _start_navigation_polling(wb, backend_url)
    _set_status_message(
        wb, f"CodeStruct: Workbench loaded for '{resolved_folder.name}'."
    )

    # 8. Report analysis status and diagnostics directly to Thonny's native Shell
    _report_analysis_to_shell(wb, backend_url, analysis_id, resolved_folder.name)


def analyze_current_project(event: Any = None) -> None:
    """Action invoked from Thonny Tools menu to analyze active Python file."""
    global _active_operation, _active_worker

    wb = get_workbench()
    if wb is None:
        return

    with _state_lock:
        if _active_operation is not None:
            _set_status_message(wb, "CodeStruct: Operation already in progress.")
            return

    operation_started = False
    try:
        # 1. Determine active editor from Thonny
        editor_notebook = getattr(wb, "get_editor_notebook", lambda: None)()
        editor = (
            editor_notebook.get_current_editor()
            if editor_notebook is not None
            else None
        )
        if editor is None:
            tkinter.messagebox.showinfo(
                "No Active File",
                "No Python file is currently open in Thonny.\n\n"
                "Please open a Python (.py or .pyw) file in the editor to analyze.",
                parent=wb,
            )
            return

        # 2. Check if editor is on a remote device
        if getattr(editor, "is_remote", lambda: False)():
            tkinter.messagebox.showinfo(
                "Remote File Not Supported",
                "CodeStruct can only analyze local files.\n\n"
                "Remote files on microcontrollers or SSH devices are not supported.",
                parent=wb,
            )
            return

        # 3. Check if editor is untitled or has no target path
        is_untitled = getattr(editor, "is_untitled", lambda: False)()
        target_path_str = getattr(editor, "get_target_path", lambda: None)()
        if is_untitled or not target_path_str:
            tkinter.messagebox.showinfo(
                "Unsaved File",
                "Please save the file before analyzing with CodeStruct.",
                parent=wb,
            )
            return

        # 4. Check if editor has unsaved modifications
        if getattr(editor, "is_modified", lambda: False)():
            tkinter.messagebox.showinfo(
                "Unsaved Changes",
                "Please save your changes before analyzing with CodeStruct.",
                parent=wb,
            )
            return

        # 5. Validate file extension (.py or .pyw)
        target_path = Path(target_path_str)
        if target_path.suffix.lower() not in (".py", ".pyw"):
            tkinter.messagebox.showinfo(
                "Unsupported File Type",
                f"Only Python files (.py or .pyw) can be analyzed.\n\n"
                f"The current file is '{target_path.name}'.",
                parent=wb,
            )
            return

        # 6. Validate path exists, is a regular file, and not a symlink/reparse point
        if _has_link_component(target_path.absolute()) or _is_link_or_reparse(
            target_path
        ):
            tkinter.messagebox.showerror(
                "Symlinks Not Supported",
                f"CodeStruct does not support symlinks or reparse points for security reasons:\n\n{target_path}",
                parent=wb,
            )
            return

        try:
            resolved_path = target_path.resolve(strict=True)
        except (OSError, RuntimeError) as err:
            tkinter.messagebox.showerror(
                "File Inaccessible",
                f"The active file cannot be accessed on disk:\n\n{target_path}\n({err})",
                parent=wb,
            )
            return

        if not resolved_path.is_file():
            tkinter.messagebox.showerror(
                "Invalid File",
                f"The active editor path is not a regular file:\n\n{resolved_path}",
                parent=wb,
            )
            return

        if _is_link_or_reparse(resolved_path):
            tkinter.messagebox.showerror(
                "Symlinks Not Supported",
                f"CodeStruct does not support symlinks or reparse points for security reasons:\n\n{resolved_path}",
                parent=wb,
            )
            return

        # 7. Validate URLs as loopback-only
        backend_url = os.environ.get("CODESTRUCT_BACKEND_URL", DEFAULT_BACKEND_URL)
        frontend_url = os.environ.get("CODESTRUCT_FRONTEND_URL", DEFAULT_FRONTEND_URL)

        if not is_loopback_url(backend_url):
            tkinter.messagebox.showerror(
                "Security Configuration Error",
                f"The configured backend URL is not a loopback address:\n  {backend_url}\n\n"
                "CodeStruct only permits loopback addresses (127.0.0.1, localhost, ::1).",
                parent=wb,
            )
            return

        if not is_loopback_url(frontend_url):
            tkinter.messagebox.showerror(
                "Security Configuration Error",
                f"The configured frontend viewer URL is not a loopback address:\n  {frontend_url}\n\n"
                "CodeStruct only permits loopback addresses (127.0.0.1, localhost, ::1).",
                parent=wb,
            )
            return

        # 8. Start background worker thread
        op_id = f"file:{resolved_path}"
        event_queue: queue.Queue[Tuple[str, Any]] = queue.Queue()

        with _state_lock:
            _active_operation = op_id
            worker = CodeStructAnalysisWorker(
                file_path=str(resolved_path),
                backend_url=backend_url,
                frontend_url=frontend_url,
                event_queue=event_queue,
            )
            _active_worker = worker

        _set_status_message(
            wb, f"CodeStruct: Submitting analysis for '{resolved_path.name}'..."
        )

        def _drain_queue() -> None:
            global _active_operation, _active_worker

            if _is_shutting_down:
                return

            try:
                if not wb.winfo_exists():
                    return
            except Exception:
                return

            finished = False
            while not event_queue.empty():
                try:
                    event_type, payload = event_queue.get_nowait()
                except queue.Empty:
                    break

                if event_type == "SUCCESS":
                    finished = True
                    analysis_id, viewer_url, browser_launched = payload
                    with _state_lock:
                        # Capture the capability_id (root_id set after registration)
                        # and registered file path so navigation is strictly bound.
                        global \
                            _nav_session_token, \
                            _nav_registered_file, \
                            _nav_registered_file_resolved, \
                            _nav_poll_generation
                        if _active_worker is not None:
                            _nav_session_token = _active_worker.root_id
                            if _active_worker.file_path:
                                _nav_registered_file = Path(_active_worker.file_path)
                                try:
                                    _nav_registered_file_resolved = Path(
                                        _active_worker.file_path
                                    ).resolve(strict=True)
                                except Exception:
                                    _nav_registered_file_resolved = _nav_registered_file
                        _active_operation = None
                        _active_worker = None

                    # Start navigation polling using the capability token so that
                    # the frontend can later request Thonny to open a file.
                    _start_navigation_polling(wb, backend_url)

                    if browser_launched:
                        _set_status_message(
                            wb, f"CodeStruct: Analysis {analysis_id} opened in browser."
                        )
                    else:
                        _set_status_message(
                            wb,
                            f"CodeStruct: Analysis {analysis_id} ready. Browser launch failed.",
                        )
                        tkinter.messagebox.showinfo(
                            "CodeStruct Analysis Ready",
                            f"Analysis submitted successfully (ID: {analysis_id}).\n\n"
                            f"Could not launch the web browser automatically.\n"
                            f"Please open this URL in your browser:\n\n{viewer_url}",
                            parent=wb,
                        )

                elif event_type == "ERROR":
                    finished = True
                    error_msg = str(payload)
                    with _state_lock:
                        _active_operation = None
                        _active_worker = None

                    _set_status_message(wb, "CodeStruct: Analysis submission failed.")
                    tkinter.messagebox.showerror(
                        "CodeStruct Analysis Error",
                        f"CodeStruct analysis failed:\n\n{error_msg}",
                        parent=wb,
                    )

            if not finished and not _is_shutting_down:
                wb.after(50, _drain_queue)

        wb.after(50, _drain_queue)
        thread = threading.Thread(
            target=worker.run,
            daemon=True,
            name=f"codestruct-worker-{resolved_path.name}",
        )
        thread.start()
        operation_started = True

    except Exception as exc:
        logger.exception("Error during CodeStruct operation setup: %s", exc)
        tkinter.messagebox.showerror(
            "CodeStruct Initialization Error",
            f"An unexpected error occurred while starting CodeStruct analysis:\n\n{exc}",
            parent=wb,
        )
    finally:
        if not operation_started:
            with _state_lock:
                _active_operation = None
                _active_worker = None


def on_workbench_shutdown(event: Any = None) -> None:
    """Handle Thonny shutdown gracefully, cancelling workers and suppressing UI."""
    wb = get_workbench()
    if (
        event is not None
        and getattr(event, "widget", None) is not None
        and wb is not None
    ):
        # Tkinter delivers <Destroy> events for all child widgets to root bindings.
        # Ignore destruction of child dialogs/frames/buttons unless the widget is the root workbench itself.
        if event.widget != wb:
            return

    global _is_shutting_down, _active_worker, _active_operation, _nav_poll_active
    _is_shutting_down = True
    _nav_poll_active = False  # stop navigation poll loop
    with _state_lock:
        if _active_worker is not None:
            _active_worker.cancel()
            _active_worker = None
        _active_operation = None

    _restore_files_pane(wb)


def _flush_nav_queue() -> None:
    """Discard all pending messages in _nav_queue.

    Called when a new session starts so that leftover STOP or NAVIGATE
    messages from the previous generation cannot affect the new poller.
    Safe to call from any thread; queue.Queue.get_nowait is thread-safe.
    """
    while True:
        try:
            _nav_queue.get_nowait()
        except queue.Empty:
            break


def _start_navigation_polling(wb: Any, backend_url: str) -> None:
    """Begin polling the backend for pending navigate-to-source commands.

    Called from the Tk main thread (via the _drain_queue callback) after a
    successful analysis submission. The poll loop runs every
    _NAV_POLL_INTERVAL_MS milliseconds using wb.after() so it stays on the Tk
    event thread and can safely call Thonny APIs.
    """
    global _nav_poll_active, _nav_poll_generation

    with _state_lock:
        token = _nav_session_token
        if not token:
            logger.debug("Navigation polling skipped: no session token available.")
            return

        _nav_poll_generation += 1
        generation = _nav_poll_generation
        _nav_poll_active = True

    # Discard any leftover messages from the previous session so that stale
    # STOP/NAVIGATE entries cannot affect the newly started poller.
    _flush_nav_queue()

    _poll_navigate(wb, backend_url.rstrip("/"), token, generation)


def _poll_navigate(
    wb: Any, backend_url: str, session_token: str, generation: int
) -> None:
    """Single poll cycle: check for a pending navigate command and execute it.

    Runs on the Tk main thread. Schedules itself again after
    _NAV_POLL_INTERVAL_MS unless the plugin is shutting down or generation is stale.
    """
    global _nav_poll_active, _nav_poll_in_flight

    # 1. Drain any pending messages from the background poll thread.
    # STOP messages carry the generation that produced them so a late error
    # from an old session cannot disable a newer active poller.
    while not _nav_queue.empty():
        try:
            msg_type, payload = _nav_queue.get_nowait()
        except queue.Empty:
            break
        if msg_type == "NAVIGATE":
            cmd_id, rel_path, line_no, col_no, gen, token = payload
            if gen != _nav_poll_generation or token != _nav_session_token:
                # Stale navigate from an old session — discard silently.
                logger.debug(
                    "Discarding stale NAVIGATE (gen %s, token %s); current gen %s.",
                    gen,
                    token,
                    _nav_poll_generation,
                )
                continue
            _execute_navigate(
                wb,
                backend_url,
                token,
                cmd_id,
                rel_path,
                line_no,
                col_no,
                gen,
            )
        elif msg_type == "STOP":
            # payload is the generation that issued this STOP.
            stop_gen = payload
            if stop_gen != _nav_poll_generation:
                # This STOP belongs to a previous session; ignore it.
                logger.debug(
                    "Discarding stale STOP (gen %s); current gen %s — new session stays active.",
                    stop_gen,
                    _nav_poll_generation,
                )
                continue
            _nav_poll_active = False
            return

    if (
        _is_shutting_down
        or not _nav_poll_active
        or generation != _nav_poll_generation
        or session_token != _nav_session_token
    ):
        return

    try:
        if not wb.winfo_exists():
            _nav_poll_active = False
            return
    except Exception:
        _nav_poll_active = False
        return

    # 2. Spawn a background poll thread if one is not already in flight
    if not _nav_poll_in_flight:
        _nav_poll_in_flight = True

        def _do_poll() -> None:
            """Blocking HTTP call executed in a daemon thread so Tk is not blocked."""
            global _nav_poll_active, _nav_poll_in_flight
            try:
                if (
                    _is_shutting_down
                    or not _nav_poll_active
                    or generation != _nav_poll_generation
                    or session_token != _nav_session_token
                ):
                    return

                encoded_token = urllib.parse.quote(session_token, safe="")
                poll_url = f"{backend_url}/api/v1/editor/navigate/pending?session_token={encoded_token}"
                req = urllib.request.Request(
                    poll_url,
                    headers={"Accept": "application/json"},
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                if (
                    _is_shutting_down
                    or generation != _nav_poll_generation
                    or session_token != _nav_session_token
                ):
                    return

                if data.get("has_command"):
                    relative_path = data.get("relative_path", "")
                    line = data.get("line", 1)
                    column = data.get("column") or 1
                    command_id = data.get("command_id", "")
                    if relative_path and line:
                        _nav_queue.put(
                            (
                                "NAVIGATE",
                                (
                                    command_id,
                                    relative_path,
                                    line,
                                    column,
                                    generation,
                                    session_token,
                                ),
                            )
                        )

                # Poll pending shell messages routed from CodeStruct workbench
                try:
                    shell_poll_url = f"{backend_url}/api/v1/editor/shell-messages/pending?session_token={encoded_token}"
                    shell_req = urllib.request.Request(
                        shell_poll_url,
                        headers={"Accept": "application/json"},
                        method="GET",
                    )
                    with urllib.request.urlopen(shell_req, timeout=5.0) as shell_resp:
                        shell_data = json.loads(shell_resp.read().decode("utf-8"))
                    messages = shell_data.get("messages", [])
                    if messages:
                        ack_ids = []
                        for msg in messages:
                            m_id = msg.get("id")
                            t_text = msg.get("text", "")
                            s_stream = msg.get("stream", "stdout")
                            if m_id:
                                ack_ids.append(m_id)
                            if t_text:
                                wb.after(
                                    0,
                                    lambda t=t_text, s=s_stream: print_to_thonny_shell(
                                        wb, t, s
                                    ),
                                )
                        if ack_ids:
                            ack_url = f"{backend_url}/api/v1/editor/shell-messages/acknowledge"
                            ack_payload = json.dumps(
                                {
                                    "session_token": session_token,
                                    "message_ids": ack_ids,
                                }
                            ).encode("utf-8")
                            ack_req = urllib.request.Request(
                                ack_url,
                                data=ack_payload,
                                headers={
                                    "Content-Type": "application/json",
                                    "Accept": "application/json",
                                },
                                method="POST",
                            )
                            with urllib.request.urlopen(ack_req, timeout=5.0):
                                pass
                except Exception as shell_poll_err:
                    logger.debug("Shell messages poll error: %s", shell_poll_err)
            except urllib.error.HTTPError as http_err:
                if http_err.code in (401, 403, 404, 410):
                    logger.info(
                        "Navigation session expired or invalid (%d); stopping polling.",
                        http_err.code,
                    )
                    with _state_lock:
                        if generation == _nav_poll_generation:
                            _nav_poll_active = False
                    # Include generation so _poll_navigate can discard stale STOPs.
                    _nav_queue.put(("STOP", generation))
                    return
                logger.debug("Navigation poll HTTP error: %s", http_err)
            except urllib.error.URLError as url_err:
                logger.debug(
                    "Navigation poll backend unavailable (%s); stopping poll loop.",
                    url_err,
                )
                with _state_lock:
                    if generation == _nav_poll_generation:
                        _nav_poll_active = False
                # Include generation so _poll_navigate can discard stale STOPs.
                _nav_queue.put(("STOP", generation))
                return
            except Exception as exc:
                logger.debug("Navigation poll error: %s", exc)
            finally:
                _nav_poll_in_flight = False

        t = threading.Thread(target=_do_poll, daemon=True, name="codestruct-nav-poll")
        t.start()

    # 3. Schedule next poll cycle on the Tk main thread
    if (
        not _is_shutting_down
        and _nav_poll_active
        and generation == _nav_poll_generation
        and session_token == _nav_session_token
    ):
        wb.after(
            _NAV_POLL_INTERVAL_MS,
            lambda: _poll_navigate(wb, backend_url, session_token, generation),
        )


def _execute_navigate(
    wb: Any,
    backend_url: str,
    session_token: str,
    command_id: str,
    relative_path: str,
    line: int,
    column: int,
    generation: int = 0,
) -> None:
    """Open the specified file at line in Thonny. Runs on the Tk main thread."""
    global \
        _nav_registered_file, \
        _nav_registered_file_resolved, \
        _nav_registered_root, \
        _nav_session_token

    # 1. Bind to the registered session's file/root and check generation
    if (
        _is_shutting_down
        or (_nav_registered_file is None and _nav_registered_root is None)
        or _nav_session_token != session_token
    ):
        logger.warning(
            "Navigation rejected: session mismatch or no file/root registered for session %s.",
            session_token,
        )
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="session_mismatch",
        )
        return

    if generation and generation != _nav_poll_generation:
        logger.warning(
            "Navigation rejected: stale generation (%s vs %s).",
            generation,
            _nav_poll_generation,
        )
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="stale_session",
        )
        return

    # 2. Scope validation: check relative path against registered root or file
    clean_slash = relative_path.replace("\\", "/").strip()
    raw_parts = [p for p in clean_slash.split("/") if p]
    if ".." in raw_parts:
        logger.warning(
            "Navigation rejected: path traversal in relative_path '%s'.", relative_path
        )
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="traversal_rejected",
        )
        return

    clean_rel = clean_slash
    while clean_rel.startswith("./"):
        clean_rel = clean_rel[2:]
    clean_rel = clean_rel.strip()

    if _nav_registered_root is not None:
        try:
            target_path = (_nav_registered_root / clean_rel).resolve(strict=True)
            if not target_path.is_relative_to(_nav_registered_root):
                raise ValueError("Target escapes registered root")
        except Exception as scope_err:
            logger.warning(
                "Navigation rejected: target '%s' invalid or escapes root '%s' (%s).",
                clean_rel,
                _nav_registered_root,
                scope_err,
            )
            _acknowledge_navigate(
                backend_url,
                session_token,
                command_id,
                status="failed",
                reason="scope_mismatch",
            )
            return
    elif _nav_registered_file is not None:
        if clean_rel != _nav_registered_file.name:
            logger.warning(
                "Navigation rejected: target '%s' does not match session-registered file '%s'.",
                clean_rel,
                _nav_registered_file.name,
            )
            _acknowledge_navigate(
                backend_url,
                session_token,
                command_id,
                status="failed",
                reason="scope_mismatch",
            )
            return
        target_path = _nav_registered_file
    else:
        return

    # 3. Canonical containment, path identity & symlink check (defense in depth)
    if _has_link_component(target_path.absolute()) or _is_link_or_reparse(target_path):
        logger.warning("Navigation rejected: target path contains a link or junction.")
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="symlink_rejected",
        )
        return

    try:
        resolved = target_path.resolve(strict=True)
    except (OSError, RuntimeError) as err:
        logger.warning("Navigation rejected: target file inaccessible (%s).", err)
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="file_inaccessible",
        )
        return

    if not resolved.is_file():
        logger.warning(
            "Navigation rejected: target is not a regular file (%s).", resolved
        )
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="not_regular_file",
        )
        return

    if _nav_registered_root is not None:
        if not resolved.is_relative_to(_nav_registered_root):
            logger.warning(
                "Navigation rejected: resolved file escapes registered root."
            )
            _acknowledge_navigate(
                backend_url,
                session_token,
                command_id,
                status="failed",
                reason="path_identity_mismatch",
            )
            return
    elif (
        _nav_registered_file_resolved is not None
        and resolved != _nav_registered_file_resolved
    ):
        logger.warning(
            "Navigation rejected: target resolved path '%s' does not match registered identity '%s'.",
            resolved,
            _nav_registered_file_resolved,
        )
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="path_identity_mismatch",
        )
        return

    if _is_link_or_reparse(resolved):
        logger.warning("Navigation rejected: resolved file is a link (%s).", resolved)
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="symlink_rejected",
        )
        return

    # 4. Open the exact file and cursor position on the Tk main thread
    # Thonny lines are 1-indexed; text widget columns (col_offset) are 0-indexed.
    col_offset = max(0, column - 1) if column is not None else 0
    try:
        editor_notebook = getattr(wb, "get_editor_notebook", lambda: None)()
        navigated = False
        cursor_placed = False
        if editor_notebook is not None:
            if hasattr(editor_notebook, "show_file_at_line"):
                editor_notebook.show_file_at_line(str(resolved), line, col_offset)
                navigated = True
                cursor_placed = True
            elif hasattr(editor_notebook, "show_file"):
                editor = editor_notebook.show_file(str(resolved))
                if editor is not None and hasattr(editor, "select_line"):
                    editor.select_line(line, col_offset)
                    cursor_placed = True
                navigated = True

        if not navigated:
            if hasattr(wb, "open_file"):
                wb.open_file(str(resolved))
                navigated = True
                cursor_placed = False
            else:
                logger.warning(
                    "Cannot navigate: Thonny API for opening files not found."
                )
                _acknowledge_navigate(
                    backend_url,
                    session_token,
                    command_id,
                    status="failed",
                    reason="missing_thonny_api",
                )
                return

        if cursor_placed:
            _set_status_message(wb, f"CodeStruct: Navigated to {resolved.name}:{line}")
            print_to_thonny_shell(
                wb,
                f'[CodeStruct] Navigated to File "{resolved}", line {line}, col {col_offset + 1}\n',
                stream="stdout",
            )
            _acknowledge_navigate(
                backend_url, session_token, command_id, status="delivered"
            )
        else:
            _set_status_message(
                wb,
                f"CodeStruct: Opened {resolved.name} (cursor positioning unavailable)",
            )
            print_to_thonny_shell(
                wb,
                f'[CodeStruct] Opened File "{resolved}" (cursor positioning unavailable)\n',
                stream="stdout",
            )
            _acknowledge_navigate(
                backend_url,
                session_token,
                command_id,
                status="failed",
                reason="cursor_unavailable",
            )
    except Exception as nav_exc:
        logger.warning("Navigation failed: %s", nav_exc)
        _set_status_message(
            wb, f"CodeStruct: Navigation failed ({type(nav_exc).__name__})"
        )
        print_to_thonny_shell(
            wb,
            f"[CodeStruct] Navigation failed for '{clean_rel}': {type(nav_exc).__name__}\n",
            stream="stderr",
        )
        _acknowledge_navigate(
            backend_url,
            session_token,
            command_id,
            status="failed",
            reason="navigation_error",
        )


def _acknowledge_navigate(
    backend_url: str,
    session_token: str,
    command_id: str,
    status: str = "delivered",
    reason: Optional[str] = None,
) -> None:
    """POST to /api/v1/editor/navigate/acknowledge to consume the command."""

    def _do_ack() -> None:
        try:
            ack_url = f"{backend_url}/api/v1/editor/navigate/acknowledge"
            body: dict[str, Any] = {
                "session_token": session_token,
                "command_id": command_id,
                "status": status,
            }
            if reason:
                body["reason"] = reason
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                ack_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5.0):
                pass
        except Exception as exc:
            logger.debug("Navigate acknowledge failed: %s", exc)

    t = threading.Thread(target=_do_ack, daemon=True, name="codestruct-nav-ack")
    t.start()


def _apply_windows_uri_compatibility_patch() -> None:
    """Ensure Windows file paths with forward slashes from Tkinter dialogs are recognized as local paths."""
    try:
        import thonny.misc_utils

        _orig_is_local_path = thonny.misc_utils.is_local_path

        def _patched_is_local_path(s: str) -> bool:
            if not s or s.startswith("<"):
                return False
            if thonny.misc_utils.is_legacy_remote_filename(s):
                return False
            if s.startswith("/"):
                return True
            if len(s) >= 3 and s[1] == ":" and s[2] in ("\\", "/"):
                return True
            return _orig_is_local_path(s)

        thonny.misc_utils.is_local_path = _patched_is_local_path
    except Exception as exc:
        logger.debug("Could not apply Windows URI compatibility patch: %s", exc)


def load_plugin() -> None:
    """Plugin entry point discovered and executed by Thonny."""
    _apply_windows_uri_compatibility_patch()

    wb = get_workbench()
    if wb is None:
        return

    # Primary workbench editor tab command
    wb.add_command(
        command_id="codestruct",
        menu_name="tools",
        command_label="CodeStruct",
        handler=open_codestruct_workbench,
        group=70,
        caption="CodeStruct Architecture Workbench",
    )

    # Integrate the single persistent unified Project & Symbol Explorer
    _integrate_persistent_explorer(wb)

    try:
        _bind_editor_notebook_events(wb)
    except Exception:
        pass
    try:
        wb.bind("WorkbenchOpen", lambda event: _integrate_persistent_explorer(wb), True)
    except Exception:
        pass
    try:
        wb.bind("WorkbenchClose", on_workbench_shutdown, True)
    except Exception:
        pass
    try:
        wb.bind("<Destroy>", on_workbench_shutdown, True)
    except Exception:
        pass
    logger.info("CodeStruct Thonny plugin loaded successfully")
