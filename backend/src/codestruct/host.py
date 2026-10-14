"""Windows host bridge and folder selection capabilities."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Test hook to allow headless test automation without GUI dialogs
_FOLDER_CHOOSER_HOOK: Callable[[str], str | None] | None = None

# Known Windows system directories that must not be registered as project roots
FORBIDDEN_WINDOWS_DIR_NAMES = {
    "windows",
    "winnt",
    "system32",
    "program files",
    "program files (x86)",
    "programdata",
    "$recycle.bin",
    "system volume information",
}


class FolderValidationError(ValueError):
    """Raised when a selected folder path is invalid or prohibited."""


def set_folder_chooser_hook(hook: Callable[[str], str | None] | None) -> None:
    """Set or clear a custom folder chooser hook (primarily for unit testing)."""
    global _FOLDER_CHOOSER_HOOK
    _FOLDER_CHOOSER_HOOK = hook


def choose_folder_dialog(title: str = "Select Project Folder") -> str | None:
    """Invoke the native Windows folder picker dialog.

    Returns the canonical string path if selected, or None if cancelled.
    """
    if _FOLDER_CHOOSER_HOOK is not None:
        return _FOLDER_CHOOSER_HOOK(title)

    env_mock = os.environ.get("CODESTRUCT_MOCK_CHOOSE_FOLDER")
    if env_mock:
        return env_mock

    # On Windows, invoke PowerShell to open the native FolderBrowserDialog
    if sys.platform == "win32":
        try:
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                f"$f.Description = '{title}'; "
                "$f.ShowNewFolderButton = $false; "
                "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
                "    Write-Output $f.SelectedPath "
                "}"
            )
            ps_exe = shutil.which("powershell.exe") or "powershell.exe"
            result = subprocess.run(  # noqa: S603
                [ps_exe, "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            out = result.stdout.strip()
            return out if out else None
        except Exception as exc:
            logger.warning("PowerShell folder browser dialog failed: %s", exc)

    # Fallback to tkinter if available
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title=title)
        root.destroy()
        return selected if selected else None
    except Exception as exc:
        logger.warning("Tkinter folder browser dialog fallback failed: %s", exc)
        return None


def validate_project_folder(folder_path: str | Path) -> Path:
    """Validate and canonicalize a project root directory path.

    Enforces:
    - Path must exist and be a directory.
    - Path must not be a filesystem root (e.g. C:\\ or /).
    - Path must not be a system/forbidden OS directory.
    - Path must resolve to a canonical real path without symlink escape.
    """
    try:
        path = Path(folder_path).resolve()
    except Exception as exc:
        raise FolderValidationError(f"Invalid path format: {exc}") from exc

    if not path.exists():
        raise FolderValidationError(f"The path '{path}' does not exist.")

    if not path.is_dir():
        raise FolderValidationError(f"The path '{path}' is not a directory.")

    # Rejection of filesystem roots (e.g., C:\, D:\, /)
    if path == path.parent:
        raise FolderValidationError(
            f"The drive root '{path}' cannot be registered as a project folder. "
            "Please select a specific project directory."
        )

    # Rejection of Windows system directories
    parts_lower = [p.lower() for p in path.parts]
    for forbidden in FORBIDDEN_WINDOWS_DIR_NAMES:
        if forbidden in parts_lower:
            raise FolderValidationError(
                f"The directory '{path}' contains forbidden system folder '{forbidden}' "
                "and cannot be analyzed."
            )

    return path
