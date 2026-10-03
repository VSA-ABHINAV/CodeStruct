"""Focused tests for analysis options, metrics flag, and cache isolation (CS-008)."""

import time
from pathlib import Path

from codestruct.analysis import AnalysisPolicy, PythonAstParser, scan_project
from codestruct.analysis.models import ProjectParseResult
from codestruct.api.app import create_app
from codestruct.graph.builder import build_graph
from codestruct.settings import Settings
from codestruct.storage.cache_keys import (
    cache_key,
    policy_fingerprint,
)
from fastapi.testclient import TestClient


def test_policy_fingerprint_differentiates_metrics():
    """CS-008: policy_fingerprint must differ when compute_metrics is True vs False."""
    p_no_metrics = AnalysisPolicy(compute_metrics=False)
    p_metrics = AnalysisPolicy(compute_metrics=True)

    fp1 = policy_fingerprint(p_no_metrics)
    fp2 = policy_fingerprint(p_metrics)
    assert fp1 != fp2

    key1 = cache_key("root", ".", "proj_hash", fp1)
    key2 = cache_key("root", ".", "proj_hash", fp2)
    assert key1 != key2


def test_build_graph_conditional_metrics(tmp_path: Path):
    """CS-008: build_graph enriches nodes only when compute_metrics is True."""
    (tmp_path / "app.py").write_text("def a(): pass\ndef b(): a()\n", encoding="utf-8")
    policy = AnalysisPolicy(authorized_roots=(tmp_path,))
    scan = scan_project(tmp_path, policy)
    parser = PythonAstParser()
    files = [parser.parse(tmp_path, sf, policy) for sf in scan.source_files]
    parsed = ProjectParseResult(
        scan=scan, files=tuple(files), diagnostics=scan.diagnostics
    )

    graph_no_m = build_graph(parsed, compute_metrics=False)
    node_a_no_m = next(n for n in graph_no_m.nodes if n.name == "a")
    attrs_no_m = dict(node_a_no_m.attributes)
    assert "fan_in" not in attrs_no_m
    assert "centrality" not in attrs_no_m

    graph_m = build_graph(parsed, compute_metrics=True)
    node_a_m = next(n for n in graph_m.nodes if n.name == "a")
    attrs_m = dict(node_a_m.attributes)
    assert "fan_in" in attrs_m
    assert "centrality" in attrs_m
    assert attrs_m["fan_in"] == "1"


def test_api_options_metrics_cache_isolation(tmp_path: Path):
    """CS-008: API requests with metrics=False and metrics=True create separate cached jobs."""
    proj_root = tmp_path / "sample_proj"
    proj_root.mkdir()
    (proj_root / "mod.py").write_text("def f(): pass\n", encoding="utf-8")

    db_path = tmp_path / "options_test.sqlite3"
    settings = Settings(
        authorized_roots={"sample": proj_root},
        database_path=db_path,
    )
    app = create_app(settings)

    try:
        with TestClient(app) as client:
            # 1. Create with metrics=False
            res_no_m = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "sample", "relative_path": "."},
                    "options": {"metrics": False},
                },
            )
            assert res_no_m.status_code == 202
            id_no_m = res_no_m.json()["analysis_id"]

            for _ in range(50):
                poll = client.get(f"/api/v1/analyses/{id_no_m}").json()
                if poll.get("terminal"):
                    break
                time.sleep(0.05)

            graph_no_m = client.get(f"/api/v1/analyses/{id_no_m}/graph").json()
            fn_node_no_m = next(n for n in graph_no_m["nodes"] if n["name"] == "f")
            attrs_no_m = dict(fn_node_no_m.get("attributes", ()))
            assert "fan_in" not in attrs_no_m

            # 2. Create with metrics=True (should be a separate job / cache miss)
            res_m = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "sample", "relative_path": "."},
                    "options": {"metrics": True},
                },
            )
            assert res_m.status_code == 202
            id_m = res_m.json()["analysis_id"]
            assert id_m != id_no_m

            for _ in range(50):
                poll = client.get(f"/api/v1/analyses/{id_m}").json()
                if poll.get("terminal"):
                    break
                time.sleep(0.05)

            graph_m = client.get(f"/api/v1/analyses/{id_m}/graph").json()
            fn_node_m = next(n for n in graph_m["nodes"] if n["name"] == "f")
            attrs_m = dict(fn_node_m.get("attributes", ()))
            assert "fan_in" in attrs_m
            assert attrs_m["fan_in"] == "0"

            # 3. Repeat with metrics=True -> cache hit
            res_m_repeat = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "sample", "relative_path": "."},
                    "options": {"metrics": True},
                },
            )
            assert res_m_repeat.status_code == 200
            assert res_m_repeat.json()["cache_hit"] is True
    finally:
        app.state.analysis_service.shutdown()
