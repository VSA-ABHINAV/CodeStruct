"""Runtime configuration, AppData persistence, LocalAppData caching, and PyInstaller asset resolution."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


def is_frozen() -> bool:
    """Return True if running inside a PyInstaller frozen bundle."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def get_resource_base() -> Path:
    """Return base directory for bundled assets (frontend, sample_project).
    
    Uses sys._MEIPASS when running as a PyInstaller executable,
    otherwise resolves to the codestruct package root directory.
    """
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def get_app_data_dir() -> Path:
    """Return persistent user config directory under %APPDATA%\\CodeStruct on Windows."""
    app_data = os.environ.get("APPDATA")
    if app_data:
        path = Path(app_data) / "CodeStruct"
    elif sys.platform == "win32":
        path = Path.home() / "AppData" / "Roaming" / "CodeStruct"
    else:
        path = Path.home() / ".config" / "codestruct"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    """Return full path to persisted configuration JSON file in %APPDATA%."""
    return get_app_data_dir() / "config.json"


def get_cache_dir() -> Path:
    """Return persistent incremental AST cache directory under %LOCALAPPDATA%\\CodeStruct\\cache."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        path = Path(local_app_data) / "CodeStruct" / "cache"
    elif sys.platform == "win32":
        path = Path.home() / "AppData" / "Local" / "CodeStruct" / "cache"
    else:
        path = Path.home() / ".local" / "share" / "codestruct" / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    """Return directory for application runtime logs under %LOCALAPPDATA%\\CodeStruct\\logs."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        path = Path(local_app_data) / "CodeStruct" / "logs"
    elif sys.platform == "win32":
        path = Path.home() / "AppData" / "Local" / "CodeStruct" / "logs"
    else:
        path = Path.home() / ".local" / "share" / "codestruct" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_ollama_models_dir() -> str:
    """Return default Ollama models directory path."""
    env_dir = os.environ.get("OLLAMA_MODELS")
    if env_dir:
        return env_dir
    return str(Path.home() / ".ollama" / "models")


def default_config() -> Dict[str, Any]:
    """Return default application configuration dictionary."""
    return {
        "first_run_completed": False,
        "ai_enabled": False,
        "ollama_host": "http://localhost:11434",
        "ollama_model": "qwen2.5-coder:3b",
        "ollama_models_dir": get_default_ollama_models_dir(),
    }


def load_config() -> Dict[str, Any]:
    """Load persisted configuration from %APPDATA%\\CodeStruct\\config.json."""
    cfg_path = get_config_path()
    defaults = default_config()
    if not cfg_path.exists():
        return defaults
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            return defaults
        merged = {**defaults, **loaded}
        return merged
    except Exception:
        return defaults


def save_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge updates into existing config and persist atomically to %APPDATA%."""
    current = load_config()
    current.update(updates)
    cfg_path = get_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cfg_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    tmp_path.replace(cfg_path)
    return current

