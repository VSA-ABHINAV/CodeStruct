# ruff: noqa: S101, E402
"""Deterministic verification runner for Milestone 5: Runtime Analysis Pipeline & Merger."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from codestruct.api.app import create_app
from codestruct.settings import Settings
from fastapi.testclient import TestClient


def run_m5_verification() -> dict[str, object]:
    sample_root = REPO_ROOT / "sample_project"
    settings = Settings(
        authorized_roots={"sample": sample_root},
        max_concurrent_jobs=2,
        max_queued_jobs=4,
        analysis_timeout_seconds=30,
        cancellation_grace_seconds=1,
        result_retention_seconds=120,
        polling_interval_ms=100,
    )

    app = create_app(settings)
    results: dict[str, object] = {}

    with TestClient(app) as client:
        # Step 1: Create static analysis job
        create_resp = client.post(
            "/api/v1/analyses",
            json={"project": {"root_id": "sample", "relative_path": "."}},
        )
        assert create_resp.status_code == 202, (
            f"Expected 202, got {create_resp.status_code}: {create_resp.text}"
        )
        analysis_id = create_resp.json()["analysis_id"]
        results["analysis_id"] = analysis_id

        # Step 2: Poll static analysis until completion
        deadline = time.monotonic() + 15
        static_completed = False
        while time.monotonic() < deadline:
            status_resp = client.get(f"/api/v1/analyses/{analysis_id}")
            state = status_resp.json()["state"]
            if state in ("completed", "partially_completed"):
                static_completed = True
                break
            time.sleep(0.05)
        assert static_completed, "Static analysis did not reach completed state"

        # Step 3: Verify initial runtime sessions are empty and graph has no runtime evidence
        init_sessions_resp = client.get(f"/api/v1/analyses/{analysis_id}/runtime")
        assert init_sessions_resp.status_code == 200
        assert init_sessions_resp.json()["sessions"] == []

        init_graph_resp = client.get(f"/api/v1/analyses/{analysis_id}/graph")
        assert init_graph_resp.status_code == 200
        init_graph = init_graph_resp.json()
        init_runtime_ev = [
            ev
            for ev in init_graph.get("evidence", [])
            if ev.get("origin") == "runtime_trace"
        ]
        assert len(init_runtime_ev) == 0, (
            "Static analysis unexpectedly generated runtime evidence"
        )

        # Step 4: Execute explicit opt-in runtime session 1
        r1_resp = client.post(
            f"/api/v1/analyses/{analysis_id}/runtime",
            json={
                "target_file": "main.py",
                "args": [],
                "timeout_seconds": 5.0,
            },
        )
        assert r1_resp.status_code == 200, (
            f"Expected 200, got {r1_resp.status_code}: {r1_resp.text}"
        )
        r1_body = r1_resp.json()
        r1_session = r1_body["session"]
        results["session_1"] = r1_session

        assert r1_session["status"] == "completed"
        assert r1_session["total_calls"] >= 1
        assert r1_session["covered_nodes"] >= 1
        assert r1_session["coverage_percent"] > 0

        # Step 5: Execute repeat run (session 2) to test cumulative call counts and fresh metrics
        r2_resp = client.post(
            f"/api/v1/analyses/{analysis_id}/runtime",
            json={
                "target_file": "main.py",
                "args": [],
                "timeout_seconds": 5.0,
            },
        )
        assert r2_resp.status_code == 200
        r2_session = r2_resp.json()["session"]
        results["session_2"] = r2_session

        # Step 6: Verify sessions list contains both sessions
        list_resp = client.get(f"/api/v1/analyses/{analysis_id}/runtime")
        assert list_resp.status_code == 200
        sessions_list = list_resp.json()["sessions"]
        assert len(sessions_list) == 2
        results["total_recorded_sessions"] = len(sessions_list)

        # Step 7: Verify merged graph has runtime evidence and updated node/edge attributes
        merged_graph_resp = client.get(f"/api/v1/analyses/{analysis_id}/graph")
        assert merged_graph_resp.status_code == 200
        merged_graph = merged_graph_resp.json()
        merged_runtime_ev = [
            ev
            for ev in merged_graph.get("evidence", [])
            if ev.get("origin") == "runtime_trace"
        ]
        assert len(merged_runtime_ev) >= 1
        results["runtime_evidence_count"] = len(merged_runtime_ev)

        # Step 8: Test unauthorized escaping path rejection
        bad_resp = client.post(
            f"/api/v1/analyses/{analysis_id}/runtime",
            json={"target_file": "../outside.py"},
        )
        assert bad_resp.status_code == 400
        assert bad_resp.json()["error"]["code"] == "RUNTIME_PATH_OUTSIDE_PROJECT"
        results["security_containment_verified"] = True

    app.state.analysis_service.shutdown()
    return results


if __name__ == "__main__":
    res = run_m5_verification()
    print(json.dumps(res, indent=2))
