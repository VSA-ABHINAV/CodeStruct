"""Tests for directory tree and nested Python symbol hierarchy."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from codestruct.analysis.tree import build_project_tree
from codestruct.api.app import create_app
from codestruct.jobs.models import JobRecord, JobState
from codestruct.settings import Settings
from fastapi.testclient import TestClient


def test_build_project_tree_hierarchy_and_symbols(tmp_path: Path):
    proj_dir = tmp_path / "tree_sample"
    proj_dir.mkdir()

    # Create subdirectories and files
    sub_dir = proj_dir / "pkg"
    sub_dir.mkdir()
    (sub_dir / "notes.txt").write_text("plain text file\n", encoding="utf-8")

    py_file = sub_dir / "worker.py"
    py_file.write_text(
        "class Worker:\n    def run(self):\n        pass\n\ndef helper():\n    pass\n",
        encoding="utf-8",
    )

    # Excluded directories
    (proj_dir / ".git").mkdir()
    (proj_dir / "__pycache__").mkdir()
    (proj_dir / ".venv").mkdir()

    # Mock graph nodes for worker.py
    graph_nodes = [
        {
            "id": "mod_pkg_worker",
            "name": "pkg.worker",
            "qualified_name": "pkg.worker",
            "kind": "module",
            "location": {"path": "pkg/worker.py", "start_line": 1, "start_column": 0},
        },
        {
            "id": "cls_Worker",
            "name": "Worker",
            "qualified_name": "pkg.worker.Worker",
            "kind": "class",
            "location": {"path": "pkg/worker.py", "start_line": 1, "start_column": 0},
        },
        {
            "id": "fn_run",
            "name": "run",
            "qualified_name": "pkg.worker.Worker.run",
            "kind": "method",
            "parent_id": "cls_Worker",
            "location": {"path": "pkg/worker.py", "start_line": 2, "start_column": 4},
        },
        {
            "id": "fn_helper",
            "name": "helper",
            "qualified_name": "pkg.worker.helper",
            "kind": "function",
            "location": {"path": "pkg/worker.py", "start_line": 5, "start_column": 0},
        },
    ]

    tree, excluded = build_project_tree(proj_dir, graph_nodes=graph_nodes)

    assert tree["kind"] == "directory"
    assert tree["id"] == "dir_root"

    # Verify excluded directories
    excluded_paths = {item["path"] for item in excluded}
    assert ".git" in excluded_paths
    assert "__pycache__" in excluded_paths
    assert ".venv" in excluded_paths
    for exc in excluded:
        assert "Default policy excludes" in exc["reason"]

    # Verify children
    child_names = {c["name"]: c for c in tree["children"]}
    assert "pkg" in child_names
    pkg_node = child_names["pkg"]
    assert pkg_node["kind"] == "directory"

    pkg_children = {c["name"]: c for c in pkg_node["children"]}
    assert "notes.txt" in pkg_children
    notes = pkg_children["notes.txt"]
    assert notes["kind"] == "file"
    assert notes["extension"] == ".txt"
    assert "symbols" not in notes

    assert "worker.py" in pkg_children
    worker = pkg_children["worker.py"]
    assert worker["kind"] == "file"
    assert worker["extension"] == ".py"
    assert "symbols" in worker

    # Symbols hierarchy: module -> [class (with method run), function helper]
    symbols = worker["symbols"]
    assert len(symbols) == 1
    mod = symbols[0]
    assert mod["kind"] == "module"
    assert mod["name"] == "pkg.worker"

    # Under module: Worker class and helper function in source order
    top_symbols = mod["children"]
    assert len(top_symbols) == 2
    cls_node = top_symbols[0]
    assert cls_node["kind"] == "class"
    assert cls_node["name"] == "Worker"
    assert len(cls_node["children"]) == 1
    method_node = cls_node["children"][0]
    assert method_node["kind"] == "method"
    assert method_node["name"] == "run"

    func_node = top_symbols[1]
    assert func_node["kind"] == "function"
    assert func_node["name"] == "helper"


def test_build_project_tree_symlink_escape_protection(tmp_path: Path):
    """Verify that symlinks pointing outside the project root are safely skipped."""
    outside_dir = tmp_path / "outside_secret"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("secret\n", encoding="utf-8")

    proj_dir = tmp_path / "inside_proj"
    proj_dir.mkdir()

    symlink_path = proj_dir / "escape_link"
    try:
        os.symlink(outside_dir, symlink_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported in this test environment")

    tree, excluded = build_project_tree(proj_dir)
    assert not any(c["name"] == "escape_link" for c in tree["children"])
    assert any("escape_link" in exc["path"] for exc in excluded)


def test_api_analyses_tree_endpoint(tmp_path: Path):
    proj_dir = tmp_path / "sample_api_proj"
    proj_dir.mkdir()
    (proj_dir / "core.py").write_text("class Alpha:\n    pass\n", encoding="utf-8")

    settings = Settings(authorized_roots={"test_root": proj_dir})
    app = create_app(settings)
    client = TestClient(app)

    service = app.state.analysis_service
    job = JobRecord(
        "ana_tree_test",
        "test_root",
        str(proj_dir),
        state=JobState.COMPLETED,
        percent=100,
        graph={
            "metadata": {"analysis_id": "ana_tree_test"},
            "nodes": [
                {
                    "id": "cls_alpha",
                    "name": "Alpha",
                    "qualified_name": "core.Alpha",
                    "kind": "class",
                    "location": {"path": "core.py", "start_line": 1, "start_column": 0},
                }
            ],
            "edges": [],
        },
    )
    service.registry.add(job)

    # Unknown analysis -> 404
    r_bad = client.get("/api/v1/analyses/unknown_id/tree")
    assert r_bad.status_code == 404

    # Valid analysis -> 200
    r_good = client.get("/api/v1/analyses/ana_tree_test/tree")
    assert r_good.status_code == 200
    data = r_good.json()
    assert data["analysis_id"] == "ana_tree_test"
    assert data["root_id"] == "test_root"
    assert "tree" in data
    assert "excluded" in data
    tree = data["tree"]
    assert any(c["name"] == "core.py" for c in tree["children"])


def test_api_projects_tree_endpoint(tmp_path: Path):
    proj_dir = tmp_path / "sample_proj_root"
    proj_dir.mkdir()
    (proj_dir / "index.py").write_text("x = 1\n", encoding="utf-8")

    settings = Settings(authorized_roots={"root_x": proj_dir})
    app = create_app(settings)
    client = TestClient(app)

    # Unknown root -> 404
    r_bad = client.get("/api/v1/projects/nonexistent/tree")
    assert r_bad.status_code == 404

    # Valid root -> 200
    r_good = client.get("/api/v1/projects/root_x/tree")
    assert r_good.status_code == 200
    data = r_good.json()
    assert data["root_id"] == "root_x"
    assert "tree" in data
