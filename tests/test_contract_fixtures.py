"""Permanent regression tests validating frontend contract fixtures against real API routes and serializers."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from codestruct.analysis import AnalysisPolicy, parse_project
from codestruct.api.app import create_app
from codestruct.api.pagination import decode_cursor, slice_graph
from codestruct.api.routes.navigate import (
    AcknowledgeRequest,
    AcknowledgeResponse,
    NavigateRequest,
    NavigateResponse,
    PendingNavigateResponse,
)
from codestruct.api.schemas import (
    DiagnosticsResponse,
    JobResponse,
    NodeExplanationResponse,
    ProjectsResponse,
)
from codestruct.graph import build_graph, graph_from_dict, graph_to_dict
from codestruct.settings import Settings, load_settings
from fastapi.testclient import TestClient

CONTRACT_DIR = Path(__file__).resolve().parents[1] / "docs" / "frontend-contract"
REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"
BRIEF_PATH = REPOSITORY / "LOVABLE_FRONTEND_BRIEF.md"

CANONICAL_SUMMARY_KEYS = {
    "source_units_total",
    "nodes_total",
    "edges_total",
    "evidence_total",
    "diagnostics_total",
    "nodes_by_kind",
    "edges_by_kind",
    "edges_by_resolution",
    "edges_by_confidence",
    "diagnostics_by_severity",
    "diagnostics_by_code",
    "excluded_entries",
    "failed_files",
    "skipped_files",
    "describes_full_result",
}


def test_projects_fixture_conforms_to_schema_and_route(tmp_path: Path):
    path = CONTRACT_DIR / "projects.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    model = ProjectsResponse.model_validate(data)
    assert model.api_version == "v1"
    assert len(model.projects) >= 1
    assert model.projects[0].id == "sample_service"

    # Verify against live TestClient route
    settings = Settings(
        authorized_roots={"sample_service": SAMPLE},
        database_path=tmp_path / "api.sqlite3",
    )
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/projects")
            assert resp.status_code == 200
            route_model = ProjectsResponse.model_validate(resp.json())
            assert route_model.api_version == "v1"
            assert route_model.projects[0].id == "sample_service"
            assert route_model.projects[0].display_name == "Sample Service"
    finally:
        app.state.analysis_service.shutdown()


def test_brief_create_request_matches_route_and_unsupported_options_rejected(
    tmp_path: Path,
):
    """Item 1: Test parsed JSON from actual brief in isolated TestClient returns 202; unsupported options return 400."""
    brief_text = BRIEF_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"### 5\.2 Create Analysis.*?\*\*Request Body:\*\*\s*```json\s*(\{.*?\})\s*```",
        brief_text,
        re.DOTALL,
    )
    assert match is not None, (
        "Failed to locate Section 5.2 create request body in LOVABLE_FRONTEND_BRIEF.md"
    )
    create_body = json.loads(match.group(1))

    # Supported options in M1: metrics=False, no custom grammar or patterns
    assert create_body["project"]["root_id"] == "sample_service"
    assert create_body.get("options", {}).get("metrics") is False
    assert "source_grammar" not in create_body.get("options", {})

    settings = Settings(
        authorized_roots={"sample_service": SAMPLE},
        database_path=tmp_path / "brief_create.sqlite3",
    )
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/analyses", json=create_body)
            assert resp.status_code == 202
            data = resp.json()
            assert data["api_version"] == "v1"
            assert data["state"] in {"submitted", "queued", "validating"}
            assert data["links"]["graph"] is None

            # Verify unsupported options are explicitly rejected with HTTP 400 OPTION_UNSUPPORTED
            unsupported_grammar = {
                "project": {"root_id": "sample_service", "relative_path": "."},
                "options": {"source_grammar": "3.12"},
            }
            resp_grammar = client.post("/api/v1/analyses", json=unsupported_grammar)
            assert resp_grammar.status_code == 400
            assert resp_grammar.json()["error"]["code"] == "OPTION_UNSUPPORTED"

            supported_metrics = {
                "project": {"root_id": "sample_service", "relative_path": "."},
                "options": {"metrics": True},
            }
            resp_metrics = client.post("/api/v1/analyses", json=supported_metrics)
            assert resp_metrics.status_code in {200, 202}

            unsupported_patterns = {
                "project": {"root_id": "sample_service", "relative_path": "."},
                "options": {"include_patterns": ["*.py"]},
            }
            resp_patterns = client.post("/api/v1/analyses", json=unsupported_patterns)
            assert resp_patterns.status_code == 400
            assert resp_patterns.json()["error"]["code"] == "OPTION_UNSUPPORTED"

    finally:
        app.state.analysis_service.shutdown()


def test_analysis_job_fixture_matches_canonical_serializer_and_route_summary(
    tmp_path: Path,
):
    """Item 2: Compare nested summary key set (schema shape) against canonical serializer and live route.

    Note: analysis_job.json reflects the synthetic toy graph schema (1 source unit, 3 nodes, 2 edges).
    This test verifies canonical key-set / schema shape conformance against canonical serializer output
    and live route execution, not numeric value equality between the toy graph and sample_project.
    """
    path = CONTRACT_DIR / "analysis_job.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    model = JobResponse.model_validate(data)
    assert model.api_version == "v1"
    assert model.state == "completed"
    assert model.terminal is True
    assert model.progress.percent == 100

    result = model.result
    assert result is not None
    assert "result_id" in result
    assert "graph_id" in result
    assert "schema_version" in result
    assert "summary" in result
    fixture_summary = result["summary"]
    assert isinstance(fixture_summary, dict)

    # Compare exact key set against canonical summary definition
    assert set(fixture_summary.keys()) == CANONICAL_SUMMARY_KEYS
    assert "total_files" not in fixture_summary
    assert "total_nodes" not in fixture_summary
    assert "total_edges" not in fixture_summary

    # Compare against canonical serializer summary from sample_project
    policy = AnalysisPolicy(authorized_roots=(SAMPLE,))
    canonical_graph = graph_to_dict(build_graph(parse_project(SAMPLE, policy)))
    canonical_summary = canonical_graph["summary"]
    assert isinstance(canonical_summary, dict)
    assert set(canonical_summary.keys()) == set(fixture_summary.keys())

    # Validate against live completed TestClient job
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
        database_path=tmp_path / "job_summary.sqlite3",
    )
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            create_resp = client.post(
                "/api/v1/analyses",
                json={"project": {"root_id": "sample", "relative_path": "."}},
            )
            assert create_resp.status_code == 202
            ana_id = create_resp.json()["analysis_id"]

            job_data: dict[str, object] = {}
            for _ in range(50):
                poll = client.get(f"/api/v1/analyses/{ana_id}").json()
                if poll.get("terminal"):
                    job_data = poll
                    break
                time.sleep(0.05)

            assert job_data.get("terminal") is True
            job_result = job_data.get("result")
            assert isinstance(job_result, dict)
            route_summary = job_result.get("summary")
            assert isinstance(route_summary, dict)
            assert set(route_summary.keys()) == CANONICAL_SUMMARY_KEYS
    finally:
        app.state.analysis_service.shutdown()


def test_diagnostics_fixture_and_route_retrieval_and_canonical_shape(tmp_path: Path):
    """Item 3: Validate canonical GraphDiagnostic location and shape in fixture and isolated route."""
    path = CONTRACT_DIR / "diagnostics.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    model = DiagnosticsResponse.model_validate(data)
    assert model.api_version == "v1"
    assert model.schema_version == "1.0.0"
    assert len(model.items) >= 1
    assert (
        "error" in model.totals or "warning" in model.totals or "info" in model.totals
    )

    required_diag_keys = {
        "id",
        "code",
        "severity",
        "phase",
        "message",
        "location",
        "entity_id",
        "edge_id",
        "recoverable",
        "consequence",
        "suggested_action",
        "details",
    }
    location_keys = {
        "source_unit_id",
        "path",
        "start_line",
        "start_column",
        "end_line",
        "end_column",
    }

    for item in model.items:
        assert required_diag_keys.issubset(item.keys())
        assert "file_path" not in item
        assert "line" not in item
        assert item["severity"] in {"info", "warning", "error"}
        loc = item["location"]
        assert isinstance(loc, dict)
        assert location_keys.issubset(loc.keys())
        assert isinstance(loc["path"], str)
        assert isinstance(loc["start_line"], int)

    # Route retrieval from isolated static syntax error project
    bad_root = tmp_path / "bad_syntax_proj"
    bad_root.mkdir()
    (bad_root / "invalid.py").write_text("def broken(\n", encoding="utf-8")
    settings = Settings(
        authorized_roots={"bad_proj": bad_root},
        database_path=tmp_path / "diag.sqlite3",
    )
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            create_resp = client.post(
                "/api/v1/analyses",
                json={"project": {"root_id": "bad_proj", "relative_path": "."}},
            )
            assert create_resp.status_code == 202
            ana_id = create_resp.json()["analysis_id"]

            for _ in range(50):
                poll = client.get(f"/api/v1/analyses/{ana_id}").json()
                if poll.get("terminal"):
                    break
                time.sleep(0.05)

            diag_resp = client.get(f"/api/v1/analyses/{ana_id}/diagnostics")
            assert diag_resp.status_code == 200
            diag_model = DiagnosticsResponse.model_validate(diag_resp.json())
            assert len(diag_model.items) >= 1
            bad_item = diag_model.items[0]
            assert required_diag_keys.issubset(bad_item.keys())
            assert bad_item["code"] == "FILE_SYNTAX_ERROR"
            assert bad_item["severity"] == "error"
            assert bad_item["phase"] == "parsing"
            bad_loc = bad_item["location"]
            assert isinstance(bad_loc, dict)
            assert location_keys.issubset(bad_loc.keys())
            assert bad_loc["path"] == "invalid.py"
    finally:
        app.state.analysis_service.shutdown()


def test_api_error_envelopes_and_schema_validation(tmp_path: Path):
    """Item 4: Validate real ApiError envelope against TestClient."""
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
        database_path=tmp_path / "errors.sqlite3",
    )
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            # 404: Unknown analysis ID
            resp_404 = client.get("/api/v1/analyses/ana_nonexistent_12345")
            assert resp_404.status_code == 404
            data_404 = resp_404.json()
            assert data_404["api_version"] == "v1"
            assert data_404["request_id"].startswith("req_")
            err_404 = data_404["error"]
            assert err_404["code"] == "JOB_NOT_FOUND"
            assert (
                err_404["message"]
                == "The requested analysis does not exist or has expired."
            )
            assert err_404["recoverable"] is True
            assert err_404["field_errors"] == []
            assert err_404["safe_context"] == {}
            assert err_404["retry_after_seconds"] is None
            assert "details" not in err_404

            # 422: Malformed request payload
            resp_422 = client.post("/api/v1/analyses", json={"project": 12345})
            assert resp_422.status_code == 422
            data_422 = resp_422.json()
            assert data_422["api_version"] == "v1"
            err_422 = data_422["error"]
            assert err_422["code"] == "REQUEST_INVALID"
            assert err_422["field_errors"] == []
            assert err_422["safe_context"] == {}
            assert "details" not in err_422

            # 400: Unsupported option
            resp_400 = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "sample", "relative_path": "."},
                    "options": {"include_patterns": ["*.py"]},
                },
            )
            assert resp_400.status_code == 400
            err_400 = resp_400.json()["error"]
            assert err_400["code"] == "OPTION_UNSUPPORTED"
            assert "details" not in err_400
    finally:
        app.state.analysis_service.shutdown()


def test_nonterminal_and_terminal_graph_link_availability(tmp_path: Path):
    """Item 5: links.graph is None until usable result, then available."""
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
        database_path=tmp_path / "links.sqlite3",
    )
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            create_resp = client.post(
                "/api/v1/analyses",
                json={"project": {"root_id": "sample", "relative_path": "."}},
            )
            assert create_resp.status_code == 202
            created_job = create_resp.json()
            ana_id = created_job["analysis_id"]

            # In nonterminal state, links.graph must be None
            assert created_job["links"]["graph"] is None

            # Requesting graph while job is nonterminal returns 409
            if not created_job["terminal"]:
                graph_early = client.get(f"/api/v1/analyses/{ana_id}/graph")
                # Either 409 RESULT_NOT_READY or already completed in thread
                assert graph_early.status_code in {200, 409}
                if graph_early.status_code == 409:
                    assert graph_early.json()["error"]["code"] in {
                        "RESULT_NOT_READY",
                        "RESULT_UNAVAILABLE",
                    }

            # Poll until completion
            for _ in range(50):
                poll = client.get(f"/api/v1/analyses/{ana_id}").json()
                if poll.get("terminal"):
                    break
                time.sleep(0.05)

            terminal_job = client.get(f"/api/v1/analyses/{ana_id}").json()
            assert terminal_job["terminal"] is True
            assert terminal_job["links"]["graph"] == f"/api/v1/analyses/{ana_id}/graph"

            # Graph is now accessible via 200
            graph_resp = client.get(f"/api/v1/analyses/{ana_id}/graph")
            assert graph_resp.status_code == 200
    finally:
        app.state.analysis_service.shutdown()


def test_cancellation_idempotency_and_paging_caps(tmp_path: Path):
    """Item 6: Cancelling already-cancelled is idempotent; limit omission returns full graph; limit > 1000 returns 413."""
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
        database_path=tmp_path / "cancel.sqlite3",
    )
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            # 1. Test cancellation idempotency
            create_resp = client.post(
                "/api/v1/analyses",
                json={"project": {"root_id": "sample", "relative_path": "."}},
            )
            ana_id = create_resp.json()["analysis_id"]
            cancel_1 = client.delete(f"/api/v1/analyses/{ana_id}")
            assert cancel_1.status_code in {200, 202}

            # Wait until cancellation is fully recorded if it was 202
            for _ in range(50):
                poll = client.get(f"/api/v1/analyses/{ana_id}").json()
                if poll.get("state") == "cancelled":
                    break
                time.sleep(0.05)

            # Idempotent cancel: cancelling an already-cancelled job returns HTTP 200 (not 409!)
            cancel_2 = client.delete(f"/api/v1/analyses/{ana_id}")
            assert cancel_2.status_code == 200
            assert cancel_2.json()["state"] == "cancelled"

            # 2. Test terminal completed job cancellation returns 409 JOB_TERMINAL
            comp_resp = client.post(
                "/api/v1/analyses",
                json={"project": {"root_id": "sample", "relative_path": "."}},
            )
            comp_id = comp_resp.json()["analysis_id"]
            for _ in range(50):
                poll = client.get(f"/api/v1/analyses/{comp_id}").json()
                if poll.get("terminal"):
                    break
                time.sleep(0.05)

            cancel_comp = client.delete(f"/api/v1/analyses/{comp_id}")
            assert cancel_comp.status_code == 409
            assert cancel_comp.json()["error"]["code"] == "JOB_TERMINAL"

            # 3. Paging caps: omitted limit returns full graph (not capped by max_graph_page_size)
            full_graph = client.get(f"/api/v1/analyses/{comp_id}/graph")
            assert full_graph.status_code == 200
            assert "schema_version" in full_graph.json()

            # Explicit limit > max_graph_page_size (1000) returns 413 PAGE_LIMIT_EXCEEDED
            over_limit = client.get(f"/api/v1/analyses/{comp_id}/graph?limit=1001")
            assert over_limit.status_code == 413
            assert over_limit.json()["error"]["code"] == "PAGE_LIMIT_EXCEEDED"

            # Valid explicit limit returns sliced page
            sliced = client.get(f"/api/v1/analyses/{comp_id}/graph?limit=2")
            assert sliced.status_code == 200
            assert "page" in sliced.json()
    finally:
        app.state.analysis_service.shutdown()


def test_node_explanation_fixture_conforms_to_schema():
    path = CONTRACT_DIR / "node_explanation.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    model = NodeExplanationResponse.model_validate(data)
    assert model.api_version == "v1"
    assert model.node_id == "node_pkg_service_process_fn"
    assert model.kind == "function"
    assert len(model.recommendations) >= 1


def test_editor_navigate_fixture_conforms_to_schemas():
    path = CONTRACT_DIR / "editor_navigate.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    nav_req = NavigateRequest.model_validate(data["navigate_request"])
    assert nav_req.session_token.startswith("cap_")

    nav_resp = NavigateResponse.model_validate(data["navigate_response"])
    assert nav_resp.status == "queued"

    pending_resp = PendingNavigateResponse.model_validate(
        data["pending_navigate_response"]
    )
    assert pending_resp.has_command is True

    ack_req = AcknowledgeRequest.model_validate(data["acknowledge_request"])
    assert ack_req.status == "delivered"

    ack_resp = AcknowledgeResponse.model_validate(data["acknowledge_response"])
    assert ack_resp.acknowledged is True


def test_graph_slice_fixture_round_trip_and_real_pagination():
    path = CONTRACT_DIR / "graph_slice.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    # Validate top-level envelope fields
    assert data["api_version"] == "v1"
    assert data["schema_version"] == "1.0.0"
    assert isinstance(data["metadata"], dict)
    assert isinstance(data["summary"], dict)
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    assert isinstance(data["evidence"], list)
    assert isinstance(data["diagnostics"], list)
    assert isinstance(data["page"], dict)

    # Verify deserializer round-trip for graph data
    graph_obj = graph_from_dict(data)
    assert len(graph_obj.nodes) == len(data["nodes"])
    assert len(graph_obj.edges) == len(data["edges"])
    assert len(graph_obj.evidence) == len(data["evidence"])

    # Verify round-tripped serialization preserves exact coordinates & attributes
    dict_repr = graph_to_dict(graph_obj)
    assert dict_repr["metadata"]["graph_id"] == data["metadata"]["graph_id"]
    for orig_node, res_node in zip(data["nodes"], dict_repr["nodes"], strict=True):
        assert orig_node["id"] == res_node["id"]
        assert orig_node["kind"] == res_node["kind"]
        if orig_node.get("location"):
            assert (
                orig_node["location"]["start_line"]
                == res_node["location"]["start_line"]
            )
            assert (
                orig_node["location"]["start_column"]
                == res_node["location"]["start_column"]
            )

    # Test real graph generation & slice_graph on sample_project
    policy = AnalysisPolicy(authorized_roots=(SAMPLE,))
    sample_graph = graph_to_dict(build_graph(parse_project(SAMPLE, policy)))
    sliced = slice_graph(
        sample_graph,
        limit=2,
        cursor=None,
        node_kind=None,
        edge_kind=None,
        resolution_status=None,
    )
    assert sliced["page"]["returned_nodes"] >= 2
    assert sliced["page"]["total_nodes"] >= sliced["page"]["returned_nodes"]
    assert sliced["page"]["partial_load"] is True
    next_cur = sliced["page"]["next_cursor"]
    assert next_cur is not None

    # Verify next cursor decodes with matching filter context
    decoded_offset = decode_cursor(
        next_cur,
        str(sample_graph["metadata"]["graph_id"]),
        {
            "node_kind": None,
            "edge_kind": None,
            "resolution_status": None,
            "limit": 2,
        },
    )
    assert decoded_offset == 2


def test_brief_full_graph_bytes_default_matches_settings():
    """Item 1: Validate documented default cap against Settings and load_settings."""
    brief_text = BRIEF_PATH.read_text(encoding="utf-8")

    # Assert documented default mentions 4194304 bytes / 4 MiB and CODESTRUCT_MAX_FULL_GRAPH_BYTES
    match_55 = re.search(
        r"GRAPH_TOO_LARGE.*?max_full_graph_bytes.*?\(default (\d+) bytes / 4 MiB, configurable via `CODESTRUCT_MAX_FULL_GRAPH_BYTES`\)",
        brief_text,
    )
    assert match_55 is not None, (
        "Failed to match default max_full_graph_bytes in section 5.5"
    )
    documented_bytes_55 = int(match_55.group(1))
    assert documented_bytes_55 == 4194304

    match_56 = re.search(
        r"max_full_graph_bytes.*?\(default (\d+) bytes / 4 MiB, configurable via `CODESTRUCT_MAX_FULL_GRAPH_BYTES`\)",
        brief_text,
    )
    assert match_56 is not None, (
        "Failed to match default max_full_graph_bytes in section 5.6"
    )
    documented_bytes_56 = int(match_56.group(1))
    assert documented_bytes_56 == 4194304

    # Verify against Settings default
    settings_default = Settings(authorized_roots={}).max_full_graph_bytes
    assert settings_default == 4 * 1024 * 1024
    assert settings_default == documented_bytes_55

    # Verify load_settings() default preserves 4 MiB
    loaded = load_settings()
    assert loaded.max_full_graph_bytes == 4 * 1024 * 1024


def test_brief_section_5_6_paged_graph_example_and_cursor():
    """Item 2: Test actual markdown JSON example from section 5.6, decode its cursor and follow it."""
    brief_text = BRIEF_PATH.read_text(encoding="utf-8")
    section_56 = brief_text.split("### 5.6", 1)[1].split("### 5.7", 1)[0]
    match = re.search(r"```json\s*(.*?)\s*```", section_56, re.DOTALL)
    assert match is not None, "Failed to locate section 5.6 markdown JSON snippet"
    example = json.loads(match.group(1))

    # Verify documented structure and values
    assert example["api_version"] == "v1"
    assert example["schema_version"] == "1.0.0"
    graph_id = example["metadata"]["graph_id"]
    assert graph_id == "graph_canonical_01"

    # Endpoints guarantee: limit=1 on nodes returns edge_01, which includes both endpoint nodes
    assert len(example["nodes"]) == 2
    assert {n["id"] for n in example["nodes"]} == {
        "node_pkg_module",
        "node_pkg_service_class",
    }
    assert len(example["edges"]) == 1
    assert example["edges"][0]["id"] == "edge_01"
    assert example["page"]["returned_nodes"] == 2
    assert example["page"]["total_nodes"] == 3
    assert example["page"]["returned_edges"] == 1
    assert example["page"]["total_edges"] == 2
    assert example["page"]["partial_load"] is True

    # Test decoding the actual documented cursor
    doc_cursor = example["page"]["next_cursor"]
    assert isinstance(doc_cursor, str)
    filters = {
        "node_kind": None,
        "edge_kind": None,
        "resolution_status": None,
        "limit": 1,
    }
    offset = decode_cursor(doc_cursor, graph_id, filters)
    assert offset == 1

    # Load complete toy graph fixture and verify slice_graph generates this exact page
    toy_path = CONTRACT_DIR / "graph_slice.json"
    toy_graph = json.loads(toy_path.read_text(encoding="utf-8"))
    generated_page1 = slice_graph(
        toy_graph,
        limit=1,
        cursor=None,
        node_kind=None,
        edge_kind=None,
        resolution_status=None,
    )
    assert generated_page1["page"] == example["page"]
    assert generated_page1["nodes"] == example["nodes"]
    assert generated_page1["edges"] == example["edges"]

    # Follow the documented cursor against the toy graph to fetch the next page
    generated_page2 = slice_graph(
        toy_graph,
        limit=1,
        cursor=doc_cursor,
        node_kind=None,
        edge_kind=None,
        resolution_status=None,
    )
    assert generated_page2["page"]["returned_edges"] == 2
    assert generated_page2["page"]["returned_nodes"] == 3
    assert generated_page2["page"]["partial_load"] is True
    # Next cursor from page 2 decodes to offset 2
    cursor_page2 = generated_page2["page"]["next_cursor"]
    assert cursor_page2 is not None
    assert decode_cursor(cursor_page2, graph_id, filters) == 2


def test_diagnostics_nullable_location_and_parser_fixture():
    """Item 3: Diagnostics location can be null; verify with real parser_project diagnostics and schema validation."""
    # Statically parse parser_project (strictly static AST parsing, never executed)
    parser_fixture = REPOSITORY / "tests" / "fixtures" / "parser_project"
    policy = AnalysisPolicy(authorized_roots=(parser_fixture,))
    parsed = parse_project(parser_fixture, policy)
    graph = graph_to_dict(build_graph(parsed))
    diagnostics = graph["diagnostics"]

    # Verify real diagnostics with null location exist
    null_loc_diags = [d for d in diagnostics if d["location"] is None]
    assert len(null_loc_diags) >= 5, (
        f"Expected at least 5 null location diags, found {len(null_loc_diags)}"
    )

    codes = {d["code"] for d in null_loc_diags}
    assert "FILE_ENCODING_FAILURE" in codes
    assert "PATH_EXCLUDED" in codes
    assert "INHERITANCE_CYCLE" in codes

    # Pick real locationless encoding failure diagnostic
    encoding_diag = next(
        d for d in null_loc_diags if d["code"] == "FILE_ENCODING_FAILURE"
    )
    assert encoding_diag["location"] is None
    assert encoding_diag["entity_id"] is None
    assert encoding_diag["edge_id"] is None

    # Validate through DiagnosticsResponse Pydantic schema
    response_payload = {
        "api_version": "v1",
        "request_id": "req_test_null_diag_01",
        "schema_version": "1.0.0",
        "analysis_id": "ana_test_01",
        "provisional": False,
        "items": [encoding_diag],
        "totals": {"error": 1},
    }
    validated = DiagnosticsResponse.model_validate(response_payload)
    assert len(validated.items) == 1
    validated_item = validated.items[0]
    assert validated_item["code"] == "FILE_ENCODING_FAILURE"
    assert validated_item["location"] is None
