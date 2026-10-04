"""Milestone 4 real Windows workflow smoke test.

Validates end-to-end behavior across:
1. Configured projects discovery (CS-006)
2. Real analysis submission and status polling progression (CS-006)
3. Node architecture explanation API integration (CS-006)
4. Graphviz DOT export API integration (CS-006)
5. Editor source navigation roundtrip (Frontend -> Backend -> Thonny pending poll) (CS-006, CS-022)
6. Editor navigation failure handling (invalid/expired session) (CS-006)
7. Job cancellation lifecycle and terminal state (CS-021)
8. Large-graph pagination and slice metadata (CS-007)
"""

import json
import shutil
import tempfile
import time
from pathlib import Path

from codestruct.api.app import create_app
from codestruct.settings import Settings
from starlette.testclient import TestClient


def run_m4_real_workflow() -> dict:
    temp_dir = tempfile.mkdtemp(prefix="codestruct_m4_smoke_")
    results = {}
    try:
        temp_path = Path(temp_dir)
        db_path = temp_path / "codestruct_m4_smoke.db"

        # Create sample project structure
        project_root = temp_path / "sample_project"
        project_root.mkdir(parents=True)
        (project_root / "core.py").write_text(
            "class BaseService:\n"
            "    def execute(self) -> str:\n"
            "        return 'base'\n",
            encoding="utf-8",
        )
        (project_root / "service.py").write_text(
            "from core import BaseService\n"
            "\n"
            "class Service(BaseService):\n"
            "    def execute(self) -> str:\n"
            "        return 'service'\n",
            encoding="utf-8",
        )
        (project_root / "main.py").write_text(
            "from service import Service\n"
            "\n"
            "def run_app():\n"
            "    svc = Service()\n"
            "    return svc.execute()\n",
            encoding="utf-8",
        )

        settings = Settings(
            authorized_roots={"sample": project_root},
            database_path=db_path,
        )
        app = create_app(settings)
        client = TestClient(app)

        # 1. Configured projects discovery
        proj_res = client.get("/api/v1/projects")
        assert proj_res.status_code == 200, f"Projects failed: {proj_res.text}"
        proj_data = proj_res.json()
        assert proj_data["api_version"] == "v1"
        assert len(proj_data["projects"]) == 1
        assert proj_data["projects"][0]["id"] == "sample"
        assert proj_data["projects"][0]["available"] is True
        results["projects_discovery"] = proj_data["projects"]

        # 2. Submit real analysis
        submit_res = client.post(
            "/api/v1/analyses",
            json={
                "project": {"root_id": "sample", "relative_path": "."},
                "options": {"metrics": True},
            },
        )
        assert submit_res.status_code in (200, 201, 202), (
            f"Submit failed: {submit_res.text}"
        )
        analysis_id = submit_res.json()["analysis_id"]
        results["analysis_id"] = analysis_id

        # Poll until complete
        for _ in range(50):
            st = client.get(f"/api/v1/analyses/{analysis_id}").json()
            if st["state"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(0.1)
        assert st["state"] == "completed", f"Analysis did not complete: {st}"
        results["analysis_terminal_state"] = st["state"]

        # 3. Retrieve full graph and verify schema
        graph_res = client.get(f"/api/v1/analyses/{analysis_id}/graph")
        assert graph_res.status_code == 200
        graph_data = graph_res.json()
        results["graph_nodes_count"] = len(graph_data["nodes"])
        results["graph_edges_count"] = len(graph_data["edges"])
        results["schema_version"] = graph_data["schema_version"]

        # 4. Explain node
        service_node = next(n for n in graph_data["nodes"] if n["name"] == "Service")
        explain_res = client.get(
            f"/api/v1/analyses/{analysis_id}/nodes/{service_node['id']}/explain"
        )
        assert explain_res.status_code == 200, f"Explain failed: {explain_res.text}"
        explain_data = explain_res.json()
        assert explain_data["api_version"] == "v1"
        assert explain_data["node_id"] == service_node["id"]
        assert "Service" in explain_data["name"]
        results["explanation_role"] = explain_data["role"]
        results["explanation_summary"] = explain_data["summary"]

        # 5. Export DOT graphviz
        dot_res = client.get(f"/api/v1/analyses/{analysis_id}/export/dot")
        assert dot_res.status_code == 200, f"DOT export failed: {dot_res.text}"
        dot_content = dot_res.text
        assert "digraph" in dot_content
        assert "Service" in dot_content
        results["dot_export_length"] = len(dot_content)
        results["dot_export_header"] = dot_content.splitlines()[0]

        # 6. Editor capability registration & navigation roundtrip
        # Register capability via POST /api/v1/editor/selection
        sel_res = client.post(
            "/api/v1/editor/selection",
            json={"file_path": str(project_root / "main.py")},
        )
        assert sel_res.status_code == 200, f"Editor selection failed: {sel_res.text}"
        cap_token = sel_res.json()["capability_id"]
        results["editor_capability_id_prefix"] = cap_token[:4]

        # Dispatch navigation from frontend
        nav_post = client.post(
            "/api/v1/editor/navigate",
            json={
                "session_token": cap_token,
                "relative_path": "main.py",
                "line": 3,
                "column": 1,
            },
        )
        assert nav_post.status_code in (200, 202), (
            f"Navigation dispatch failed: {nav_post.text}"
        )
        results["nav_dispatch_status"] = nav_post.json().get("status") or "queued"

        # Thonny polls pending navigation queue
        nav_poll = client.get(
            "/api/v1/editor/navigate/pending",
            params={"session_token": cap_token},
        )
        assert nav_poll.status_code == 200, f"Navigation poll failed: {nav_poll.text}"
        nav_event = nav_poll.json()
        assert nav_event["has_command"] is True
        assert nav_event["relative_path"] == "main.py"
        assert nav_event["line"] == 3
        results["nav_roundtrip_received"] = {
            "path": nav_event["relative_path"],
            "line": nav_event["line"],
            "column": nav_event["column"],
        }

        # 7. Navigation error handling on invalid/stale session token
        nav_bad = client.post(
            "/api/v1/editor/navigate",
            json={
                "session_token": "cap_invalid_or_expired",
                "relative_path": "service.py",
                "line": 3,
            },
        )
        assert nav_bad.status_code in (403, 404), (
            f"Bad session did not error: {nav_bad.status_code}"
        )
        results["nav_bad_session_status"] = nav_bad.status_code
        results["nav_bad_session_error"] = nav_bad.json().get("error", {}).get("code")

        # 8. Cancellation lifecycle test
        cancel_sub = client.post(
            "/api/v1/analyses",
            json={
                "project": {"root_id": "sample", "relative_path": "."},
                "options": {"metrics": False},
                "refresh": True,
            },
        )
        cancel_id = cancel_sub.json()["analysis_id"]
        # Immediately cancel
        cancel_res = client.delete(f"/api/v1/analyses/{cancel_id}")
        assert cancel_res.status_code in (200, 202), f"Cancel failed: {cancel_res.text}"
        cancel_data = cancel_res.json()
        assert cancel_data["state"] in (
            "cancellation_requested",
            "cancelled",
            "completed",
        )
        results["cancellation_ack_state"] = cancel_data["state"]

        # 9. Bounded Graph Pagination (CS-007)
        page1_res = client.get(
            f"/api/v1/analyses/{analysis_id}/graph", params={"limit": 2}
        )
        assert page1_res.status_code == 200
        page1_data = page1_res.json()
        assert page1_data["page"]["returned_nodes"] == len(page1_data["nodes"])
        assert page1_data["page"]["total_nodes"] == len(graph_data["nodes"])
        assert page1_data["page"]["partial_load"] is True
        results["pagination_slice"] = {
            "returned_nodes": page1_data["page"]["returned_nodes"],
            "total_nodes": page1_data["page"]["total_nodes"],
            "has_next_cursor": bool(page1_data["page"].get("next_cursor")),
            "partial_load": page1_data["page"]["partial_load"],
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return results


if __name__ == "__main__":
    out = run_m4_real_workflow()
    print(json.dumps(out, indent=2))
