"""Contract and regression tests for POST /api/v1/editor/navigate, GET …/pending, POST …/acknowledge."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from codestruct.api.app import create_app
from codestruct.settings import Settings
from fastapi.testclient import TestClient

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """Create a FastAPI test client against an isolated app instance."""
    tmp = tmp_path_factory.mktemp("nav_tests")
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
        database_path=tmp / "test.db",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
    if hasattr(app.state, "analysis_service"):
        app.state.analysis_service.shutdown()


def _register_session(
    client: TestClient, filename: str = "main.py", ttl: float = 120.0
) -> str:
    """Helper to register an active editor capability on a real sample file."""
    file_path = str(SAMPLE / filename)
    resp = client.post("/api/v1/editor/selection", json={"file_path": file_path})
    assert resp.status_code == 200, f"Registration failed: {resp.text}"
    return resp.json()["capability_id"]


# ---------------------------------------------------------------------------
# POST /api/v1/editor/navigate
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_post_navigate_queues_command(client):
    """Frontend can queue a navigate command for an active session; response has expected shape."""
    sess_id = _register_session(client, "main.py")
    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": sess_id,
            "relative_path": "main.py",
            "line": 42,
            "column": 5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_version"] == "v1"
    assert data["status"] == "queued"
    assert data["session_token"] == sess_id
    assert data["command_id"].startswith("nav_")


@pytest.mark.contract
def test_post_navigate_minimal_body(client):
    """column is optional."""
    sess_id = _register_session(client, "user.py")
    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": sess_id,
            "relative_path": "user.py",
            "line": 1,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


@pytest.mark.contract
def test_post_navigate_rejects_nul_in_path(client):
    """Paths with NUL characters are rejected with 422."""
    sess_id = _register_session(client, "main.py")
    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": sess_id,
            "relative_path": "evil\x00.py",
            "line": 1,
        },
    )
    assert resp.status_code == 422


@pytest.mark.contract
def test_post_navigate_rejects_zero_line(client):
    """line must be >= 1."""
    sess_id = _register_session(client, "main.py")
    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": sess_id,
            "relative_path": "main.py",
            "line": 0,
        },
    )
    assert resp.status_code == 422


@pytest.mark.contract
def test_post_navigate_rejects_unknown_session(client):
    """Unknown session token is rejected with 403 SESSION_UNAUTHORIZED."""
    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": "cap_nonexistent_unknown_123",
            "relative_path": "main.py",
            "line": 10,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SESSION_UNAUTHORIZED"


@pytest.mark.contract
def test_post_navigate_rejects_public_alias_as_credential(client):
    """A configured public project alias cannot authenticate navigation."""
    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": "sample",
            "relative_path": "main.py",
            "line": 10,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SESSION_UNAUTHORIZED"


@pytest.mark.contract
def test_post_navigate_rejects_path_traversal(client):
    """Path traversal is rejected across both / and \\."""
    sess_id = _register_session(client, "main.py")
    for evil in (
        "../main.py",
        "..\\main.py",
        "dir/../../main.py",
        "dir\\..\\..\\main.py",
    ):
        resp = client.post(
            "/api/v1/editor/navigate",
            json={
                "session_token": sess_id,
                "relative_path": evil,
                "line": 1,
            },
        )
        assert resp.status_code == 403, f"Evil path {evil} was not rejected"
        assert resp.json()["error"]["code"] == "PROJECT_UNAUTHORIZED"


@pytest.mark.contract
def test_post_navigate_rejects_absolute_drive_unc_path(client):
    """Absolute, drive, and UNC paths are rejected."""
    sess_id = _register_session(client, "main.py")
    for bad_path in (
        "/etc/passwd",
        "C:\\Windows\\system32\\cmd.exe",
        "\\\\server\\share\\x.py",
        "//server/share/x.py",
    ):
        resp = client.post(
            "/api/v1/editor/navigate",
            json={
                "session_token": sess_id,
                "relative_path": bad_path,
                "line": 1,
            },
        )
        assert resp.status_code == 403, f"Bad path {bad_path} was not rejected"
        assert resp.json()["error"]["code"] == "PROJECT_UNAUTHORIZED"


@pytest.mark.contract
def test_post_navigate_confines_to_selected_file_scope(client):
    """Selected-file capability remains strictly confined to its registered file scope."""
    sess_id = _register_session(client, "main.py")
    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": sess_id,
            "relative_path": "database.py",  # Exists in sample_project, but not registered in this session
            "line": 5,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SCOPE_UNAUTHORIZED"


@pytest.mark.contract
def test_post_navigate_rejects_expired_session(client):
    """Expired session token is rejected with 403 SESSION_UNAUTHORIZED."""
    service = client.app.state.analysis_service
    cap = service.register_editor_file(SAMPLE / "database.py", ttl_seconds=60.0)
    cap.expires_at = time.time() - 10.0

    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": cap.capability_id,
            "relative_path": "database.py",
            "line": 1,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SESSION_UNAUTHORIZED"


@pytest.mark.contract
def test_post_navigate_rejects_revoked_session(client):
    """Revoked session token is rejected with 403 SESSION_UNAUTHORIZED."""
    service = client.app.state.analysis_service
    cap = service.register_editor_file(SAMPLE / "main.py", ttl_seconds=60.0)
    service.revoke_editor_capability(cap.capability_id)

    resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": cap.capability_id,
            "relative_path": "main.py",
            "line": 1,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SESSION_UNAUTHORIZED"


# ---------------------------------------------------------------------------
# GET /api/v1/editor/navigate/pending
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_get_pending_returns_queued_command(client):
    """After a navigate POST, pending GET returns the command."""
    sess_id = _register_session(client, "main.py")
    post_resp = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": sess_id,
            "relative_path": "main.py",
            "line": 10,
            "column": 3,
        },
    )
    assert post_resp.status_code == 200
    command_id = post_resp.json()["command_id"]

    get_resp = client.get(
        "/api/v1/editor/navigate/pending",
        params={"session_token": sess_id},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["api_version"] == "v1"
    assert data["has_command"] is True
    assert data["command_id"] == command_id
    assert data["relative_path"] == "main.py"
    assert data["line"] == 10
    assert data["column"] == 3


@pytest.mark.contract
def test_get_pending_no_command_returns_false(client):
    """A valid session with no queued command gets has_command=false."""
    sess_id = _register_session(client, "database.py")
    resp = client.get(
        "/api/v1/editor/navigate/pending",
        params={"session_token": sess_id},
    )
    assert resp.status_code == 200
    assert resp.json()["has_command"] is False
    assert resp.json()["command_id"] is None


@pytest.mark.contract
def test_get_pending_rejects_unknown_session(client):
    """Polling with unknown session token raises 403 SESSION_UNAUTHORIZED."""
    resp = client.get(
        "/api/v1/editor/navigate/pending",
        params={"session_token": "cap_unknown_poll_xyz"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SESSION_UNAUTHORIZED"


@pytest.mark.contract
def test_get_pending_command_ttl_expires(client):
    """Command expires after TTL; pending GET returns has_command=false."""
    service = client.app.state.analysis_service
    cap = service.register_editor_file(SAMPLE / "main.py", ttl_seconds=60.0)
    # Queue with very short command TTL
    service.queue_editor_navigation(
        cap.capability_id, "main.py", line=1, column=1, command_ttl_seconds=0.05
    )
    time.sleep(0.08)

    get_resp = client.get(
        "/api/v1/editor/navigate/pending",
        params={"session_token": cap.capability_id},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["has_command"] is False


@pytest.mark.contract
def test_last_wins_bounded_queue_replacement(client):
    """A second POST replaces the earlier command (deterministic last-wins queue bound)."""
    sess_id = _register_session(client, "main.py")

    client.post(
        "/api/v1/editor/navigate",
        json={"session_token": sess_id, "relative_path": "main.py", "line": 1},
    )
    post2 = client.post(
        "/api/v1/editor/navigate",
        json={
            "session_token": sess_id,
            "relative_path": "main.py",
            "line": 99,
            "column": 7,
        },
    )
    latest_id = post2.json()["command_id"]

    get_resp = client.get(
        "/api/v1/editor/navigate/pending",
        params={"session_token": sess_id},
    )
    data = get_resp.json()
    assert data["relative_path"] == "main.py"
    assert data["line"] == 99
    assert data["column"] == 7
    assert data["command_id"] == latest_id


# ---------------------------------------------------------------------------
# POST /api/v1/editor/navigate/acknowledge
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_acknowledge_consumes_command(client):
    """Acknowledging a command removes it from pending and returns status=delivered."""
    sess_id = _register_session(client, "main.py")
    post_resp = client.post(
        "/api/v1/editor/navigate",
        json={"session_token": sess_id, "relative_path": "main.py", "line": 7},
    )
    command_id = post_resp.json()["command_id"]

    ack_resp = client.post(
        "/api/v1/editor/navigate/acknowledge",
        json={
            "session_token": sess_id,
            "command_id": command_id,
            "status": "delivered",
        },
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acknowledged"] is True
    assert ack_resp.json()["status"] == "delivered"

    # Command is no longer pending
    get_resp = client.get(
        "/api/v1/editor/navigate/pending",
        params={"session_token": sess_id},
    )
    assert get_resp.json()["has_command"] is False


@pytest.mark.contract
def test_acknowledge_wrong_command_id(client):
    """Acknowledging with a wrong command_id returns acknowledged=false."""
    sess_id = _register_session(client, "main.py")
    client.post(
        "/api/v1/editor/navigate",
        json={"session_token": sess_id, "relative_path": "main.py", "line": 1},
    )

    ack_resp = client.post(
        "/api/v1/editor/navigate/acknowledge",
        json={"session_token": sess_id, "command_id": "nav_wrong_command_id"},
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acknowledged"] is False
    assert ack_resp.json()["status"] == "unknown_command"


@pytest.mark.contract
def test_acknowledge_failed_delivery_with_reason(client):
    """Plugin can acknowledge with status=failed and safe reason."""
    sess_id = _register_session(client, "main.py")
    post_resp = client.post(
        "/api/v1/editor/navigate",
        json={"session_token": sess_id, "relative_path": "main.py", "line": 15},
    )
    command_id = post_resp.json()["command_id"]

    ack_resp = client.post(
        "/api/v1/editor/navigate/acknowledge",
        json={
            "session_token": sess_id,
            "command_id": command_id,
            "status": "failed",
            "reason": "editor_widget_destroyed",
        },
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acknowledged"] is True
    assert ack_resp.json()["status"] == "failed"


@pytest.mark.contract
def test_distinct_sessions_isolation(client):
    """Two distinct IDE sessions remain isolated and do not cross-deliver."""
    sess_a = _register_session(client, "main.py")
    sess_b = _register_session(client, "user.py")

    # Acknowledge any leftover command on sess_b to ensure clean slate
    pending_b = client.get(
        "/api/v1/editor/navigate/pending", params={"session_token": sess_b}
    ).json()
    if pending_b.get("has_command"):
        client.post(
            "/api/v1/editor/navigate/acknowledge",
            json={"session_token": sess_b, "command_id": pending_b["command_id"]},
        )

    # Queue command on Session A
    client.post(
        "/api/v1/editor/navigate",
        json={"session_token": sess_a, "relative_path": "main.py", "line": 10},
    )

    # Session B should have no command
    get_b = client.get(
        "/api/v1/editor/navigate/pending", params={"session_token": sess_b}
    )
    assert get_b.json()["has_command"] is False

    # Session A should have the command
    get_a = client.get(
        "/api/v1/editor/navigate/pending", params={"session_token": sess_a}
    )
    assert get_a.json()["has_command"] is True
    assert get_a.json()["relative_path"] == "main.py"
