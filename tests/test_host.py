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


def test_validate_project_folder_user_home():
    home = Path.home()
    with pytest.raises(FolderValidationError, match="user profile directory"):
        validate_project_folder(home)
    if home.parent.exists() and home.parent != home:
        with pytest.raises(FolderValidationError, match="user profile directory"):
            validate_project_folder(home.parent)


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


def test_host_register_folder_api_success_and_disambiguation(tmp_path: Path):
    proj_a = tmp_path / "workspace1" / "my_project"
    proj_a.mkdir(parents=True)
    (proj_a / "module_a.py").write_text("def run(): pass\n", encoding="utf-8")

    proj_b = tmp_path / "workspace2" / "my_project"
    proj_b.mkdir(parents=True)
    (proj_b / "module_b.py").write_text("def execute(): pass\n", encoding="utf-8")

    app = create_app(Settings(authorized_roots={}))
    client = TestClient(app)

    # 1. Register proj_a
    resp_a = client.post("/api/v1/host/register-folder", json={"path": str(proj_a)})
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["root_id"] == "my_project"
    assert data_a["project_name"] == "my_project"
    assert data_a["path"] == str(proj_a.resolve())
    assert data_a["analysis_id"] is not None

    # Verify authorized_roots has proj_a
    assert (
        app.state.analysis_service.settings.authorized_roots["my_project"]
        == proj_a.resolve()
    )

    # Re-registering proj_a should return same root_id
    resp_a_repeat = client.post(
        "/api/v1/host/register-folder", json={"path": str(proj_a)}
    )
    assert resp_a_repeat.status_code == 200
    assert resp_a_repeat.json()["root_id"] == "my_project"

    # 2. Register proj_b (same folder name, different location) -> disambiguated root_id
    resp_b = client.post("/api/v1/host/register-folder", json={"path": str(proj_b)})
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["root_id"] == "my_project_1"
    assert data_b["project_name"] == "my_project"
    assert data_b["path"] == str(proj_b.resolve())
    assert data_b["analysis_id"] is not None

    assert (
        app.state.analysis_service.settings.authorized_roots["my_project_1"]
        == proj_b.resolve()
    )


def test_host_register_folder_api_validation_errors(tmp_path: Path):
    app = create_app(Settings(authorized_roots={}))
    client = TestClient(app)

    # Non-existent path
    resp_nonexistent = client.post(
        "/api/v1/host/register-folder",
        json={"path": str(tmp_path / "does_not_exist")},
    )
    assert resp_nonexistent.status_code == 400
    assert resp_nonexistent.json()["error"]["code"] == "INVALID_PROJECT_FOLDER"

    # File path instead of folder
    file_path = tmp_path / "file.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    resp_file = client.post(
        "/api/v1/host/register-folder",
        json={"path": str(file_path)},
    )
    assert resp_file.status_code == 400
    assert resp_file.json()["error"]["code"] == "INVALID_PROJECT_FOLDER"


def test_host_register_folder_api_static_non_execution(tmp_path: Path):
    """Verify that source code in the registered folder is NOT executed."""
    hostile_dir = tmp_path / "hostile_registered_proj"
    hostile_dir.mkdir()
    (hostile_dir / "exploit.py").write_text(
        "raise RuntimeError('EXECUTED_REGISTER_FOLDER_DANGER')\n",
        encoding="utf-8",
    )

    app = create_app(Settings(authorized_roots={}))
    client = TestClient(app)

    resp = client.post(
        "/api/v1/host/register-folder",
        json={"path": str(hostile_dir)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_id"] is not None


def test_host_register_folder_token_auth(tmp_path: Path):
    proj_dir = tmp_path / "token_proj"
    proj_dir.mkdir()

    with mock.patch.dict(os.environ, {"CODESTRUCT_HOST_TOKEN": "token_xyz_999"}):
        app = create_app(Settings(authorized_roots={}))
        client = TestClient(app)

        # Missing token -> 403
        resp_no_token = client.post(
            "/api/v1/host/register-folder",
            json={"path": str(proj_dir)},
        )
        assert resp_no_token.status_code == 403

        # Wrong token -> 403
        resp_bad_token = client.post(
            "/api/v1/host/register-folder",
            json={"path": str(proj_dir)},
            headers={"X-CodeStruct-Host-Token": "bad_token"},
        )
        assert resp_bad_token.status_code == 403

        # Correct token -> 200
        resp_ok = client.post(
            "/api/v1/host/register-folder",
            json={"path": str(proj_dir)},
            headers={"X-CodeStruct-Host-Token": "token_xyz_999"},
        )
        assert resp_ok.status_code == 200
        assert resp_ok.json()["root_id"] is not None
