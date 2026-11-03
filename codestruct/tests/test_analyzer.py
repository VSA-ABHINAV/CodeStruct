"""Tests for CodeStruct AST Static Analysis Engine (Phase 1).

Validates the deterministic test oracle counts and error-handling behavior specified
in Sections 4.1, 5, and 7 of CodeStruct_Project_Plan.md.
"""

import sys
from pathlib import Path
import pytest

# Ensure codestruct package root is in sys.path
TESTS_DIR = Path(__file__).resolve().parent
CODESTRUCT_DIR = TESTS_DIR.parent
if str(CODESTRUCT_DIR) not in sys.path:
    sys.path.insert(0, str(CODESTRUCT_DIR))

from backend.analyzer import analyze_project

SAMPLE_PROJECT_DIR = CODESTRUCT_DIR / "sample_project"
SAMPLE_PROJECT_FILE = SAMPLE_PROJECT_DIR / "sample_project.py"


@pytest.fixture
def sample_analysis():
    """Run analysis on the deterministic sample project fixture."""
    assert SAMPLE_PROJECT_FILE.exists(), f"Sample project file missing at {SAMPLE_PROJECT_FILE}"
    return analyze_project(str(SAMPLE_PROJECT_DIR))


def test_sample_project_node_counts(sample_analysis):
    """Section 7 Oracle: node_count = 16 (1 module + 4 classes + 2 functions + 9 methods)."""
    summary = sample_analysis["summary"]
    nodes = sample_analysis["nodes"]

    assert summary["node_count"] == 16, f"Expected 16 nodes, got {summary['node_count']}"
    assert len(nodes) == 16, f"Expected len(nodes) == 16, got {len(nodes)}"
    assert summary["module_count"] == 1, f"Expected 1 module, got {summary['module_count']}"
    assert summary["class_count"] == 4, f"Expected 4 classes, got {summary['class_count']}"
    assert summary["function_count"] == 2, f"Expected 2 functions, got {summary['function_count']}"
    assert summary["method_count"] == 9, f"Expected 9 methods, got {summary['method_count']}"

    # Verify specific node IDs
    node_ids = {node["id"] for node in nodes}
    expected_ids = {
        "sample_project",
        "sample_project.Animal",
        "sample_project.Animal.__init__",
        "sample_project.Animal.speak",
        "sample_project.Animal.describe",
        "sample_project.Dog",
        "sample_project.Dog.fetch",
        "sample_project.Dog.speak",
        "sample_project.Cat",
        "sample_project.Cat.climb_tree",
        "sample_project.Cat.speak",
        "sample_project.Zoo",
        "sample_project.Zoo.__init__",
        "sample_project.Zoo.add_animal",
        "sample_project.build_zoo",
        "sample_project.main",
    }
    assert node_ids == expected_ids, f"Mismatch in node IDs. Diff: {expected_ids.symmetric_difference(node_ids)}"


def test_sample_project_inherits_edges(sample_analysis):
    """Section 7 Oracle: inherits edges = 2 (Dog->Animal, Cat->Animal)."""
    inherits_edges = [e for e in sample_analysis["edges"] if e["type"] == "inherits"]
    assert len(inherits_edges) == 2, f"Expected 2 inherits edges, got {len(inherits_edges)}"

    inherits_pairs = {(e["source"], e["target"]) for e in inherits_edges}
    expected_inherits = {
        ("sample_project.Dog", "sample_project.Animal"),
        ("sample_project.Cat", "sample_project.Animal"),
    }
    assert inherits_pairs == expected_inherits, f"Unexpected inherits pairs: {inherits_pairs}"


def test_sample_project_defines_edges(sample_analysis):
    """Section 7 Oracle: defines edges = 15."""
    defines_edges = [e for e in sample_analysis["edges"] if e["type"] == "defines"]
    assert len(defines_edges) == 15, f"Expected 15 defines edges, got {len(defines_edges)}"

    defines_pairs = {(e["source"], e["target"]) for e in defines_edges}
    expected_defines = {
        # Module defines classes and functions
        ("sample_project", "sample_project.Animal"),
        ("sample_project", "sample_project.Dog"),
        ("sample_project", "sample_project.Cat"),
        ("sample_project", "sample_project.Zoo"),
        ("sample_project", "sample_project.build_zoo"),
        ("sample_project", "sample_project.main"),
        # Classes define methods
        ("sample_project.Animal", "sample_project.Animal.__init__"),
        ("sample_project.Animal", "sample_project.Animal.speak"),
        ("sample_project.Animal", "sample_project.Animal.describe"),
        ("sample_project.Dog", "sample_project.Dog.fetch"),
        ("sample_project.Dog", "sample_project.Dog.speak"),
        ("sample_project.Cat", "sample_project.Cat.climb_tree"),
        ("sample_project.Cat", "sample_project.Cat.speak"),
        ("sample_project.Zoo", "sample_project.Zoo.__init__"),
        ("sample_project.Zoo", "sample_project.Zoo.add_animal"),
    }
    assert defines_pairs == expected_defines, f"Unexpected defines pairs: {defines_pairs}"


def test_sample_project_constructs_edges(sample_analysis):
    """Section 7 Oracle: constructs edges = 3 (build_zoo->Zoo, build_zoo->Dog, build_zoo->Cat)."""
    constructs_edges = [e for e in sample_analysis["edges"] if e["type"] == "constructs"]
    assert len(constructs_edges) == 3, f"Expected 3 constructs edges, got {len(constructs_edges)}"

    constructs_pairs = {(e["source"], e["target"]) for e in constructs_edges}
    expected_constructs = {
        ("sample_project.build_zoo", "sample_project.Zoo"),
        ("sample_project.build_zoo", "sample_project.Dog"),
        ("sample_project.build_zoo", "sample_project.Cat"),
    }
    assert constructs_pairs == expected_constructs, f"Unexpected constructs pairs: {constructs_pairs}"


def test_sample_project_calls_edges(sample_analysis):
    """Section 7 Oracle: main->build_zoo and build_zoo->Zoo.add_animal must exist."""
    calls_pairs = {(e["source"], e["target"]) for e in sample_analysis["edges"] if e["type"] == "calls"}

    assert ("sample_project.main", "sample_project.build_zoo") in calls_pairs, (
        f"Missing call main -> build_zoo in {calls_pairs}"
    )
    assert ("sample_project.build_zoo", "sample_project.Zoo.add_animal") in calls_pairs, (
        f"Missing call build_zoo -> Zoo.add_animal in {calls_pairs}"
    )


def test_sample_project_errors_empty(sample_analysis):
    """Section 7 Oracle: errors = empty list for valid project."""
    assert sample_analysis["errors"] == [], f"Expected no errors, got {sample_analysis['errors']}"


def test_graceful_error_handling(tmp_path):
    """A directory containing one broken .py file does not crash analysis; the broken file appears in errors."""
    valid_file = tmp_path / "valid.py"
    valid_file.write_text("def valid_function():\n    return 42\n", encoding="utf-8")

    broken_file = tmp_path / "broken.py"
    broken_file.write_text("def broken_syntax( syntax error here\n", encoding="utf-8")

    # Analysis must not raise an exception
    result = analyze_project(str(tmp_path))

    # Valid file was processed
    node_ids = {n["id"] for n in result["nodes"]}
    assert "valid" in node_ids
    assert "valid.valid_function" in node_ids

    # Broken file appears in errors
    assert len(result["errors"]) == 1
    assert "broken.py" in result["errors"][0]["file_path"]
    assert "SyntaxError" in result["errors"][0]["message"]

