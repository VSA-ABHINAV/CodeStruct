"""Reproduce M1 review findings without executing analyzed source.

Run from repo root with the project venv. Temporary fixture paths are retained
under .codestruct for inspection; no user processes or files are removed.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient


def main():
    repo = Path(__file__).resolve().parents[2]
    fixture_parent = repo / ".codestruct"
    fixture_parent.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="m1-review-", dir=fixture_parent))
    os.environ["CODESTRUCT_DATABASE_PATH"] = str(scratch / "module-default.db")
    from codestruct.api.app import create_app
    from codestruct.settings import Settings

    selected = scratch / "selected"
    selected.mkdir()
    other = scratch / "other"
    other.mkdir()
    for root in (selected, other):
        (root / "app.py").write_text("def run():\n    pass\n", encoding="utf-8")
    results = {}
    app = create_app(
        Settings(
            authorized_roots={"fixture": selected}, database_path=scratch / "review.db"
        )
    )
    with TestClient(app) as client:
        service = app.state.analysis_service
        first = service.register_editor_file(selected / "app.py")
        second = service.register_editor_file(selected / "app.py")
        results["two_registrations_share_session_token"] = (
            first.capability_id == second.capability_id
        )
        request = {
            "session_token": first.capability_id,
            "relative_path": "app.py",
            "line": 1,
        }
        response = client.post(
            "/api/v1/editor/navigate",
            json=request,
            headers={"Origin": "https://untrusted.invalid"},
        )
        results["untrusted_origin_post_status"] = response.status_code
        command = service.queue_editor_navigation(
            first.capability_id, "app.py", 1, command_ttl_seconds=0.01
        )
        time.sleep(0.03)
        results["expired_command_ack"] = service.acknowledge_navigation(
            first.capability_id, command.command_id
        )
        # Retarget a previously registered directory path through a real Windows junction.
        selected.rename(scratch / "selected-original")
        junction = subprocess.run(  # noqa: S603
            ["cmd.exe", "/c", "mklink", "/J", str(selected), str(other)],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        results["junction_created"] = junction.returncode == 0
        if junction.returncode == 0:
            response = client.post("/api/v1/editor/navigate", json=request)
            results["retargeted_junction_post_status"] = response.status_code
            results["retargeted_junction_pending"] = client.get(
                "/api/v1/editor/navigate/pending",
                params={"session_token": first.capability_id},
            ).json()["has_command"]
    app.state.analysis_service.shutdown()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
