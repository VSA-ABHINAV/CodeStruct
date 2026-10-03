"""Focused tests for canonical node context extraction, evidence preservation, and explanation (CS-011)."""

from pathlib import Path
from tempfile import TemporaryDirectory

from codestruct.analysis import AnalysisPolicy, parse_project
from codestruct.analysis.llm_summary import (
    RuleBasedExplainer,
    extract_node_context,
)
from codestruct.api.app import create_app
from codestruct.graph import build_graph, graph_to_dict
from fastapi.testclient import TestClient


def test_extract_node_context_real_serialized_graph():
    """CS-011: Test extract_node_context with real graph_to_dict(build_graph(...)) output."""
    with TemporaryDirectory(prefix="codestruct-test-explain-") as directory:
        root = Path(directory)
        code = (
            "def helper():\n"
            "    return 42\n\n"
            "def compute():\n"
            "    '''Compute value with helper.'''\n"
            "    return helper()\n"
        )
        (root / "service.py").write_text(code, encoding="utf-8")

        policy = AnalysisPolicy(authorized_roots=(root,), compute_metrics=True)
        parse_result = parse_project(root, policy)
        graph_obj = build_graph(parse_result, compute_metrics=True)
        graph_dict = graph_to_dict(graph_obj)

        compute_node = next(n for n in graph_dict["nodes"] if n["name"] == "compute")
        helper_node = next(n for n in graph_dict["nodes"] if n["name"] == "helper")

        ctx = extract_node_context(graph_dict, compute_node["id"])

        # 1. Canonical location fidelity (start_line, end_line directly from serializer)
        assert ctx.name == "compute"
        assert ctx.file_path == "service.py"
        assert ctx.line == 4
        assert ctx.end_line == 6
        assert ctx.kind == "function"

        # 2. Dependency network (only resolved relationships)
        assert helper_node["qualified_name"] in ctx.callees

        # 3. Evidence preservation
        assert len(ctx.evidence) > 0, (
            "Node context must carry incident evidence records"
        )
        for ev in ctx.evidence:
            assert "id" in ev
            assert "origin" in ev
            assert "observation_kind" in ev
            assert "location" in ev

        # 4. Metrics preservation
        assert "fan_out" in ctx.metrics
        assert "component_id" in ctx.metrics
        assert "community_id" in ctx.metrics

        # 5. Explanation synthesis with exact location and evidence
        explanation = RuleBasedExplainer.explain(ctx)
        assert (
            "service.py:4-6" in explanation.summary
            or "service.py:4" in explanation.summary
        )
        assert "helper" in explanation.dependencies_summary
        assert "Fan-in:" in explanation.metrics_summary


def test_extract_node_context_flat_serializer_dict():
    """CS-011: Test with flat location dictionary matching graph_to_dict exact format."""
    graph = {
        "nodes": [
            {
                "id": "node_func_a",
                "name": "render_view",
                "qualified_name": "app.ui.render_view",
                "kind": "function",
                "location": {
                    "source_unit_id": "file_1",
                    "path": "app/ui.py",
                    "start_line": 42,
                    "start_column": 1,
                    "end_line": 58,
                    "end_column": 10,
                },
                "attributes": [
                    ("centrality", "0.250"),
                    ("community", "1"),
                    ("component", "1"),
                    ("fan_in", "3"),
                    ("fan_out", "2"),
                    ("in_cycle", "false"),
                    ("instability", "0.40"),
                    ("docstring", "Render main application view template."),
                ],
            },
            {
                "id": "node_func_b",
                "name": "load_data",
                "qualified_name": "app.db.load_data",
                "kind": "function",
                "location": {
                    "path": "app/db.py",
                    "start_line": 10,
                    "end_line": 20,
                },
            },
            {
                "id": "node_unresolved_tgt",
                "name": "missing",
                "qualified_name": "app.missing",
                "kind": "function",
            },
        ],
        "edges": [
            {
                "id": "e_resolved",
                "source_id": "node_func_a",
                "target_id": "node_func_b",
                "kind": "CALLS",
                "resolution_status": "resolved",
                "evidence_ids": ["ev_1"],
            },
            {
                "id": "e_unresolved",
                "source_id": "node_func_a",
                "target_id": "node_unresolved_tgt",
                "kind": "CALLS",
                "resolution_status": "unresolved",
                "evidence_ids": ["ev_2"],
            },
        ],
        "evidence": [
            {
                "evidence_id": "ev_1",
                "origin": "static_resolution",
                "observation_kind": "call_resolution",
                "location": {
                    "path": "app/ui.py",
                    "start_line": 45,
                    "end_line": 45,
                },
                "explanation": "Resolved static call",
                "expression": "load_data()",
            },
            {
                "evidence_id": "ev_2",
                "origin": "source_ast",
                "observation_kind": "call",
                "location": {
                    "path": "app/ui.py",
                    "start_line": 50,
                    "end_line": 50,
                },
                "explanation": "Unresolved call",
                "expression": "missing()",
            },
        ],
    }

    ctx = extract_node_context(graph, "node_func_a")
    assert ctx.file_path == "app/ui.py"
    assert ctx.line == 42
    assert ctx.end_line == 58
    assert ctx.docstring == "Render main application view template."

    # Only resolved callee should be present in callee network
    assert "app.db.load_data" in ctx.callees
    assert "app.missing" not in ctx.callees

    # Evidence from resolved edge must be attached
    assert len(ctx.evidence) == 1
    assert ctx.evidence[0]["id"] == "ev_1"
    assert ctx.evidence[0]["expression"] == "load_data()"

    # Explain synthesis
    explanation = RuleBasedExplainer.explain(ctx)
    assert "app/ui.py:42-58" in explanation.summary
    assert "Fan-in: 3, Fan-out: 2" in explanation.metrics_summary


def test_live_explain_api_route():
    """CS-011: Test GET /analyses/{analysis_id}/nodes/{node_id}/explain endpoint."""
    with TemporaryDirectory(prefix="codestruct-test-explain-api-") as directory:
        root = Path(directory)
        (root / "app.py").write_text(
            "def handle_request():\n"
            "    '''Process incoming HTTP request.'''\n"
            "    return {'status': 'ok'}\n",
            encoding="utf-8",
        )
        from codestruct.settings import Settings

        settings = Settings(
            authorized_roots={"default": root},
            database_path=root / "test_api.sqlite3",
        )
        app = create_app(settings)
        try:
            with TestClient(app) as client:
                # 1. Create analysis
                create_resp = client.post(
                    "/api/v1/analyses",
                    json={
                        "project": {"root_id": "default", "relative_path": "."},
                        "options": {"metrics": True},
                    },
                )
                assert create_resp.status_code in (200, 201, 202)
                analysis_id = create_resp.json()["analysis_id"]

                # 2. Wait for completion & Fetch completed job
                import time

                for _ in range(50):
                    poll = client.get(f"/api/v1/analyses/{analysis_id}").json()
                    if poll.get("terminal"):
                        break
                    time.sleep(0.05)

                get_resp = client.get(f"/api/v1/analyses/{analysis_id}/graph")
                assert get_resp.status_code == 200
                graph_data = get_resp.json()
                assert graph_data is not None

                target_node = next(
                    n for n in graph_data["nodes"] if n["name"] == "handle_request"
                )

                # 3. Request explanation via API
                explain_resp = client.get(
                    f"/api/v1/analyses/{analysis_id}/nodes/{target_node['id']}/explain"
                )
                assert explain_resp.status_code == 200
                data = explain_resp.json()
                assert data["node_id"] == target_node["id"]
                assert data["name"] == "handle_request"
                assert (
                    "handle_request" in data["summary"]
                    or "Process incoming HTTP request." in data["summary"]
                )
                assert data["provider"] == "rule-based"
        finally:
            app.state.analysis_service.shutdown()
