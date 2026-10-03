"""
CodeStruct integration plugin for Thonny IDE.
Enables analyzing Python projects directly from Thonny and viewing results in CodeStruct.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import queue
import stat as _stat_module
import threading
import tkinter.filedialog
import tkinter.messagebox
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Optional, Tuple

try:
    from thonny import get_workbench
except ImportError:
    # Allow importing and testing outside of full Thonny runtime
    def get_workbench() -> Any:
        return None


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
    global _nav_registered_file, _nav_registered_file_resolved, _nav_session_token

    # 1. Bind to the registered session's file and check generation
    if (
        _is_shutting_down
        or _nav_registered_file is None
        or _nav_session_token != session_token
    ):
        logger.warning(
            "Navigation rejected: session mismatch or no file registered for session %s.",
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

    # 2. Scope validation: check relative path against registered file
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

    # 3. Canonical containment, path identity & symlink check (defense in depth)
    target_path = _nav_registered_file
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

    if (
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
            _acknowledge_navigate(
                backend_url, session_token, command_id, status="delivered"
            )
        else:
            _set_status_message(
                wb,
                f"CodeStruct: Opened {resolved.name} (cursor positioning unavailable)",
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

    wb.add_command(
        command_id="codestruct_analyze",
        menu_name="tools",
        command_label="Analyze with CodeStruct",
        handler=analyze_current_project,
        group=70,
        caption="Analyze with CodeStruct",
    )

    try:
        wb.bind("WorkbenchClose", on_workbench_shutdown, True)
    except Exception:
        pass
    try:
        wb.bind("<Destroy>", on_workbench_shutdown, True)
    except Exception:
        pass

    logger.info("CodeStruct Thonny plugin loaded successfully")
