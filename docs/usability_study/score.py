#!/usr/bin/env python3
"""CodeStruct Usability Study scoring tool (Phase 20, Task 2 & 4).

Reads raw per-participant responses (JSON lines, one JSON object per line)
from docs/usability_study/raw_data/, computes per-condition usability metrics
using the standard System Usability Scale (SUS) formula, and writes
docs/usability_study/results.md.

Standard SUS scoring formula:
  - Odd items (1, 3, 5, 7, 9): score contribution = raw_score - 1
  - Even items (2, 4, 6, 8, 10): score contribution = 5 - raw_score
  - SUS = sum of contributions * 2.5  (range 0-100)

This script is unit-testable: import compute_sus_score and compute_condition_stats
directly and pass in known inputs.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths (relative to this file: docs/usability_study/score.py)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # docs/usability_study/
RAW_DATA_DIR = BASE_DIR / "raw_data"
RESULTS_PATH = BASE_DIR / "results.md"

# Standard SUS item keys (1-indexed to match questionnaire.html)
SUS_ITEM_KEYS = [f"item{i}" for i in range(1, 11)]

RUBRIC_KEYS = ["contentQuality", "presentationQuality", "usefulness"]  # usefulness


# ---------------------------------------------------------------------------
# Core computation (unit-testable)
# ---------------------------------------------------------------------------

def compute_sus_score(sus_responses: Dict[str, Any]) -> Optional[float]:
    """Compute a single SUS score (0-100) from a dict of item responses.

    Args:
        sus_responses: dict like {"item1": 4, "item2": 2, ..., "item10": 5}
                       Values should be integers 1-5. Missing or non-integer
                       values return None.

    Returns:
        SUS score as float, or None if any item is missing/invalid.
    """
    contributions: List[float] = []
    for idx, key in enumerate(SUS_ITEM_KEYS, start=1):
        raw = sus_responses.get(key)
        if raw is None:
            return None
        try:
            raw = int(raw)
        except (TypeError, ValueError):
            return None
        if raw < 1 or raw > 5:
            return None
        # Standard SUS: odd items -> score - 1; even items -> 5 - score
        if idx % 2 == 1:  # odd
            contributions.append(raw - 1)
        else:  # even
            contributions.append(5 - raw)
    return sum(contributions) * 2.5


def compute_rubric_mean(rubric: Dict[str, Any]) -> Optional[float]:
    """Compute mean of the 3 rubric items (content, presentation, usefulness)."""
    values: List[float] = []
    for key in RUBRIC_KEYS:
        raw = rubric.get(key)
        if raw is None:
            return None
        try:
            raw = int(raw)
        except (TypeError, ValueError):
            return None
        if raw < 1 or raw > 5:
            return None
        values.append(raw)
    if not values:
        return None
    return sum(values) / len(values)


def compute_condition_stats(responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute per-condition descriptive stats.

    Returns a dict with:
      - n: number of valid responses
      - sus_mean, sus_std: mean and population std dev of SUS scores
      - rubric_mean, rubric_std: mean and population std dev of rubric scores
      - responses: list of per-response dicts with computed scores
    """
    scored: List[Dict[str, Any]] = []
    for resp in responses:
        sus = compute_sus_score(resp.get("sus", {}))
        rubric = compute_rubric_mean(resp.get("rubric", {}))
        if sus is None or rubric is None:
            # Skip incomplete responses for stats but keep note
            continue
        scored.append({
            "participantId": resp.get("participantId"),
            "condition": resp.get("condition"),
            "sus": sus,
            "rubric": rubric,
            "timestamp": resp.get("timestamp"),
        })

    n = len(scored)
    if n == 0:
        return {
            "n": 0,
            "sus_mean": None,
            "sus_std": None,
            "rubric_mean": None,
            "rubric_std": None,
            "responses": [],
        }

    sus_values = [r["sus"] for r in scored]
    rubric_values = [r["rubric"] for r in scored]

    sus_mean = sum(sus_values) / n
    rubric_mean = sum(rubric_values) / n

    # Population standard deviation (divide by n), consistent for small-N studies
    sus_std = statistics.pstdev(sus_values) if n > 1 else 0.0
    rubric_std = statistics.pstdev(rubric_values) if n > 1 else 0.0

    return {
        "n": n,
        "sus_mean": round(sus_mean, 2),
        "sus_std": round(sus_std, 2),
        "rubric_mean": round(rubric_mean, 2),
        "rubric_std": round(rubric_std, 2),
        "responses": scored,
    }


def compute_pct_difference(baseline_mean: Optional[float],
                           advanced_mean: Optional[float]) -> Optional[float]:
    """% difference = (advanced - baseline) / baseline * 100.

    Returns None if either mean is None or baseline is 0.
    """
    if baseline_mean is None or advanced_mean is None:
        return None
    if baseline_mean == 0:
        return None
    return round((advanced_mean - baseline_mean) / baseline_mean * 100, 2)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def load_responses(raw_data_dir: Path) -> List[Dict[str, Any]]:
    """Load all JSON-lines response files from raw_data_dir.

    Each file is expected to contain one JSON object per line (the format
    written by questionnaire.html). Blank lines are skipped.
    """
    responses: List[Dict[str, Any]] = []
    if not raw_data_dir.exists():
        return responses

    for path in sorted(raw_data_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in (".json", ".jsonl", ".txt"):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    responses.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines but keep going
                    continue
    return responses


def write_results(results_path: Path, report_md: str) -> None:
    results_path.write_text(report_md, encoding="utf-8")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_report(baseline_stats: Dict[str, Any],
                 advanced_stats: Dict[str, Any],
                 total_responses: int,
                 pct_diff: Optional[float],
                 raw_file_count: int) -> str:
    lines: List[str] = []
    lines.append("# CodeStruct Usability Evaluation Study — Results")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")

    lines.append("## 1. Overview")
    lines.append("")
    lines.append(f"- Total raw response files read: {raw_file_count}")
    lines.append(f"- Total valid responses: {total_responses}")
    lines.append("")

    lines.append("## 2. Per-Condition Results")
    lines.append("")

    def condition_table(title: str, stats: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        out.append(f"### {title}")
        out.append("")
        out.append(f"- **n (participants):** {stats['n']}")
        if stats['sus_mean'] is not None:
            out.append(f"- **Mean SUS score:** {stats['sus_mean']} (std dev: {stats['sus_std']})")
        else:
            out.append("- **Mean SUS score:** N/A (no valid responses)")
        if stats['rubric_mean'] is not None:
            out.append(f"- **Mean rubric score:** {stats['rubric_mean']} / 5 (std dev: {stats['rubric_std']})")
        else:
            out.append("- **Mean rubric score:** N/A (no valid responses)")
        out.append("")
        out.append("#### Individual responses")
        out.append("")
        out.append("| Participant | SUS | Rubric |")
        out.append("|-------------|-----|--------|")
        for r in stats['responses']:
            out.append(f"| {r['participantId']} | {r['sus']} | {r['rubric']} |")
        out.append("")
        return out

    lines.extend(condition_table("Baseline (Graph / Table / Inspector only)", baseline_stats))
    lines.extend(condition_table("Advanced Architecture", advanced_stats))

    lines.append("## 3. Comparison")
    lines.append("")
    if pct_diff is not None:
        direction = "improvement" if pct_diff > 0 else ("decline" if pct_diff < 0 else "no change")
        lines.append(f"- **% difference (Advanced Architecture vs Baseline):** {pct_diff}% ({direction})")
    else:
        lines.append("- **% difference:** N/A (insufficient data in one or both conditions)")
    lines.append("")

    lines.append("## 4. Methodology & Limitations")
    lines.append("")
    lines.append("- This is a **small-N convenience sample**; results are not statistically generalizable.")
    lines.append("- This is a **self-contained before/after comparison within CodeStruct** comparing the")
    lines.append("  baseline experience (Graph / Table / Inspector only) against the Advanced Architecture")
    lines.append("  feature (Phase 19 component clustering + narrative).")
    lines.append("- This study is **not a replication of, nor does it claim to outperform,** DSAR's own")
    lines.append("  industrial evaluation (Rukmono et al., FSE Companion '26). DSAR's evaluation is a")
    lines.append("  qualitative industrial judgment study with no single published number to numerically beat.")
    lines.append("- Participants explored the same project under both conditions in **counterbalanced order**")
    lines.append("  (half baseline first, half Advanced Architecture first) to control for learning-effect confound.")
    lines.append("- Each participant completed the standard 10-item SUS instrument, a 3-item rubric (content")
    lines.append("  quality, presentation quality, usefulness, 1-5 each), and one comprehension question once per condition.")
    lines.append("- SUS scores use the standard validated formula (odd items: score-1; even items: 5-score; sum x 2.5).")
    lines.append("- The result is reported as-is, whatever it is — if the measured improvement is below 1%, or")
    lines.append("  even negative, that is what gets reported.")
    lines.append("")

    lines.append("## 5. Raw Data")
    lines.append("")
    lines.append("Raw per-participant responses are stored in `docs/usability_study/raw_data/`")
    lines.append("(one JSON object per line per response). Not committed if it contains")
    lines.append("personally identifiable information — handle per your institution's policy.")
    lines.append("")

    return "\n".join(lines)


def run(raw_data_dir: Path = RAW_DATA_DIR,
        results_path: Path = RESULTS_PATH) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[float]]:
    """Main entry point: load responses, compute stats, write results.md.

    Returns (baseline_stats, advanced_stats, pct_diff) for programmatic use.
    """
    responses = load_responses(raw_data_dir)

    baseline_responses = [r for r in responses if r.get("condition") == "baseline"]
    advanced_responses = [r for r in responses if r.get("condition") == "advanced"]

    baseline_stats = compute_condition_stats(baseline_responses)
    advanced_stats = compute_condition_stats(advanced_responses)

    pct_diff = compute_pct_difference(baseline_stats["sus_mean"], advanced_stats["sus_mean"])

    total_valid = baseline_stats["n"] + advanced_stats["n"]

    report_md = build_report(baseline_stats, advanced_stats, total_valid, pct_diff, len(responses))
    write_results(results_path, report_md)

    print(f"Read {len(responses)} raw response(s) from {raw_data_dir}")
    print(f"Baseline: n={baseline_stats['n']}, mean SUS={baseline_stats['sus_mean']}")
    print(f"Advanced: n={advanced_stats['n']}, mean SUS={advanced_stats['sus_mean']}")
    if pct_diff is not None:
        print(f"% difference: {pct_diff}%")
    else:
        print("% difference: N/A")
    print(f"Results written to {results_path}")

    return baseline_stats, advanced_stats, pct_diff


if __name__ == "__main__":
    run()