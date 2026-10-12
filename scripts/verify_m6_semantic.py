# ruff: noqa: S101, E402
"""Deterministic verification runner for Milestone 6: Grounded Semantic Explanations (CS-016)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from codestruct.analysis.llm_summary import FakeExplanationProvider
from codestruct.api.app import create_app
from codestruct.settings import Settings
from fastapi.testclient import TestClient


def run_m6_verification() -> dict[str, object]:
    sample_root = REPO_ROOT / "sample_project"
    results: dict[str, object] = {
        "milestone": "M6",
        "issue": "CS-016",
        "timestamp_start": time.time(),
    }

    with tempfile.TemporaryDirectory(prefix="codestruct_m6_db_") as tmp_dir:
        db_path = Path(tmp_dir) / "isolated_analysis_m6.db"
        settings = Settings(
            authorized_roots={"sample": sample_root},
            database_path=db_path,
            max_concurrent_jobs=2,
            max_queued_jobs=4,
            analysis_timeout_seconds=30,
            cancellation_grace_seconds=1,
            result_retention_seconds=120,
            polling_interval_ms=100,
        )

        app = create_app(settings)

        with TestClient(app) as client:
            service = app.state.analysis_service

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
            deadline = time.monotonic() + 20
            static_completed = False
            while time.monotonic() < deadline:
                status_resp = client.get(f"/api/v1/analyses/{analysis_id}")
                state = status_resp.json()["state"]
                if state in ("completed", "partially_completed"):
                    static_completed = True
                    break
                time.sleep(0.1)

            assert static_completed, f"Static analysis job did not complete: {state}"

            # Step 3: Fetch graph slice to pick target node
            graph_resp = client.get(f"/api/v1/analyses/{analysis_id}/graph")
            assert graph_resp.status_code == 200
            graph_data = graph_resp.json()
            nodes = graph_data.get("nodes", [])
            assert len(nodes) > 0, "No nodes returned in graph slice"

            # Select a function or class node with source location
            target_node = None
            for n in nodes:
                if n.get("kind") in ("function", "class") and n.get("location"):
                    target_node = n
                    break
            if target_node is None:
                target_node = nodes[0]

            node_id = target_node["id"]
            node_name = target_node.get("name", node_id)
            results["target_node"] = {
                "id": node_id,
                "name": node_name,
                "kind": target_node.get("kind"),
            }

            # Scenario 1: Default rule-based explanation (offline deterministic)
            s1_resp = client.get(
                f"/api/v1/analyses/{analysis_id}/nodes/{node_id}/explain"
            )
            assert s1_resp.status_code == 200, f"S1 failed: {s1_resp.text}"
            s1_data = s1_resp.json()
            assert s1_data["provider"] == "rule-based"
            assert s1_data["fallback_used"] is False
            assert s1_data["fallback_reason"] is None
            assert len(s1_data["claims"]) >= 3
            assert all(c["provenance"] == "RULE_SYNTHESIZED" for c in s1_data["claims"])
            results["scenario_1_rule_based"] = {
                "status_code": s1_resp.status_code,
                "provider": s1_data["provider"],
                "fallback_used": s1_data["fallback_used"],
                "role": s1_data["role"],
                "retrieved_evidence_ids": s1_data["retrieved_evidence_ids"],
                "claims_count": len(s1_data["claims"]),
                "claims_provenance": [c["provenance"] for c in s1_data["claims"]],
            }

            # Scenario 2: Injected deterministic LLM provider (opt-in provider="llm")
            # Retrieve canonical evidence IDs from S1 to provide a valid citation
            valid_evidence_ids = s1_data["retrieved_evidence_ids"]
            citation = valid_evidence_ids[:1] if valid_evidence_ids else []

            fake_payload = {
                "role": "Architectural Foundation Component",
                "summary": f"Synthesized architectural summary for {node_name}.",
                "dependencies_summary": "Evaluated incoming callers and outgoing callees.",
                "metrics_summary": "Evaluated stability and coupling indices.",
                "recommendations": ["Preserve API stability for downstream consumers."],
                "evidence_references": citation,
                "claims": [
                    {
                        "statement": f"{node_name} coordinates module responsibilities.",
                        "claim_type": "architectural_interpretation",
                        "evidence_ids": citation,
                        "provenance": "LLM_INFERRED",
                    }
                ],
            }
            fake_provider = FakeExplanationProvider(
                payload=fake_payload, name="injected-fake-llm"
            )
            service.custom_explanation_provider = fake_provider

            s2_resp = client.get(
                f"/api/v1/analyses/{analysis_id}/nodes/{node_id}/explain?provider=llm"
            )
            assert s2_resp.status_code == 200, f"S2 failed: {s2_resp.text}"
            s2_data = s2_resp.json()
            assert s2_data["provider"] == "injected-fake-llm"
            assert s2_data["fallback_used"] is False
            assert s2_data["role"] == "Architectural Foundation Component"
            assert len(s2_data["claims"]) == 1
            assert s2_data["claims"][0]["provenance"] == "LLM_INFERRED"
            results["scenario_2_injected_llm"] = {
                "status_code": s2_resp.status_code,
                "provider": s2_data["provider"],
                "fallback_used": s2_data["fallback_used"],
                "role": s2_data["role"],
                "cited_evidence_ids": s2_data["cited_evidence_ids"],
                "claims_provenance": [c["provenance"] for c in s2_data["claims"]],
            }

            # Scenario 3: Hallucinated evidence reference triggers fallback
            hallucinating_payload = {
                "role": "Hallucinating Component",
                "summary": "Summary with invented citations.",
                "dependencies_summary": "Dependencies.",
                "metrics_summary": "Metrics.",
                "recommendations": [],
                "evidence_references": ["ev_hallucinated_invalid_9999"],
                "claims": [],
            }
            service.custom_explanation_provider = FakeExplanationProvider(
                payload=hallucinating_payload,
                name="hallucinating-provider",
            )
            s3_resp = client.get(
                f"/api/v1/analyses/{analysis_id}/nodes/{node_id}/explain?provider=llm"
            )
            assert s3_resp.status_code == 200
            s3_data = s3_resp.json()
            assert s3_data["fallback_used"] is True
            assert "ev_hallucinated_invalid_9999" in str(s3_data["fallback_reason"])
            assert "rule-based" in s3_data["provider"]
            results["scenario_3_hallucination_fallback"] = {
                "status_code": s3_resp.status_code,
                "fallback_used": s3_data["fallback_used"],
                "fallback_reason": s3_data["fallback_reason"],
                "effective_provider": s3_data["provider"],
            }

            # Scenario 4: Provider timeout triggers fallback
            service.custom_explanation_provider = FakeExplanationProvider(
                error=TimeoutError("Request timed out after 6.000s"),
                name="timing-out-provider",
            )
            s4_resp = client.get(
                f"/api/v1/analyses/{analysis_id}/nodes/{node_id}/explain?provider=llm"
            )
            assert s4_resp.status_code == 200
            s4_data = s4_resp.json()
            assert s4_data["fallback_used"] is True
            assert "TimeoutError" in str(s4_data["fallback_reason"])
            assert "rule-based" in s4_data["provider"]
            results["scenario_4_timeout_fallback"] = {
                "status_code": s4_resp.status_code,
                "fallback_used": s4_data["fallback_used"],
                "fallback_reason": s4_data["fallback_reason"],
                "effective_provider": s4_data["provider"],
            }

            # Scenario 5: Unconfigured LLM provider falls back
            service.custom_explanation_provider = None
            s5_resp = client.get(
                f"/api/v1/analyses/{analysis_id}/nodes/{node_id}/explain?provider=llm"
            )
            assert s5_resp.status_code == 200
            s5_data = s5_resp.json()
            assert s5_data["fallback_used"] is True
            assert "CODESTRUCT_LLM_API_BASE unset" in str(s5_data["fallback_reason"])
            assert "rule-based" in s5_data["provider"]
            results["scenario_5_unconfigured_fallback"] = {
                "status_code": s5_resp.status_code,
                "fallback_used": s5_data["fallback_used"],
                "fallback_reason": s5_data["fallback_reason"],
                "effective_provider": s5_data["provider"],
            }

        app.state.analysis_service.shutdown()

    results["timestamp_end"] = time.time()
    results["duration_seconds"] = results["timestamp_end"] - results["timestamp_start"]
    results["status"] = "PASSED"
    return results


if __name__ == "__main__":
    out = run_m6_verification()
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["status"] == "PASSED" else 1)
