"""First-Run Setup Wizard, System Readiness Checks & Optional Ollama Setup."""

import ctypes
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from backend.config import (
    get_cache_dir,
    get_config_path,
    load_config,
    save_config,
)
from backend.qwen_client import check_ollama_connection

# Background task state for long-running Ollama install / model pull
_TASK_LOCK = threading.Lock()
_TASK_STATE: Dict[str, Any] = {
    "status": "idle",  # idle | running | completed | error
    "action": None,
    "message": "",
    "logs": [],
}


def _set_task_state(
    status: str,
    action: Optional[str] = None,
    message: str = "",
    log_line: Optional[str] = None,
    reset_logs: bool = False,
) -> None:
    with _TASK_LOCK:
        _TASK_STATE["status"] = status
        if action is not None:
            _TASK_STATE["action"] = action
        _TASK_STATE["message"] = message
        if reset_logs:
            _TASK_STATE["logs"] = []
        if log_line:
            _TASK_STATE["logs"].append(log_line)
            if len(_TASK_STATE["logs"]) > 100:
                _TASK_STATE["logs"] = _TASK_STATE["logs"][-100:]


def get_task_state() -> Dict[str, Any]:
    with _TASK_LOCK:
        return {
            "status": _TASK_STATE["status"],
            "action": _TASK_STATE["action"],
            "message": _TASK_STATE["message"],
            "logs": list(_TASK_STATE["logs"]),
        }


def get_system_ram_gb() -> Dict[str, float]:
    """Return total and available physical RAM in GB."""
    if sys.platform == "win32":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            total_gb = round(stat.ullTotalPhys / (1024 ** 3), 2)
            avail_gb = round(stat.ullAvailPhys / (1024 ** 3), 2)
            return {"total_gb": total_gb, "available_gb": avail_gb}
        except Exception:
            pass
    return {"total_gb": 0.0, "available_gb": 0.0}


def get_disk_free_gb(target_path: Path) -> float:
    """Return free disk space in GB for the drive/mount containing target_path."""
    try:
        probe = target_path
        while not probe.exists() and probe.parent != probe:
            probe = probe.parent
        usage = shutil.disk_usage(str(probe))
        return round(usage.free / (1024 ** 3), 2)
    except Exception:
        return 0.0


def check_webview2_installed() -> Dict[str, Any]:
    """Check if Microsoft Edge WebView2 Runtime is installed on Windows."""
    if sys.platform != "win32":
        return {"installed": True, "version": "native-webkit"}
    try:
        import winreg

        guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        locations = [
            (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{guid}"),
            (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}"),
            (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{guid}"),
        ]
        for hive, subkey in locations:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    ver, _ = winreg.QueryValueEx(key, "pv")
                    if ver and str(ver) != "0.0.0.0":
                        return {"installed": True, "version": str(ver)}
            except FileNotFoundError:
                continue
    except Exception:
        pass
    return {"installed": False, "version": None}


def find_ollama_executable() -> Optional[str]:
    """Locate ollama executable on PATH or standard Windows install paths."""
    found = shutil.which("ollama")
    if found:
        return found
    if sys.platform == "win32":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Ollama" / "ollama.exe",
        ]
        for c in candidates:
            if c.is_file():
                return str(c)
    return None


def check_ollama_model_pulled(model_name: str = "qwen2.5-coder:3b", host: str = "http://localhost:11434") -> bool:
    """Return True if Ollama is running and has model_name pulled."""
    try:
        r = requests.get(f"{host.rstrip('/')}/api/tags", timeout=1.5)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            return any(m == model_name or m.startswith(model_name + ":") for m in models)
    except Exception:
        pass
    return False


def run_system_checks(custom_models_dir: Optional[str] = None) -> Dict[str, Any]:
    """Execute comprehensive hardware, OS, WebView2, storage, and Ollama checks."""
    cfg = load_config()
    models_dir_str = custom_models_dir or cfg.get("ollama_models_dir") or str(Path.home() / ".ollama" / "models")
    models_dir = Path(models_dir_str)
    cache_dir = get_cache_dir()

    ram = get_system_ram_gb()
    cache_free_gb = get_disk_free_gb(cache_dir)
    models_free_gb = get_disk_free_gb(models_dir)
    wv2 = check_webview2_installed()
    ollama_exe = find_ollama_executable()
    ollama_running = check_ollama_connection(timeout=1.0)
    target_model = cfg.get("ollama_model", "qwen2.5-coder:3b")
    model_pulled = check_ollama_model_pulled(target_model) if ollama_running else False

    winget_available = bool(shutil.which("winget")) if sys.platform == "win32" else False

    return {
        "os": platform.platform(),
        "arch": platform.machine(),
        "frozen_exe": bool(getattr(sys, "frozen", False)),
        "ram_total_gb": ram["total_gb"],
        "ram_available_gb": ram["available_gb"],
        "ram_ok_static": ram["total_gb"] == 0.0 or ram["total_gb"] >= 2.0,
        "ram_ok_ai": ram["total_gb"] == 0.0 or ram["total_gb"] >= 7.5 or ram["available_gb"] >= 4.0,
        "disk_cache_free_gb": cache_free_gb,
        "disk_models_free_gb": models_free_gb,
        "disk_ok_ai": models_free_gb >= 2.5,
        "webview2_installed": wv2["installed"],
        "webview2_version": wv2["version"],
        "ollama_installed": ollama_exe is not None,
        "ollama_exe": ollama_exe,
        "ollama_running": ollama_running,
        "model_pulled": model_pulled,
        "target_model": target_model,
        "winget_available": winget_available,
        "config_path": str(get_config_path()),
        "cache_dir": str(cache_dir),
        "models_dir": str(models_dir),
    }


def start_ollama_install_task() -> Dict[str, Any]:
    """Attempt silent/background Ollama installation via winget or open official download page."""
    with _TASK_LOCK:
        if _TASK_STATE["status"] == "running":
            return {"started": False, "message": "Another setup task is already running."}

    def _worker():
        _set_task_state("running", action="install_ollama", message="Checking package manager (winget)...", reset_logs=True)
        winget = shutil.which("winget")
        if sys.platform == "win32" and winget:
            try:
                _set_task_state(
                    "running",
                    message="Installing Ollama via winget (this may take 1-2 minutes)...",
                    log_line="> winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements",
                )
                flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
                proc = subprocess.Popen(
                    [
                        winget,
                        "install",
                        "--id",
                        "Ollama.Ollama",
                        "-e",
                        "--accept-package-agreements",
                        "--accept-source-agreements",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=flags,
                )
                if proc.stdout:
                    for line in proc.stdout:
                        clean = line.strip()
                        if clean:
                            _set_task_state("running", message="Installing Ollama via winget...", log_line=clean)
                rc = proc.wait()
                if rc == 0 or find_ollama_executable():
                    _set_task_state("completed", message="Ollama installed successfully!", log_line="Ollama binary verified.")
                    return
                else:
                    _set_task_state(
                        "error",
                        message=f"winget exited with code {rc}. Opening official Ollama download page...",
                        log_line=f"winget failed with exit code {rc}",
                    )
                    webbrowser.open("https://ollama.com/download/windows")
                    return
            except Exception as e:
                _set_task_state("error", message=f"Install failed: {e}", log_line=str(e))
                return
        else:
            webbrowser.open("https://ollama.com/download")
            _set_task_state(
                "completed",
                message="Opened https://ollama.com/download in your browser. Install Ollama, then click Re-check.",
                log_line="Launched browser to https://ollama.com/download",
            )

    threading.Thread(target=_worker, daemon=True).start()
    return {"started": True, "message": "Ollama installation started."}


def start_ollama_pull_task(models_dir: str, model_name: str = "qwen2.5-coder:3b") -> Dict[str, Any]:
    """Start Ollama daemon (if needed) with custom OLLAMA_MODELS path and pull the LLM."""
    with _TASK_LOCK:
        if _TASK_STATE["status"] == "running":
            return {"started": False, "message": "Another setup task is already running."}

    target_dir = Path(models_dir).expanduser().resolve()

    def _worker():
        _set_task_state(
            "running",
            action="pull_model",
            message=f"Preparing custom model directory: {target_dir}",
            reset_logs=True,
        )
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            _set_task_state("error", message=f"Cannot create model directory '{target_dir}': {e}", log_line=str(e))
            return

        ollama_exe = find_ollama_executable()
        if not ollama_exe:
            _set_task_state("error", message="Ollama CLI not found. Please install Ollama first.", log_line="ollama executable not found.")
            return

        env = os.environ.copy()
        env["OLLAMA_MODELS"] = str(target_dir)
        os.environ["OLLAMA_MODELS"] = str(target_dir)

        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

        # Ensure ollama serve is running
        if not check_ollama_connection(timeout=1.0):
            _set_task_state("running", message="Starting Ollama service daemon with custom model path...", log_line=f"OLLAMA_MODELS={target_dir}")
            try:
                subprocess.Popen(
                    [ollama_exe, "serve"],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
                for _ in range(20):
                    if check_ollama_connection(timeout=0.5):
                        break
                    time.sleep(0.5)
            except Exception as e:
                _set_task_state("error", message=f"Failed to start Ollama daemon: {e}", log_line=str(e))
                return

        if not check_ollama_connection(timeout=1.5):
            _set_task_state("error", message="Ollama daemon did not respond on port 11434.", log_line="Timeout waiting for Ollama API.")
            return

        _set_task_state(
            "running",
            message=f"Downloading {model_name} (~2.0 GB)... Please wait.",
            log_line=f"> ollama pull {model_name} (OLLAMA_MODELS={target_dir})",
        )
        try:
            proc = subprocess.Popen(
                [ollama_exe, "pull", model_name],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=flags,
            )
            if proc.stdout:
                for line in proc.stdout:
                    clean = line.strip()
                    if clean:
                        _set_task_state("running", message=f"Pulling {model_name}...", log_line=clean)
            rc = proc.wait()
            if rc == 0:
                save_config({
                    "ai_enabled": True,
                    "ollama_models_dir": str(target_dir),
                    "ollama_model": model_name,
                })
                _set_task_state("completed", message=f"Model '{model_name}' pulled and saved to {target_dir}!", log_line="Pull completed successfully.")
            else:
                _set_task_state("error", message=f"ollama pull exited with code {rc}", log_line=f"Exit code {rc}")
        except Exception as e:
            _set_task_state("error", message=f"Error pulling model: {e}", log_line=str(e))

    threading.Thread(target=_worker, daemon=True).start()
    return {"started": True, "message": f"Started pulling {model_name}."}

