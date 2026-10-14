"""Tests for Phase 2 Windows desktop host bridge and folder selection."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest
from codestruct.api.app import create_app
from codestruct.host import (
    FolderValidationError,
    choose_folder_dialog,
    set_folder_chooser_hook,
    validate_project_folder,
)
from codestruct.settings import Settings
from fastapi.testclient import TestClient


def test_validate_project_folder_success(tmp_path: Path):
    proj_dir = tmp_path / "valid_project"
    proj_dir.mkdir()
    validated = validate_project_folder(proj_dir)
    assert validated == proj_dir.resolve()
    assert validated.is_dir()


def test_validate_project_folder_nonexistent(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist"
    with pytest.raises(FolderValidationError, match="does not exist"):
        validate_project_folder(nonexistent)


def test_validate_project_folder_is_file(tmp_path: Path):
    file_path = tmp_path / "single_file.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(FolderValidationError, match="not a directory"):
        validate_project_folder(file_path)


def test_validate_project_folder_root_drive():
    root = Path(Path().resolve().anchor)
    with pytest.raises(FolderValidationError, match="drive root"):
        validate_project_folder(root)


def test_validate_project_folder_forbidden_system_dir():
    # Test checking forbidden system folders
    fake_win = Path("C:/Windows")
    # Even if mocked or checked:
    if fake_win.exists():
        with pytest.raises(FolderValidationError, match="forbidden system folder"):
            validate_project_folder(fake_win)


def test_choose_folder_dialog_hook_and_env():
    # Hook takes precedence
    set_folder_chooser_hook(lambda _title: "/custom/hook/path")
    try:
        assert choose_folder_dialog() == "/custom/hook/path"
    finally:
        set_folder_chooser_hook(None)

    # Env var fallback
    with mock.patch.dict(os.environ, {"CODESTRUCT_MOCK_CHOOSE_FOLDER": "/env/path"}):
        assert choose_folder_dialog() == "/env/path"


def test_host_choose_folder_api_cancelled(tmp_path: Path):
    app = create_app(Settings(authorized_roots={}))
    client = TestClient(app)

    set_folder_chooser_hook(lambda _title: None)
    try:
        resp = client.post("/api/v1/host/choose-folder")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled"] is True
        assert data["root_id"] is None
        assert data["analysis_id"] is None
    finally:
        set_folder_chooser_hook(None)


def test_host_choose_folder_api_success_and_auto_analysis(tmp_path: Path):
    proj_dir = tmp_path / "my_desktop_project"
    proj_dir.mkdir()
    (proj_dir / "app.py").write_text("class Core:\n    pass\n", encoding="utf-8")

    app = create_app(Settings(authorized_roots={}))
    client = TestClient(app)

    set_folder_chooser_hook(lambda _title: str(proj_dir))
    try:
        resp = client.post("/api/v1/host/choose-folder")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled"] is False
        assert data["project_name"] == "my_desktop_project"
        assert data["root_id"] is not None
        assert data["analysis_id"] is not None
        assert data["path"] == str(proj_dir.resolve())

        # Verify the root is now registered in authorized_roots
        assert data["root_id"] in app.state.analysis_service.settings.authorized_roots
        # Verify initial analysis job exists
        job = app.state.analysis_service.get(data["analysis_id"])
        assert job is not None
        assert job.root_id == data["root_id"]
    finally:
        set_folder_chooser_hook(None)


def test_host_choose_folder_api_static_non_execution(tmp_path: Path):
    """Verify that source code in the opened folder is NOT executed."""
    hostile_dir = tmp_path / "hostile_project"
    hostile_dir.mkdir()
    # If code were imported or exec'd, this would raise or fail
    (hostile_dir / "danger.py").write_text(
        "import sys\nraise RuntimeError('SOURCE_CODE_EXECUTED_DANGER')\n",
        encoding="utf-8",
    )

    app = create_app(Settings(authorized_roots={}))
    client = TestClient(app)

    set_folder_chooser_hook(lambda _title: str(hostile_dir))
    try:
        resp = client.post("/api/v1/host/choose-folder")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled"] is False
        assert data["analysis_id"] is not None
    finally:
        set_folder_chooser_hook(None)


def test_host_choose_folder_api_token_protection(tmp_path: Path):
    """Verify that when host authentication token is configured, requests without it are rejected."""
    proj_dir = tmp_path / "secure_proj"
    proj_dir.mkdir()

    with mock.patch.dict(os.environ, {"CODESTRUCT_HOST_TOKEN": "secret_token_123"}):
        app = create_app(Settings(authorized_roots={}))
        client = TestClient(app)

        set_folder_chooser_hook(lambda _title: str(proj_dir))
        try:
            # Request without token -> 403
            resp = client.post("/api/v1/host/choose-folder")
            assert resp.status_code == 403
            assert resp.json()["error"]["code"] == "HOST_AUTHENTICATION_REQUIRED"

            # Request with wrong token -> 403
            resp_bad = client.post(
                "/api/v1/host/choose-folder",
                headers={"X-CodeStruct-Host-Token": "wrong"},
            )
            assert resp_bad.status_code == 403

            # Request with valid token -> 200
            resp_good = client.post(
                "/api/v1/host/choose-folder",
                headers={"X-CodeStruct-Host-Token": "secret_token_123"},
            )
            assert resp_good.status_code == 200
            assert resp_good.json()["cancelled"] is False
        finally:
            set_folder_chooser_hook(None)
