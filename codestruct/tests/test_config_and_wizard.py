"""Tests for %APPDATA% Config, %LOCALAPPDATA% Cache, PyInstaller Asset Resolution & Setup Wizard."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

TESTS_DIR = Path(__file__).resolve().parent
CODESTRUCT_DIR = TESTS_DIR.parent
if str(CODESTRUCT_DIR) not in sys.path:
    sys.path.insert(0, str(CODESTRUCT_DIR))

from backend.cache import load_cache, save_cache
from backend.config import (
    get_app_data_dir,
    get_cache_dir,
    get_config_path,
    get_resource_base,
    load_config,
    save_config,
)
from backend.main import app
from backend.wizard import run_system_checks


@pytest.fixture
def isolated_appdata(tmp_path, monkeypatch):
    """Isolate %APPDATA% and %LOCALAPPDATA% to tmp_path so real user config isn't touched."""
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    roaming.mkdir()
    local.mkdir()
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    return roaming, local


def test_appdata_config_persistence(isolated_appdata):
    roaming, _ = isolated_appdata
    cfg_path = get_config_path()
    assert cfg_path == roaming / "CodeStruct" / "config.json"

    # Initially returns defaults with first_run_completed == False
    initial = load_config()
    assert initial["first_run_completed"] is False
    assert initial["ai_enabled"] is False

    # Save custom configuration
    custom_models = str(roaming / "CustomModels")
    saved = save_config({
        "first_run_completed": True,
        "ai_enabled": True,
        "ollama_models_dir": custom_models,
    })
    assert saved["first_run_completed"] is True
    assert saved["ai_enabled"] is True
    assert saved["ollama_models_dir"] == custom_models
    assert cfg_path.is_file()

    # Reload from disk
    reloaded = load_config()
    assert reloaded["first_run_completed"] is True
    assert reloaded["ollama_models_dir"] == custom_models


def test_localappdata_cache_directory(isolated_appdata, tmp_path):
    _, local = isolated_appdata
    cache_dir = get_cache_dir()
    assert cache_dir == local / "CodeStruct" / "cache"
    assert cache_dir.is_dir()

    fake_proj = tmp_path / "demo_proj"
    fake_proj.mkdir()
    save_cache(str(fake_proj), {"hello.py": {"mtime": 1.0, "nodes": []}})
    loaded = load_cache(str(fake_proj))
    assert "hello.py" in loaded
    # Confirm cache file sits under %LOCALAPPDATA%\CodeStruct\cache
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1


def test_pyinstaller_meipass_resource_resolution(tmp_path, monkeypatch):
    meipass_dir = tmp_path / "_MEI12345"
    meipass_dir.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)

    assert get_resource_base() == meipass_dir


def test_system_checks_structure(isolated_appdata, tmp_path):
    custom_models = tmp_path / "OllamaCustom"
    custom_models.mkdir()
    checks = run_system_checks(custom_models_dir=str(custom_models))

    assert "os" in checks
    assert "ram_total_gb" in checks
    assert "disk_cache_free_gb" in checks
    assert "disk_models_free_gb" in checks
    assert "webview2_installed" in checks
    assert "ollama_installed" in checks
    assert "ollama_running" in checks
    assert "model_pulled" in checks
    assert checks["models_dir"] == str(custom_models)
    assert "CodeStruct" in checks["config_path"]
    assert "CodeStruct" in checks["cache_dir"]


def test_wizard_endpoints(isolated_appdata, tmp_path):
    custom_models = tmp_path / "CustomModels"
    with TestClient(app) as client:
        # 1. GET /api/wizard/status
        res = client.get(f"/api/wizard/status?models_dir={custom_models}")
        assert res.status_code == 200
        data = res.json()
        assert data["config"]["first_run_completed"] is False
        assert "system_checks" in data

        # 2. POST /api/wizard/complete
        res2 = client.post("/api/wizard/complete", json={
            "ai_enabled": True,
            "ollama_models_dir": str(custom_models),
            "ollama_model": "qwen2.5-coder:3b",
        })
        assert res2.status_code == 200
        body2 = res2.json()
        assert body2["saved"] is True
        assert body2["config"]["first_run_completed"] is True
        assert body2["config"]["ai_enabled"] is True
        assert body2["config"]["ollama_models_dir"] == str(custom_models.resolve())
        assert custom_models.is_dir()
