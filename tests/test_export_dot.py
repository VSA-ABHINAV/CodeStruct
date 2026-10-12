"""Tests for Graphviz DOT, SVG, and PNG exports (CS-017)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest
from codestruct.api.app import create_app
from codestruct.graph.export_dot import (
    MAX_EXPORT_EDGES,
    MAX_EXPORT_NODES,
    GraphTooLargeForExportError,
    GraphvizNotFoundError,
    GraphvizOutputLimitError,
    GraphvizRenderError,
    GraphvizTimeoutError,
    find_graphviz_dot,
    graph_to_dot,
    render_graphviz,
)
from codestruct.jobs.models import JobRecord, JobState
from codestruct.settings import Settings
from fastapi.testclient import TestClient

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"


def test_graph_to_dot_generates_valid_syntax():
    graph_dict = {
        "metadata": {"analysis_id": "test_ana_123"},
        "nodes": [
            {
                "id": "node_1",
                "name": "UserModel",
                "kind": "class",
                "qualified_name": "app.models.UserModel",
                "attributes": {"fan_in": "2", "fan_out": "3", "instability": "0.60"},
            },
            {
                "id": "node_2",
                "name": "authenticate",
                "kind": "function",
                "qualified_name": "app.auth.authenticate",
                "attributes": {},
            },
        ],
        "edges": [
            {
                "id": "edge_1",
                "source_id": "node_2",
                "target_id": "node_1",
                "kind": "calls",
                "resolution_status": "resolved",
            }
        ],
    }

    dot = graph_to_dot(graph_dict)
    assert dot.startswith("digraph ")
    assert "node_node_1" in dot
    assert "node_node_2" in dot
    assert "UserModel" in dot
    assert "authenticate" in dot
    assert "node_node_2 -> node_node_1" in dot
    assert 'label="calls"' in dot
    assert dot.endswith("}\n")


def test_graph_to_dot_deterministic():
    # Construct nodes and edges in inverted order
    graph_a = {
        "metadata": {"analysis_id": "det_test"},
        "nodes": [
            {"id": "b", "name": "B", "kind": "function"},
            {"id": "a", "name": "A", "kind": "class"},
        ],
        "edges": [
            {"id": "e2", "source_id": "b", "target_id": "a", "kind": "calls"},
            {"id": "e1", "source_id": "a", "target_id": "b", "kind": "defines"},
        ],
    }
    graph_b = {
        "metadata": {"analysis_id": "det_test"},
        "nodes": [
            {"id": "a", "name": "A", "kind": "class"},
            {"id": "b", "name": "B", "kind": "function"},
        ],
        "edges": [
            {"id": "e1", "source_id": "a", "target_id": "b", "kind": "defines"},
            {"id": "e2", "source_id": "b", "target_id": "a", "kind": "calls"},
        ],
    }

    dot_a = graph_to_dot(graph_a)
    dot_b = graph_to_dot(graph_b)
    assert dot_a == dot_b


def test_graph_to_dot_hostile_escaping():
    hostile_graph = {
        "metadata": {"analysis_id": 'test"; drop database; --'},
        "nodes": [
            {
                "id": 'bad"node\n\\1',
                "name": '<script>alert("xss")</script>\r\n\\path\\file.py',
                "kind": 'weird"kind\t\x00',
                "qualified_name": 'bad.name."foo"\\bar',
            }
        ],
        "edges": [],
    }
    dot = graph_to_dot(hostile_graph)
    # Ensure quotes inside labels are escaped and control chars handled
    assert '\\"' in dot
    assert "\\n" in dot
    assert "\r" not in dot
    assert "\\x00" in dot


def test_graph_to_dot_bounds_enforced():
    # Exceeding MAX_EXPORT_NODES
    too_many_nodes = {
        "metadata": {"analysis_id": "large"},
        "nodes": [
            {"id": f"n{i}", "name": f"N{i}"} for i in range(MAX_EXPORT_NODES + 1)
        ],
        "edges": [],
    }
    with pytest.raises(GraphTooLargeForExportError):
        graph_to_dot(too_many_nodes)

    # Exceeding MAX_EXPORT_EDGES
    too_many_edges = {
        "metadata": {"analysis_id": "large"},
        "nodes": [{"id": "n1"}, {"id": "n2"}],
        "edges": [
            {"id": f"e{i}", "source_id": "n1", "target_id": "n2", "kind": "calls"}
            for i in range(MAX_EXPORT_EDGES + 1)
        ],
    }
    with pytest.raises(GraphTooLargeForExportError):
        graph_to_dot(too_many_edges)


def test_render_graphviz_dot_and_format_validation():
    sample_graph = {
        "metadata": {"analysis_id": "simple"},
        "nodes": [{"id": "n1", "name": "A"}],
        "edges": [],
    }

    # "dot" format returns bytes without invoking any binary
    dot_bytes = render_graphviz(sample_graph, format="dot")
    assert isinstance(dot_bytes, bytes)
    assert b"digraph " in dot_bytes

    # Unsupported format
    with pytest.raises(ValueError, match="Unsupported export format"):
        render_graphviz(sample_graph, format="pdf")


def test_render_graphviz_missing_executable():
    sample_graph = {
        "metadata": {"analysis_id": "simple"},
        "nodes": [{"id": "n1", "name": "A"}],
        "edges": [],
    }

    with mock.patch.dict(
        os.environ, {"CODESTRUCT_GRAPHVIZ_DOT_PATH": "non_existent_dot_bin_9999"}
    ):
        with mock.patch(
            "codestruct.graph.export_dot.find_graphviz_dot", return_value=None
        ):
            with pytest.raises(GraphvizNotFoundError) as exc_info:
                render_graphviz(sample_graph, format="svg")
            assert "Graphviz 'dot' executable was not found" in str(exc_info.value)


def _create_mock_dot_script(tmp_path: Path, script_content: str) -> Path:
    """Helper to create a python executable script that acts as 'dot'."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    script_file = tmp_path / "mock_dot.py"
    script_file.write_text(script_content, encoding="utf-8")
    runner_bat = tmp_path / "mock_dot.bat"
    runner_bat.write_text(f'@"{sys.executable}" "{script_file}" %*\n', encoding="utf-8")
    return runner_bat


def test_render_graphviz_mock_success(tmp_path: Path):
    sample_graph = {
        "metadata": {"analysis_id": "simple"},
        "nodes": [{"id": "n1", "name": "A"}],
        "edges": [],
    }

    script_content = (
        "import sys\n"
        "args = ' '.join(sys.argv)\n"
        "if '-Tsvg' in args:\n"
        '    sys.stdout.buffer.write(b\'<svg width="100" height="100"></svg>\')\n'
        "elif '-Tpng' in args:\n"
        "    sys.stdout.buffer.write(b'\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR')\n"
        "sys.exit(0)\n"
    )
    mock_bat = _create_mock_dot_script(tmp_path, script_content)

    svg_out = render_graphviz(sample_graph, format="svg", dot_path=str(mock_bat))
    assert svg_out.startswith(b"<svg")

    png_out = render_graphviz(sample_graph, format="png", dot_path=str(mock_bat))
    assert png_out.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_graphviz_mock_timeout(tmp_path: Path):
    sample_graph = {
        "metadata": {"analysis_id": "simple"},
        "nodes": [{"id": "n1", "name": "A"}],
        "edges": [],
    }
    script_content = "import time; time.sleep(10)\n"
    mock_bat = _create_mock_dot_script(tmp_path, script_content)

    with pytest.raises(GraphvizTimeoutError):
        render_graphviz(sample_graph, format="svg", dot_path=str(mock_bat), timeout=0.2)


def test_render_graphviz_mock_output_limit(tmp_path: Path):
    sample_graph = {
        "metadata": {"analysis_id": "simple"},
        "nodes": [{"id": "n1", "name": "A"}],
        "edges": [],
    }
    # Output 1000 bytes when limit is 500
    script_content = "import sys; sys.stdout.buffer.write(b'<svg>' + b'A' * 1000 + b'</svg>'); sys.exit(0)\n"
    mock_bat = _create_mock_dot_script(tmp_path, script_content)

    with pytest.raises(GraphvizOutputLimitError):
        render_graphviz(
            sample_graph, format="svg", dot_path=str(mock_bat), max_bytes=500
        )


def test_render_graphviz_mock_render_error(tmp_path: Path):
    sample_graph = {
        "metadata": {"analysis_id": "simple"},
        "nodes": [{"id": "n1", "name": "A"}],
        "edges": [],
    }
    script_content = (
        "import sys; sys.stderr.write('syntax error at line 1\\n'); sys.exit(1)\n"
    )
    mock_bat = _create_mock_dot_script(tmp_path, script_content)

    with pytest.raises(GraphvizRenderError) as exc:
        render_graphviz(sample_graph, format="svg", dot_path=str(mock_bat))
    assert "syntax error" in str(exc.value)


@pytest.fixture(scope="module")
def app_client():
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield app, c
    if hasattr(app.state, "analysis_service"):
        app.state.analysis_service.shutdown()


def test_get_export_dot_endpoint(app_client):
    app, client = app_client
    service = app.state.analysis_service

    job = JobRecord(
        "ana_dot_test",
        "sample",
        str(SAMPLE),
        state=JobState.COMPLETED,
        percent=100,
        graph={
            "metadata": {"analysis_id": "ana_dot_test"},
            "nodes": [
                {
                    "id": "n1",
                    "name": "App",
                    "kind": "class",
                    "qualified_name": "pkg.App",
                }
            ],
            "edges": [],
        },
    )
    service.registry.add(job)

    resp = client.get("/api/v1/analyses/ana_dot_test/export/dot")
    assert resp.status_code == 200
    assert "text/vnd.graphviz" in resp.headers["content-type"]
    assert (
        'filename="codestruct-ana_dot_test.dot"' in resp.headers["content-disposition"]
    )
    assert "digraph " in resp.text
    assert "pkg.App" in resp.text


def test_get_export_dot_when_graph_unavailable(app_client):
    app, client = app_client
    service = app.state.analysis_service

    job = JobRecord(
        "ana_dot_running",
        "sample",
        str(SAMPLE),
        state=JobState.PARSING,
        percent=20,
        graph=None,
    )
    service.registry.add(job)

    resp = client.get("/api/v1/analyses/ana_dot_running/export/dot")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "GRAPH_UNAVAILABLE"


def test_get_export_svg_and_png_diagnostics_when_no_graphviz(app_client):
    app, client = app_client
    with mock.patch("codestruct.graph.export_dot.find_graphviz_dot", return_value=None):
        resp_svg = client.get("/api/v1/analyses/ana_dot_test/export/svg")
        assert resp_svg.status_code == 503
        assert resp_svg.json()["error"]["code"] == "GRAPHVIZ_UNAVAILABLE"
        assert "Graphviz" in resp_svg.json()["error"]["message"]

        resp_png = client.get("/api/v1/analyses/ana_dot_test/export/png")
        assert resp_png.status_code == 503
        assert resp_png.json()["error"]["code"] == "GRAPHVIZ_UNAVAILABLE"


def test_get_export_query_format_routes(app_client):
    app, client = app_client

    # format=dot
    resp_dot = client.get("/api/v1/analyses/ana_dot_test/export?format=dot")
    assert resp_dot.status_code == 200
    assert "text/vnd.graphviz" in resp_dot.headers["content-type"]

    # format=invalid
    resp_bad = client.get("/api/v1/analyses/ana_dot_test/export?format=unsupported_fmt")
    assert resp_bad.status_code == 400
    assert resp_bad.json()["error"]["code"] == "UNSUPPORTED_EXPORT_FORMAT"


def test_get_export_with_mock_graphviz_success(app_client, tmp_path: Path):
    app, client = app_client

    script_content = (
        "import sys\n"
        "args = ' '.join(sys.argv)\n"
        "if '-Tsvg' in args:\n"
        '    sys.stdout.buffer.write(b\'<svg width="50" height="50"></svg>\')\n'
        "elif '-Tpng' in args:\n"
        "    sys.stdout.buffer.write(b'\\x89PNG\\r\\n\\x1a\\n\\x00\\x00')\n"
        "sys.exit(0)\n"
    )
    mock_bat = _create_mock_dot_script(tmp_path, script_content)

    with mock.patch(
        "codestruct.graph.export_dot.find_graphviz_dot", return_value=str(mock_bat)
    ):
        # Route /export/svg
        r_svg = client.get("/api/v1/analyses/ana_dot_test/export/svg")
        assert r_svg.status_code == 200
        assert r_svg.headers["content-type"] == "image/svg+xml"
        assert (
            'filename="codestruct-ana_dot_test.svg"'
            in r_svg.headers["content-disposition"]
        )
        assert r_svg.content.startswith(b"<svg")

        # Route /export/png
        r_png = client.get("/api/v1/analyses/ana_dot_test/export/png")
        assert r_png.status_code == 200
        assert r_png.headers["content-type"] == "image/png"
        assert (
            'filename="codestruct-ana_dot_test.png"'
            in r_png.headers["content-disposition"]
        )
        assert r_png.content.startswith(b"\x89PNG\r\n\x1a\n")

        # Route /export?format=svg
        r_fmt_svg = client.get("/api/v1/analyses/ana_dot_test/export?format=svg")
        assert r_fmt_svg.status_code == 200
        assert r_fmt_svg.headers["content-type"] == "image/svg+xml"


def test_find_graphviz_dot_env_and_search(tmp_path: Path):
    # 1. Environment variable override
    fake_dot = tmp_path / "fake_dot.exe"
    fake_dot.write_text("dummy")
    with mock.patch.dict(os.environ, {"CODESTRUCT_GRAPHVIZ_DOT_PATH": str(fake_dot)}):
        assert find_graphviz_dot() == str(fake_dot)

    # 2. PATH resolution via shutil.which
    with mock.patch.dict(os.environ, {"CODESTRUCT_GRAPHVIZ_DOT_PATH": ""}, clear=False):
        with mock.patch("shutil.which", return_value="C:\\dummy\\dot.exe"):
            assert find_graphviz_dot() == "C:\\dummy\\dot.exe"

    # 3. Not found anywhere
    with mock.patch.dict(
        os.environ,
        {"CODESTRUCT_GRAPHVIZ_DOT_PATH": "", "ProgramFiles": str(tmp_path)},
        clear=False,
    ):
        with mock.patch("shutil.which", return_value=None):
            assert find_graphviz_dot() is None


def test_render_graphviz_invalid_signatures_and_formats(tmp_path: Path):
    graph = {"nodes": [{"id": "n1", "name": "N1", "kind": "class"}], "edges": []}

    # Format dot
    dot_bytes = render_graphviz(graph, format="dot")
    assert b"digraph " in dot_bytes

    # Unsupported format
    with pytest.raises(ValueError, match="Unsupported export format"):
        render_graphviz(graph, format="pdf")

    # Invalid SVG (missing <svg tag)
    bad_svg_script = _create_mock_dot_script(
        tmp_path / "bad_svg",
        "import sys\nsys.stdout.buffer.write(b'NOT AN SVG')\nsys.exit(0)\n",
    )
    with pytest.raises(GraphvizRenderError, match="valid SVG root element"):
        render_graphviz(graph, format="svg", dot_path=str(bad_svg_script))

    # Invalid PNG (missing PNG magic header)
    bad_png_script = _create_mock_dot_script(
        tmp_path / "bad_png",
        "import sys\nsys.stdout.buffer.write(b'NOT A PNG')\nsys.exit(0)\n",
    )
    with pytest.raises(GraphvizRenderError, match="valid PNG file header"):
        render_graphviz(graph, format="png", dot_path=str(bad_png_script))

    # Non-zero exit code
    fail_script = _create_mock_dot_script(
        tmp_path / "fail",
        "import sys\nsys.stderr.write('Fatal syntax error')\nsys.exit(1)\n",
    )
    with pytest.raises(GraphvizRenderError, match="exited with code 1"):
        render_graphviz(graph, format="svg", dot_path=str(fail_script))

    # Spawn error (non-executable or missing path)
    with pytest.raises(GraphvizRenderError, match="Failed to spawn"):
        render_graphviz(
            graph, format="svg", dot_path=str(tmp_path / "nonexistent_dot.exe")
        )


def test_graph_to_dot_edge_status_and_missing_nodes():
    graph = {
        "nodes": [
            {"id": "n1", "name": "Alpha", "kind": "class"},
            {"id": "n2", "name": "Beta", "kind": "function"},
        ],
        "edges": [
            # Edge with unresolved/ambiguous status
            {
                "id": "e1",
                "source_id": "n1",
                "target_id": "n2",
                "kind": "calls",
                "resolution_status": "ambiguous",
            },
            # Edge referencing nonexistent node (should be skipped)
            {
                "id": "e2",
                "source_id": "n1",
                "target_id": "n_missing",
                "kind": "calls",
                "resolution_status": "resolved",
            },
        ],
    }
    dot = graph_to_dot(graph)
    assert 'tooltip="ambiguous"' in dot
    assert "n_missing" not in dot
