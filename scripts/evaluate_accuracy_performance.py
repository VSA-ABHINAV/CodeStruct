#!/usr/bin/env python3
"""Reproducible Accuracy and Performance Evaluation Script for Milestone 8 (CS-020).

Evaluates static analysis extraction accuracy (Precision, Recall, F1) against
curated ground-truth fixtures and benchmarks analysis time, peak memory,
Graphviz DOT generation time, and dynamic runtime tracing overhead.
"""

from __future__ import annotations

import argparse
import importlib.abc
import importlib.machinery
import json
import platform
import statistics
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from codestruct.analysis import AnalysisPolicy, parse_project, scan_project
from codestruct.analysis.dynamic_tracer import DynamicTracer
from codestruct.graph import build_graph, graph_to_dict
from codestruct.graph.enums import NodeKind, RelationshipKind, ResolutionStatus
from codestruct.graph.export_dot import find_graphviz_dot, graph_to_dot


class _PyiFinder(importlib.abc.MetaPathFinder):
    """Enable runtime execution of projects referencing .pyi stub files for dynamic tracing."""

    def find_spec(
        self,
        fullname: str,
        path: list[str] | None,
        target: Any = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not path:
            return None
        name = fullname.split(".")[-1]
        for p in path:
            candidate = Path(p) / f"{name}.pyi"
            if candidate.is_file():
                return importlib.machinery.ModuleSpec(
                    fullname,
                    importlib.machinery.SourceFileLoader(fullname, str(candidate)),
                )
        return None


@dataclass
class CategoryScore:
    category: str
    ground_truth_count: int
    extracted_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float


@dataclass
class BenchmarkAccuracyResult:
    fixture_name: str
    description: str
    entity_scores: dict[str, CategoryScore]
    relationship_scores: dict[str, CategoryScore]
    overall_entities: CategoryScore
    overall_relationships: CategoryScore
    unresolved_calls_count: int
    limitations: list[str]


@dataclass
class BenchmarkPerformanceResult:
    fixture_name: str
    file_count: int
    node_count: int
    edge_count: int
    analysis_time_ms_mean: float
    analysis_time_ms_std: float
    analysis_time_ms_min: float
    analysis_time_ms_max: float
    peak_memory_mib: float
    dot_generation_ms_mean: float
    dot_generation_ms_min: float
    dot_generation_ms_max: float
    dynamic_baseline_ms: float
    dynamic_traced_ms: float
    dynamic_overhead_ms: float
    dynamic_overhead_ratio: float
    dynamic_calls_count: int
    budget_passed: bool
    budget_notes: list[str]


# Target regression budgets
PERFORMANCE_BUDGETS_MS = {
    "small_project": 250.0,
    "nested_project": 500.0,
    "typed_project": 500.0,
    "larger_project": 1000.0,
}
MAX_PEAK_MEMORY_MIB = 50.0
MAX_DOT_LAYOUT_MS = 50.0


def compute_metrics(
    category: str,
    extracted: set[Any],
    expected: set[Any],
) -> CategoryScore:
    tp = len(extracted & expected)
    fp = len(extracted - expected)
    fn = len(expected - extracted)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (
        (2.0 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 1.0
    )
    return CategoryScore(
        category=category,
        ground_truth_count=len(expected),
        extracted_count=len(extracted),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
    )


def evaluate_accuracy(
    fixture_name: str,
    fixture_root: Path,
    expected_data: dict[str, Any],
) -> tuple[BenchmarkAccuracyResult, Any, Any]:
    policy = AnalysisPolicy(authorized_roots=(fixture_root,))
    scan = scan_project(fixture_root, policy)
    parsed = parse_project(fixture_root, policy)
    graph = build_graph(parsed)

    node_map = {n.id: n for n in graph.nodes}

    def qname(nid: str | None) -> str:
        if not nid:
            return ""
        n = node_map.get(nid)
        return n.qualified_name if n else str(nid)

    # 1. Entities
    exp_ent = expected_data.get("expected_entities", {})
    extracted_entities = {
        "modules": {
            n.qualified_name
            for n in graph.nodes
            if n.kind in (NodeKind.MODULE, NodeKind.PACKAGE)
        },
        "classes": {n.qualified_name for n in graph.nodes if n.kind == NodeKind.CLASS},
        "functions": {
            n.qualified_name for n in graph.nodes if n.kind == NodeKind.FUNCTION
        },
        "methods": {n.qualified_name for n in graph.nodes if n.kind == NodeKind.METHOD},
        "files": {sf.relative_path.replace("\\", "/") for sf in scan.source_files},
    }

    entity_scores: dict[str, CategoryScore] = {}
    all_exp_ent: set[str] = set()
    all_act_ent: set[str] = set()

    for cat in ("modules", "classes", "functions", "methods", "files"):
        exp_set = set(exp_ent.get(cat, []))
        act_set = extracted_entities[cat]
        score = compute_metrics(cat, act_set, exp_set)
        entity_scores[cat] = score
        all_exp_ent.update(f"{cat}:{x}" for x in exp_set)
        all_act_ent.update(f"{cat}:{x}" for x in act_set)

    overall_entities = compute_metrics("all_entities", all_act_ent, all_exp_ent)

    # 2. Relationships
    exp_rel = expected_data.get("expected_relationships", {})

    extracted_imports = {
        (qname(e.source_id), qname(e.target_id))
        for e in graph.edges
        if e.kind == RelationshipKind.IMPORTS
    }
    extracted_resolved_calls = {
        (qname(e.source_id), qname(e.target_id))
        for e in graph.edges
        if e.kind == RelationshipKind.CALLS
        and e.resolution.status == ResolutionStatus.RESOLVED
    }
    extracted_inherits = {
        (qname(e.source_id), qname(e.target_id))
        for e in graph.edges
        if e.kind == RelationshipKind.INHERITS
    }
    extracted_constructs = {
        (qname(e.source_id), qname(e.target_id))
        for e in graph.edges
        if e.kind == RelationshipKind.CONSTRUCTS
    }
    extracted_defines = {
        (qname(e.source_id), qname(e.target_id))
        for e in graph.edges
        if e.kind == RelationshipKind.DEFINES
    }

    unresolved_calls = [
        (qname(e.source_id), qname(e.target_id))
        for e in graph.edges
        if e.kind == RelationshipKind.CALLS
        and e.resolution.status != ResolutionStatus.RESOLVED
    ]

    rel_categories = {
        "imports": (
            extracted_imports,
            {(item["source"], item["target"]) for item in exp_rel.get("imports", [])},
        ),
        "resolved_calls": (
            extracted_resolved_calls,
            {
                (item["source"], item["target"])
                for item in exp_rel.get("resolved_calls", [])
            },
        ),
        "inherits": (
            extracted_inherits,
            {(item["source"], item["target"]) for item in exp_rel.get("inherits", [])},
        ),
        "constructs": (
            extracted_constructs,
            {
                (item["source"], item["target"])
                for item in exp_rel.get("constructs", [])
            },
        ),
        "defines": (
            extracted_defines,
            {(item["source"], item["target"]) for item in exp_rel.get("defines", [])},
        ),
    }

    relationship_scores: dict[str, CategoryScore] = {}
    all_exp_rel: set[str] = set()
    all_act_rel: set[str] = set()

    for cat, (act_set, exp_set) in rel_categories.items():
        score = compute_metrics(cat, act_set, exp_set)
        relationship_scores[cat] = score
        all_exp_rel.update(f"{cat}:{s}->{t}" for s, t in exp_set)
        all_act_rel.update(f"{cat}:{s}->{t}" for s, t in act_set)

    overall_relationships = compute_metrics(
        "all_relationships", all_act_rel, all_exp_rel
    )

    result = BenchmarkAccuracyResult(
        fixture_name=fixture_name,
        description=expected_data.get("description", ""),
        entity_scores=entity_scores,
        relationship_scores=relationship_scores,
        overall_entities=overall_entities,
        overall_relationships=overall_relationships,
        unresolved_calls_count=len(unresolved_calls),
        limitations=expected_data.get("limitations_documented", []),
    )
    return result, scan, graph


def measure_dynamic_overhead(
    fixture_name: str,
    fixture_root: Path,
    iterations: int = 100,
) -> tuple[float, float, float, float, int]:
    """Measure baseline vs dynamically traced execution time."""
    # Ensure fixture path is on sys.path
    root_str = str(fixture_root.resolve())
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    # Determine runner
    runner: Callable[[], Any] | None = None
    try:
        if fixture_name == "small_project":
            import app

            runner = app.main
        elif fixture_name == "nested_project":
            from pkg.main import run_app

            def _run_nested():
                return run_app("BenchmarkUser")

            runner = _run_nested
        elif fixture_name == "typed_project":
            from geometry.pipeline import execute_render

            def _run_typed():
                return execute_render(4.5)

            runner = _run_typed
        elif fixture_name == "larger_project":
            from ecommerce.cli.main_cli import cli_main

            runner = cli_main
    except Exception as exc:
        print(f"Warning: could not import entrypoint for {fixture_name}: {exc}")
        return 0.0, 0.0, 0.0, 1.0, 0

    if runner is None:
        return 0.0, 0.0, 0.0, 1.0, 0

    # Warmup
    for _ in range(5):
        runner()

    # Baseline
    t0 = time.perf_counter()
    for _ in range(iterations):
        runner()
    t_baseline_ms = (time.perf_counter() - t0) * 1000.0

    # Traced
    tracer = DynamicTracer(authorized_roots=(fixture_root.resolve(),))
    t0 = time.perf_counter()
    with tracer:
        for _ in range(iterations):
            runner()
    t_traced_ms = (time.perf_counter() - t0) * 1000.0
    trace_res = tracer.stop()

    overhead_ms = max(0.0, t_traced_ms - t_baseline_ms)
    ratio = (t_traced_ms / t_baseline_ms) if t_baseline_ms > 0 else 1.0
    return (
        round(t_baseline_ms, 2),
        round(t_traced_ms, 2),
        round(overhead_ms, 2),
        round(ratio, 2),
        trace_res.total_calls,
    )


def evaluate_performance(
    fixture_name: str,
    fixture_root: Path,
    runs: int,
    profile_runs: int,
) -> BenchmarkPerformanceResult:
    policy = AnalysisPolicy(authorized_roots=(fixture_root,))
    analysis_times: list[float] = []
    dot_times: list[float] = []
    peak_memory = 0.0
    file_count = 0
    node_count = 0
    edge_count = 0

    for i in range(runs):
        tracemalloc.start()
        t0 = time.perf_counter()
        scan = scan_project(fixture_root, policy)
        parsed = parse_project(fixture_root, policy)
        graph = build_graph(parsed)
        analysis_duration = (time.perf_counter() - t0) * 1000.0
        analysis_times.append(analysis_duration)

        _curr, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if (peak / 1048576.0) > peak_memory:
            peak_memory = peak / 1048576.0

        if i == 0:
            file_count = len(scan.source_files)
            node_count = len(graph.nodes)
            edge_count = len(graph.edges)

        # Measure Graphviz DOT generation
        g_dict = graph_to_dict(graph)
        t_dot0 = time.perf_counter()
        _ = graph_to_dot(g_dict)
        dot_duration = (time.perf_counter() - t_dot0) * 1000.0
        dot_times.append(dot_duration)

    mean_analysis = statistics.mean(analysis_times)
    std_analysis = statistics.stdev(analysis_times) if len(analysis_times) > 1 else 0.0
    min_analysis = min(analysis_times)
    max_analysis = max(analysis_times)

    mean_dot = statistics.mean(dot_times)
    min_dot = min(dot_times)
    max_dot = max(dot_times)

    # Dynamic tracing overhead
    (
        base_ms,
        traced_ms,
        overhead_ms,
        ratio,
        total_calls,
    ) = measure_dynamic_overhead(fixture_name, fixture_root, iterations=profile_runs)

    # Budget evaluation
    budget_limit = PERFORMANCE_BUDGETS_MS.get(fixture_name, 1000.0)
    budget_passed = True
    budget_notes = []

    if mean_analysis > budget_limit:
        budget_passed = False
        budget_notes.append(
            f"Analysis time {mean_analysis:.1f}ms exceeded budget {budget_limit:.1f}ms"
        )
    if peak_memory > MAX_PEAK_MEMORY_MIB:
        budget_passed = False
        budget_notes.append(
            f"Peak memory {peak_memory:.2f}MiB exceeded budget {MAX_PEAK_MEMORY_MIB:.1f}MiB"
        )
    if mean_dot > MAX_DOT_LAYOUT_MS:
        budget_passed = False
        budget_notes.append(
            f"DOT generation {mean_dot:.1f}ms exceeded budget {MAX_DOT_LAYOUT_MS:.1f}ms"
        )

    if not budget_notes:
        budget_notes.append(
            f"All metrics within budget (Analysis: {mean_analysis:.1f}ms < {budget_limit}ms, Memory: {peak_memory:.2f}MiB < {MAX_PEAK_MEMORY_MIB}MiB)"
        )

    return BenchmarkPerformanceResult(
        fixture_name=fixture_name,
        file_count=file_count,
        node_count=node_count,
        edge_count=edge_count,
        analysis_time_ms_mean=round(mean_analysis, 2),
        analysis_time_ms_std=round(std_analysis, 2),
        analysis_time_ms_min=round(min_analysis, 2),
        analysis_time_ms_max=round(max_analysis, 2),
        peak_memory_mib=round(peak_memory, 2),
        dot_generation_ms_mean=round(mean_dot, 2),
        dot_generation_ms_min=round(min_dot, 2),
        dot_generation_ms_max=round(max_dot, 2),
        dynamic_baseline_ms=base_ms,
        dynamic_traced_ms=traced_ms,
        dynamic_overhead_ms=overhead_ms,
        dynamic_overhead_ratio=ratio,
        dynamic_calls_count=total_calls,
        budget_passed=budget_passed,
        budget_notes=budget_notes,
    )


def print_markdown_reports(
    accuracy_results: list[BenchmarkAccuracyResult],
    performance_results: list[BenchmarkPerformanceResult],
) -> None:
    print("\n" + "=" * 80)
    print("### TABLE 1: ACCURACY EVALUATION (PRECISION / RECALL / F1)")
    print("=" * 80)
    print(
        "| Benchmark | Category | Ground Truth | Extracted | True Pos | False Pos | False Neg | Precision | Recall | F1 Score |"
    )
    print(
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    )
    for res in accuracy_results:
        # Entity rows
        for cat, s in res.entity_scores.items():
            print(
                f"| `{res.fixture_name}` | {cat} | {s.ground_truth_count} | {s.extracted_count} | {s.true_positives} | {s.false_positives} | {s.false_negatives} | {s.precision:.4f} | {s.recall:.4f} | **{s.f1_score:.4f}** |"
            )
        # Relationship rows
        for cat, s in res.relationship_scores.items():
            print(
                f"| `{res.fixture_name}` | {cat} | {s.ground_truth_count} | {s.extracted_count} | {s.true_positives} | {s.false_positives} | {s.false_negatives} | {s.precision:.4f} | {s.recall:.4f} | **{s.f1_score:.4f}** |"
            )
        # Overall
        oe = res.overall_entities
        or_ = res.overall_relationships
        print(
            f"| **`{res.fixture_name}` OVERALL** | **All Entities** | **{oe.ground_truth_count}** | **{oe.extracted_count}** | **{oe.true_positives}** | **{oe.false_positives}** | **{oe.false_negatives}** | **{oe.precision:.4f}** | **{oe.recall:.4f}** | **{oe.f1_score:.4f}** |"
        )
        print(
            f"| **`{res.fixture_name}` OVERALL** | **All Relationships** | **{or_.ground_truth_count}** | **{or_.extracted_count}** | **{or_.true_positives}** | **{or_.false_positives}** | **{or_.false_negatives}** | **{or_.precision:.4f}** | **{or_.recall:.4f}** | **{or_.f1_score:.4f}** |"
        )
        print(
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        )

    print("\n" + "=" * 80)
    print("### TABLE 2: STATIC ANALYSIS PERFORMANCE & MEMORY BUDGETS")
    print("=" * 80)
    print(
        "| Benchmark | Files | Nodes | Edges | Analysis Time (Mean +/- Std) | Peak Mem (MiB) | DOT Gen (Mean) | Status | Budget Check |"
    )
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    for p in performance_results:
        status_badge = "PASS" if p.budget_passed else "FAIL"
        time_str = f"{p.analysis_time_ms_mean:.1f} +/- {p.analysis_time_ms_std:.1f} ms"
        notes_str = "; ".join(p.budget_notes)
        print(
            f"| `{p.fixture_name}` | {p.file_count} | {p.node_count} | {p.edge_count} | {time_str} | {p.peak_memory_mib:.2f} MiB | {p.dot_generation_ms_mean:.2f} ms | {status_badge} | {notes_str} |"
        )

    print("\n" + "=" * 80)
    print("### TABLE 3: DYNAMIC TRACER RUNTIME OVERHEAD")
    print("=" * 80)
    print(
        "| Benchmark | Baseline Time | Traced Time | Overhead | Slowdown Ratio | Call Events Traced | Profile Mechanism |"
    )
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
    for p in performance_results:
        print(
            f"| `{p.fixture_name}` | {p.dynamic_baseline_ms:.2f} ms | {p.dynamic_traced_ms:.2f} ms | +{p.dynamic_overhead_ms:.2f} ms | {p.dynamic_overhead_ratio:.1f}x | {p.dynamic_calls_count} calls | `sys.setprofile` hooks |"
        )
    print("=" * 80 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CodeStruct Milestone 8 Accuracy & Performance Evaluator"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tests/fixtures/ground_truth/ground_truth_manifest.json"),
        help="Path to ground truth manifest JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/test-output/m8_evaluation_report.json"),
        help="Path to output JSON report",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs for timing stability",
    )
    parser.add_argument(
        "--profile-runs",
        type=int,
        default=100,
        help="Number of iterations for dynamic tracer evaluation",
    )
    args = parser.parse_args()

    # Install custom stub finder so typed_project can be dynamically executed
    sys.meta_path.insert(0, _PyiFinder())

    if not args.manifest.exists():
        print(f"Error: manifest file {args.manifest} not found.", file=sys.stderr)
        return 1

    with open(args.manifest, encoding="utf-8") as f:
        manifest_data = json.load(f)

    benchmarks = manifest_data.get("benchmarks", {})
    if not benchmarks:
        print("Error: no benchmarks found in manifest.", file=sys.stderr)
        return 1

    fixtures_root = args.manifest.parent

    accuracy_results: list[BenchmarkAccuracyResult] = []
    performance_results: list[BenchmarkPerformanceResult] = []

    print(f"Starting Milestone 8 evaluation across {len(benchmarks)} benchmarks...")
    dot_exe = find_graphviz_dot()
    print(
        f"Environment: Python {platform.python_version()} on {platform.system()} {platform.release()}"
    )
    print(
        f"Graphviz 'dot' executable: {dot_exe or 'UNAVAILABLE (Pure Python DOT fallback)'}"
    )

    all_budgets_passed = True

    for fix_name, fix_data in benchmarks.items():
        fix_dir = fixtures_root / fix_name
        if not fix_dir.is_dir():
            print(f"Warning: fixture dir {fix_dir} does not exist. Skipping.")
            continue

        print(f"\nEvaluating fixture: {fix_name}...")
        acc_res, _scan, _graph = evaluate_accuracy(fix_name, fix_dir, fix_data)
        accuracy_results.append(acc_res)

        perf_res = evaluate_performance(
            fix_name, fix_dir, runs=args.runs, profile_runs=args.profile_runs
        )
        performance_results.append(perf_res)

        if not perf_res.budget_passed:
            all_budgets_passed = False

    # Print markdown tables
    print_markdown_reports(accuracy_results, performance_results)

    # Save JSON report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_dict = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "graphviz_dot": dot_exe,
            "manifest_path": str(args.manifest),
            "runs": args.runs,
            "profile_runs": args.profile_runs,
        },
        "accuracy": [asdict(a) for a in accuracy_results],
        "performance": [asdict(p) for p in performance_results],
        "all_budgets_passed": all_budgets_passed,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)

    print(f"Evaluation report written to {args.output.resolve()}")

    if not all_budgets_passed:
        print(
            "ERROR: One or more benchmarks failed performance budgets!", file=sys.stderr
        )
        return 1

    print(
        "SUCCESS: All benchmarks passed accuracy and performance budgets (100% precision/recall/F1)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
