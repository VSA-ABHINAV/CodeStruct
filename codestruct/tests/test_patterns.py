"""Tests for CodeStruct Design-Pattern Detection (Phase 13).

Validates the three AST-based pattern heuristics:
- Singleton: __new__ guards and returns a cached class-level instance
- Factory: returns different constructed types across conditional branches
- Observer: iterates a self-owned collection and invokes a method on each element

Also verifies:
- Individual fixture detection
- Directory-level detection via GET /api/patterns
- Negative control on sample_project (0 patterns, no false positives)
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure codestruct package root is in sys.path
TESTS_DIR = Path(__file__).resolve().parent
CODESTRUCT_DIR = TESTS_DIR.parent
if str(CODESTRUCT_DIR) not in sys.path:
    sys.path.insert(0, str(CODESTRUCT_DIR))

from backend.main import app
from backend.analyzer import analyze_project
from backend.patterns import detect_patterns
from backend.schemas import PatternsResponse

FIXTURES_DIR = TESTS_DIR / "pattern_fixtures"
SAMPLE_PROJECT_DIR = CODESTRUCT_DIR / "sample_project"


@pytest.fixture(scope="module")
def client():
    """Create a TestClient instance for the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


def test_singleton_fixture_detected_individually():
    """Singleton fixture is detected with exact evidence string."""
    singleton_file = FIXTURES_DIR / "singleton_example.py"
    graph = analyze_project(str(singleton_file))
    patterns = detect_patterns(graph)

    assert len(patterns) == 1, f"Expected exactly 1 pattern, got: {patterns}"
    match = patterns[0]
    assert match["pattern"] == "Singleton"
    assert match["symbol_id"] == "singleton_example.DatabaseConnection"
    assert match["evidence"] == "__new__ guards and returns a cached class-level instance"


def test_factory_fixture_detected_individually():
    """Factory fixture is detected with exact evidence string."""
    factory_file = FIXTURES_DIR / "factory_example.py"
    graph = analyze_project(str(factory_file))
    patterns = detect_patterns(graph)

    assert len(patterns) == 1, f"Expected exactly 1 pattern, got: {patterns}"
    match = patterns[0]
    assert match["pattern"] == "Factory"
    assert match["symbol_id"] == "factory_example.create_shape"
    assert match["evidence"] == "returns different constructed types across conditional branches"


def test_observer_fixture_detected_individually():
    """Observer fixture is detected with exact evidence string."""
    observer_file = FIXTURES_DIR / "observer_example.py"
    graph = analyze_project(str(observer_file))
    patterns = detect_patterns(graph)

    assert len(patterns) == 1, f"Expected exactly 1 pattern, got: {patterns}"
    match = patterns[0]
    assert match["pattern"] == "Observer"
    assert match["symbol_id"] == "observer_example.EventDispatcher"
    assert match["evidence"] == "iterates a self-owned collection and invokes a method on each element"


def test_api_patterns_endpoint_fixtures_directory(client):
    """Analyzing the pattern_fixtures directory returns all 3 patterns via GET /api/patterns."""
    analyze_resp = client.post("/api/analyze", json={"project_path": str(FIXTURES_DIR)})
    assert analyze_resp.status_code == 200, f"Analysis failed: {analyze_resp.text}"

    resp = client.get("/api/patterns")
    assert resp.status_code == 200, f"Patterns lookup failed: {resp.text}"

    data = resp.json()
    response_model = PatternsResponse(**data)
    patterns = response_model.patterns

    assert len(patterns) == 3, f"Expected 3 patterns, got: {patterns}"

    patterns_by_type = {p.pattern: p for p in patterns}
    assert "Singleton" in patterns_by_type
    assert "Factory" in patterns_by_type
    assert "Observer" in patterns_by_type

    # Verify Singleton
    singleton = patterns_by_type["Singleton"]
    assert "DatabaseConnection" in singleton.symbol_id
    assert singleton.evidence == "__new__ guards and returns a cached class-level instance"

    # Verify Factory
    factory = patterns_by_type["Factory"]
    assert "create_shape" in factory.symbol_id
    assert factory.evidence == "returns different constructed types across conditional branches"

    # Verify Observer
    observer = patterns_by_type["Observer"]
    assert "EventDispatcher" in observer.symbol_id
    assert observer.evidence == "iterates a self-owned collection and invokes a method on each element"


def test_api_patterns_negative_control_sample_project(client):
    """Analyzing sample_project returns zero patterns (no false positives)."""
    analyze_resp = client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})
    assert analyze_resp.status_code == 200, f"Analysis failed: {analyze_resp.text}"

    resp = client.get("/api/patterns")
    assert resp.status_code == 200, f"Patterns lookup failed: {resp.text}"

    data = resp.json()
    response_model = PatternsResponse(**data)
    assert len(response_model.patterns) == 0, (
        f"Expected zero patterns in sample_project, got: {response_model.patterns}"
    )


def test_api_patterns_empty_when_no_project_analyzed(client):
    """GET /api/patterns returns empty list when no project has been analyzed yet."""
    # Reset app state last_graph
    app.state.last_graph = None
    import backend.api
    backend.api._LAST_GRAPH = None

    resp = client.get("/api/patterns")
    assert resp.status_code == 200
    assert resp.json() == {"patterns": []}


def test_factory_requires_distinct_project_classes(tmp_path):
    """A function returning the same class in multiple branches is NOT a Factory."""
    test_file = tmp_path / "same_class.py"
    test_file.write_text("""
class Widget:
    pass

def make_widget(mode):
    if mode == 1:
        return Widget()
    else:
        return Widget()
""", encoding="utf-8")

    graph = analyze_project(str(test_file))
    patterns = detect_patterns(graph)
    factory_patterns = [p for p in patterns if p["pattern"] == "Factory"]
    assert len(factory_patterns) == 0, "Should not flag function returning only 1 distinct class"


def test_observer_requires_iteration_over_self_attribute(tmp_path):
    """Iterating over a function parameter or local variable does NOT flag Observer."""
    test_file = tmp_path / "not_observer.py"
    test_file.write_text("""
class Helper:
    def process_items(self, external_list):
        for item in external_list:
            item.do_something()
""", encoding="utf-8")

    graph = analyze_project(str(test_file))
    patterns = detect_patterns(graph)
    observer_patterns = [p for p in patterns if p["pattern"] == "Observer"]
    assert len(observer_patterns) == 0, "Should not flag class iterating non-self parameter"

