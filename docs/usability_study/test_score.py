#!/usr/bin/env python3
"""Unit tests for score.py — verifying the standard SUS formula against worked examples.

Standard SUS scoring:
  - Odd items (1,3,5,7,9, positively worded): contribution = score - 1  (max 4 each)
  - Even items (2,4,6,8,10, negatively worded): contribution = 5 - score (max 4 each)
  - SUS = sum of contributions * 2.5  (range 0-100)

Worked examples:
  - Odd=5 (Strongly Agree, positive), Even=1 (Strongly Disagree, negative) -> SUS = 100
  - Odd=1 (Strongly Disagree, positive), Even=5 (Strongly Agree, negative) -> SUS = 0
"""

import sys
from pathlib import Path

# Make score.py importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from score import compute_sus_score, compute_rubric_mean, compute_condition_stats, compute_pct_difference


def test_best_possible_sus_equals_100():
    """Odd items=5 (agree w/ positive), Even items=1 (disagree w/ negative) -> SUS = 100."""
    sus = {f"item{i}": (5 if i % 2 == 1 else 1) for i in range(1, 11)}
    assert compute_sus_score(sus) == 100.0, f"Expected 100.0, got {compute_sus_score(sus)}"


def test_worst_possible_sus_equals_0():
    """Odd items=1 (disagree w/ positive), Even items=5 (agree w/ negative) -> SUS = 0."""
    sus = {f"item{i}": (1 if i % 2 == 1 else 5) for i in range(1, 11)}
    assert compute_sus_score(sus) == 0.0, f"Expected 0.0, got {compute_sus_score(sus)}"


def test_all_neutral_sus_equals_50():
    """All items=3 (neutral) -> SUS = 50 (midpoint)."""
    sus = {f"item{i}": 3 for i in range(1, 11)}
    assert compute_sus_score(sus) == 50.0, f"Expected 50.0, got {compute_sus_score(sus)}"


def test_mixed_sus_hand_computed():
    """Mixed responses verified against hand computation.

    item1=3 (odd: 3-1=2), item2=3 (even: 5-3=2), item3=4 (odd: 3), item4=2 (even: 3),
    item5=5 (odd: 4), item6=1 (even: 4), item7=2 (odd: 1), item8=4 (even: 1),
    item9=5 (odd: 4), item10=2 (even: 3)
    Sum = 2+2+3+3+4+4+1+1+4+3 = 27; SUS = 27 * 2.5 = 67.5
    """
    sus = {"item1": 3, "item2": 3, "item3": 4, "item4": 2, "item5": 5,
           "item6": 1, "item7": 2, "item8": 4, "item9": 5, "item10": 2}
    assert compute_sus_score(sus) == 67.5, f"Expected 67.5, got {compute_sus_score(sus)}"


def test_missing_item_returns_none():
    """Missing SUS item returns None (incomplete response)."""
    sus = {f"item{i}": 3 for i in range(1, 10)}  # item10 missing
    assert compute_sus_score(sus) is None


def test_out_of_range_returns_none():
    """Value outside 1-5 returns None."""
    sus = {f"item{i}": 3 for i in range(1, 11)}
    sus["item1"] = 6
    assert compute_sus_score(sus) is None


def test_rubric_mean():
    """Rubric mean of [4, 5, 3] = 4.0."""
    rubric = {"contentQuality": 4, "presentationQuality": 5, "usefulness": 3}
    assert compute_rubric_mean(rubric) == 4.0


def test_rubric_missing_returns_none():
    """Missing rubric item returns None."""
    rubric = {"contentQuality": 4, "presentationQuality": 5}  # usefulness missing
    assert compute_rubric_mean(rubric) is None


def test_pct_difference():
    """% difference: baseline=50, advanced=75 -> 50%."""
    assert compute_pct_difference(50.0, 75.0) == 50.0


def test_pct_difference_negative():
    """% difference: baseline=80, advanced=60 -> -25%."""
    assert compute_pct_difference(80.0, 60.0) == -25.0


def test_pct_difference_zero_baseline_returns_none():
    """Baseline of 0 returns None (avoid division by zero)."""
    assert compute_pct_difference(0.0, 50.0) is None


def test_condition_stats_basic():
    """Two baseline responses, stats computed correctly."""
    responses = [
        {"participantId": "P01", "condition": "baseline",
         "sus": {f"item{i}": (5 if i % 2 == 1 else 1) for i in range(1, 11)},  # SUS=100
         "rubric": {"contentQuality": 5, "presentationQuality": 5, "usefulness": 5},
         "timestamp": "2026-11-08T00:00:00Z"},
        {"participantId": "P02", "condition": "baseline",
         "sus": {f"item{i}": (1 if i % 2 == 1 else 5) for i in range(1, 11)},  # SUS=0
         "rubric": {"contentQuality": 1, "presentationQuality": 1, "usefulness": 1},
         "timestamp": "2026-11-08T00:00:00Z"},
    ]
    stats = compute_condition_stats(responses)
    assert stats["n"] == 2
    assert stats["sus_mean"] == 50.0  # (100 + 0) / 2
    assert stats["rubric_mean"] == 3.0  # (5 + 1) / 2


def test_condition_stats_advanced_higher():
    """Condition stats separates baseline vs advanced correctly."""
    responses = [
        {"participantId": "P01", "condition": "baseline",
         "sus": {f"item{i}": 3 for i in range(1, 11)},  # SUS=50
         "rubric": {"contentQuality": 3, "presentationQuality": 3, "usefulness": 3},
         "timestamp": "2026-11-08T00:00:00Z"},
        {"participantId": "P02", "condition": "advanced",
         "sus": {f"item{i}": (5 if i % 2 == 1 else 1) for i in range(1, 11)},  # SUS=100
         "rubric": {"contentQuality": 5, "presentationQuality": 5, "usefulness": 5},
         "timestamp": "2026-11-08T00:00:00Z"},
    ]
    baseline = compute_condition_stats([r for r in responses if r["condition"] == "baseline"])
    advanced = compute_condition_stats([r for r in responses if r["condition"] == "advanced"])
    assert baseline["n"] == 1 and baseline["sus_mean"] == 50.0
    assert advanced["n"] == 1 and advanced["sus_mean"] == 100.0
    pct = compute_pct_difference(baseline["sus_mean"], advanced["sus_mean"])
    assert pct == 100.0  # (100-50)/50*100 = 100%


if __name__ == "__main__":
    test_best_possible_sus_equals_100()
    print("PASS: best possible SUS = 100")
    test_worst_possible_sus_equals_0()
    print("PASS: worst possible SUS = 0")
    test_all_neutral_sus_equals_50()
    print("PASS: all neutral SUS = 50")
    test_mixed_sus_hand_computed()
    print("PASS: mixed hand-computed SUS = 67.5")
    test_missing_item_returns_none()
    print("PASS: missing item -> None")
    test_out_of_range_returns_none()
    print("PASS: out of range -> None")
    test_rubric_mean()
    print("PASS: rubric mean 4.0")
    test_rubric_missing_returns_none()
    print("PASS: missing rubric -> None")
    test_pct_difference()
    print("PASS: pct difference 50%")
    test_pct_difference_negative()
    print("PASS: pct difference -25%")
    test_pct_difference_zero_baseline_returns_none()
    print("PASS: zero baseline -> None")
    test_condition_stats_basic()
    print("PASS: condition stats n=2, sus_mean=50, rubric_mean=3")
    test_condition_stats_advanced_higher()
    print("PASS: condition separation + pct difference 100%")
    print("\nAll unit tests passed.")