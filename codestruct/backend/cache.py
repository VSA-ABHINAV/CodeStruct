"""Persistent incremental cache for CodeStruct (Phase 14 & Windows Packaging)."""
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from backend.config import get_cache_dir


def _cache_path(project_root: str) -> Path:
    abs_root = Path(project_root).resolve()
    fingerprint = hashlib.sha256(str(abs_root).encode("utf-8")).hexdigest()
    cache_dir = get_cache_dir()
    return cache_dir / f"{fingerprint}.json"


def load_cache(project_root: str) -> Dict[str, Any]:
    """Load cached project analysis data from disk."""
    path = _cache_path(project_root)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(project_root: str, data: Dict[str, Any]) -> None:
    """Save project analysis cache data to disk as JSON."""
    path = _cache_path(project_root)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_file_cache_key(file_path: Path) -> List[float]:
    """Return [mtime, size] as JSON-compatible list."""
    stat = file_path.stat()
    return [float(stat.st_mtime), int(stat.st_size)]
