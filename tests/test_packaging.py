from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

from codestruct import __version__
from codestruct.cli import _loopback, _port, doctor, parser, serve
from codestruct.settings import Settings
from codestruct.storage.migrations import migrate
from codestruct.storage.schema import SCHEMA_VERSION
from fastapi.testclient import TestClient


def _settings(root: Path) -> Settings:
    return Settings(
        authorized_roots={"fixture": root},
        database_path=None,
        max_concurrent_jobs=1,
        max_queued_jobs=1,
    )


def test_authoritative_version_and_console_parser() -> None:
    repository = Path(__file__).resolve().parents[1]
    about = repository / "backend" / "src" / "codestruct" / "__about__.py"
    vite = repository / "frontend" / "vite.config.js"
    pyproject = repository / "pyproject.toml"

    assert __version__ == "0.1.0.dev0"
    assert f'__version__ = "{__version__}"' in about.read_text("utf-8")
    assert "codestruct.__about__.__version__" in pyproject.read_text("utf-8")
    assert "version.config.js" in vite.read_text("utf-8")
    assert "__about__.py" in repository.joinpath(
        "frontend/version.config.js"
    ).read_text("utf-8")
    assert parser().parse_args(["serve"]).host == "127.0.0.1"
    assert parser().parse_args(["doctor"]).port == 8000
    assert _port("65535") == 65535
    assert _loopback("localhost")
    assert not _loopback("example.com")


def test_doctor_and_serve_fail_safely(tmp_path: Path, monkeypatch, capsys) -> None:
    cli_module = importlib.import_module("codestruct.cli")
    settings = _settings(tmp_path)
    monkeypatch.setattr(cli_module, "_assets_ready", lambda: True)
    monkeypatch.setattr(cli_module, "load_settings", lambda: settings)
    monkeypatch.setattr(
        cli_module.importlib.metadata, "version", lambda _name: __version__
    )
    assert doctor("127.0.0.1", 0) == 0
    assert str(tmp_path) not in capsys.readouterr().out

    def invalid_settings():
        raise ValueError("private configuration detail")

    monkeypatch.setattr(cli_module, "load_settings", invalid_settings)
    assert doctor("127.0.0.1", 0) == 1
    doctor_failure = capsys.readouterr().out
    assert "FAIL configuration" in doctor_failure
    assert "FAIL database" in doctor_failure
    assert "private configuration detail" not in doctor_failure
    assert serve("127.0.0.1", 8000, "info") == 2
    failure = capsys.readouterr().err
    assert "configuration is invalid" in failure
    assert "private configuration detail" not in failure

    monkeypatch.setattr(cli_module, "load_settings", lambda: settings)
    uvicorn = importlib.import_module("uvicorn")
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    assert serve("example.com", 8000, "warning") == 0
    warning = capsys.readouterr().err
    assert "no built-in authentication or TLS" in warning


def test_health_and_missing_frontend_keep_legacy_root(
    tmp_path: Path, monkeypatch
) -> None:
    app_module = importlib.import_module("codestruct.api.app")
    empty = tmp_path / "empty-web"
    empty.mkdir()
    monkeypatch.setattr(app_module, "frontend_directory", lambda: empty)
    app = app_module.create_app(_settings(tmp_path))

    with TestClient(app) as client:
        assert client.get("/").json() == {"message": "CodeStruct Backend is Working!"}
        assert client.get("/health/live").json() == {
            "status": "live",
            "version": __version__,
        }
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/v1/version").json()["version"] == __version__
        missing = client.get("/app")
        assert missing.status_code == 503
        assert "not available" in missing.json()["error"]


def test_bundled_static_assets_spa_and_api_precedence(
    tmp_path: Path, monkeypatch
) -> None:
    app_module = importlib.import_module("codestruct.api.app")
    web_module = importlib.import_module("codestruct.web")
    frontend = tmp_path / "web"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    frontend.joinpath("index.html").write_text(
        "<!doctype html><title>CodeStruct release test</title>", encoding="utf-8"
    )
    assets.joinpath("app-abcdef.js").write_text(
        "console.log('release test')", encoding="utf-8"
    )
    monkeypatch.setattr(app_module, "frontend_directory", lambda: frontend)
    monkeypatch.setattr(web_module, "frontend_directory", lambda: frontend)
    app = app_module.create_app(_settings(tmp_path))

    with TestClient(app) as client:
        assert client.get("/app/").status_code == 200
        fallback = client.get("/app/explorer/module")
        assert fallback.status_code == 200
        assert "release test" in fallback.text
        asset = client.get("/app/assets/app-abcdef.js")
        assert asset.status_code == 200
        assert "javascript" in asset.headers["content-type"]
        assert "immutable" in asset.headers["cache-control"]
        api = client.get("/api/v1/projects")
        assert api.status_code == 200
        assert api.headers["content-type"].startswith("application/json")
        assert api.headers["cache-control"] == "private, no-store"
        assert api.headers["x-content-type-options"] == "nosniff"


def test_prior_schema_upgrade_and_backup_rollback(tmp_path: Path) -> None:
    database = tmp_path / "candidate.sqlite3"
    backup = tmp_path / "candidate.before-upgrade.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE schema_metadata(version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_metadata(version) VALUES (1)")
    connection.commit()
    connection.close()
    backup.write_bytes(database.read_bytes())

    connection = sqlite3.connect(database)
    migrate(connection)
    upgraded = connection.execute("SELECT version FROM schema_metadata").fetchone()
    connection.close()
    assert upgraded == (SCHEMA_VERSION,)

    database.write_bytes(backup.read_bytes())
    connection = sqlite3.connect(database)
    restored = connection.execute("SELECT version FROM schema_metadata").fetchone()
    connection.close()
    assert restored == (1,)
