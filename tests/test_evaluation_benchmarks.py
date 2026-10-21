"""Automated regression tests for Milestone 8 evaluation benchmarks (CS-020).

Validates that static extraction maintains 100% precision/recall/F1 against
ground truth fixtures and strictly satisfies performance and memory budgets.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evaluate_accuracy_performance import (
    PERFORMANCE_BUDGETS_MS,
    _PyiFinder,
    evaluate_accuracy,
    evaluate_performance,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "ground_truth"
MANIFEST_PATH = FIXTURES_DIR / "ground_truth_manifest.json"


@pytest.fixture(scope="module", autouse=True)
def setup_pyi_finder():
    import sys

    finder = _PyiFinder()
    sys.meta_path.insert(0, finder)
    yield
    if finder in sys.meta_path:
        sys.meta_path.remove(finder)


def load_manifest() -> dict:
    assert MANIFEST_PATH.exists(), f"Manifest missing at {MANIFEST_PATH}"
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.unit
def test_ground_truth_manifest_structure() -> None:
    manifest = load_manifest()
    assert manifest.get("schema_version") == "1.0"
    benchmarks = manifest.get("benchmarks", {})
    assert set(benchmarks.keys()) == {
        "small_project",
        "nested_project",
        "typed_project",
        "larger_project",
    }
    for _name, data in benchmarks.items():
        assert "expected_entities" in data
        assert "expected_relationships" in data
        assert "limitations_documented" in data


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture_name",
    ["small_project", "nested_project", "typed_project", "larger_project"],
)
def test_accuracy_ground_truth_precision_recall_f1(fixture_name: str) -> None:
    manifest = load_manifest()
    fixture_data = manifest["benchmarks"][fixture_name]
    fixture_dir = FIXTURES_DIR / fixture_name
    assert fixture_dir.is_dir()

    res, scan, graph = evaluate_accuracy(fixture_name, fixture_dir, fixture_data)

    # 1. Verify all entity category scores
    for cat, score in res.entity_scores.items():
        assert score.false_positives == 0, (
            f"FP in {fixture_name} entity {cat}: extracted {score.extracted_count} vs expected {score.ground_truth_count}"
        )
        assert score.false_negatives == 0, (
            f"FN in {fixture_name} entity {cat}: extracted {score.extracted_count} vs expected {score.ground_truth_count}"
        )
        assert score.precision == 1.0, (
            f"Precision degraded in {fixture_name} entity {cat}"
        )
        assert score.recall == 1.0, f"Recall degraded in {fixture_name} entity {cat}"
        assert score.f1_score == 1.0, f"F1 degraded in {fixture_name} entity {cat}"

    # 2. Verify all relationship category scores
    for cat, score in res.relationship_scores.items():
        assert score.false_positives == 0, (
            f"FP in {fixture_name} relationship {cat}: extracted {score.extracted_count} vs expected {score.ground_truth_count}"
        )
        assert score.false_negatives == 0, (
            f"FN in {fixture_name} relationship {cat}: extracted {score.extracted_count} vs expected {score.ground_truth_count}"
        )
        assert score.precision == 1.0, (
            f"Precision degraded in {fixture_name} relationship {cat}"
        )
        assert score.recall == 1.0, (
            f"Recall degraded in {fixture_name} relationship {cat}"
        )
        assert score.f1_score == 1.0, (
            f"F1 degraded in {fixture_name} relationship {cat}"
        )

    # 3. Verify overall metrics
    assert res.overall_entities.f1_score == 1.0
    assert res.overall_relationships.f1_score == 1.0


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture_name",
    ["small_project", "nested_project", "typed_project", "larger_project"],
)
def test_performance_budgets(fixture_name: str) -> None:
    fixture_dir = FIXTURES_DIR / fixture_name
    perf = evaluate_performance(fixture_name, fixture_dir, runs=2, profile_runs=10)

    budget_ms = PERFORMANCE_BUDGETS_MS[fixture_name]
    assert perf.analysis_time_ms_mean < budget_ms, (
        f"{fixture_name} analysis time {perf.analysis_time_ms_mean}ms exceeded budget {budget_ms}ms"
    )
    assert perf.peak_memory_mib < 50.0, (
        f"{fixture_name} peak memory {perf.peak_memory_mib}MiB exceeded 50.0MiB"
    )
    assert perf.dot_generation_ms_mean < 50.0, (
        f"{fixture_name} DOT generation {perf.dot_generation_ms_mean}ms exceeded 50.0ms"
    )
    assert perf.budget_passed is True
