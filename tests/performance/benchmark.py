from __future__ import annotations

import json
import platform
import shutil
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

from codestruct.analysis import AnalysisPolicy, parse_project, scan_project
from codestruct.graph import build_graph, graph_to_json, validate_graph
from codestruct.storage import SQLiteRepository
from generate_projects import add_partial_file, generate_project

REPOSITORY = Path(__file__).resolve().parents[2]
OUTPUT = (REPOSITORY / "tests" / "test-output" / "benchmarks").resolve()


def timed(callable_):
    start = time.perf_counter()
    value = callable_()
    return value, (time.perf_counter() - start) * 1000


def measure(name: str, count: int, runs: int, **options):
    root = OUTPUT / name
    generate_project(root, count, **options)
    if name == "partial":
        add_partial_file(root)
    policy = AnalysisPolicy(
        authorized_roots=(root,), max_files=max(10, count * 2), max_depth=50
    )
    samples = []
    for _ in range(runs):
        tracemalloc.start()
        scan, scan_ms = timed(lambda: scan_project(root, policy))
        parsed, parse_ms = timed(lambda: parse_project(root, policy))
        graph, graph_ms = timed(lambda: build_graph(parsed))
        _, validation_ms = timed(lambda: validate_graph(graph))
        payload, serialization_ms = timed(lambda: graph_to_json(graph))
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        database = OUTPUT / f"{name}.sqlite3"
        repository = SQLiteRepository(database, 300)
        _, write_ms = timed(
            lambda: repository.store_cache(
                f"{name}-{len(samples)}", json.loads(payload), "policy", "project"
            )
        )
        _, read_ms = timed(lambda: repository.find_cache(f"{name}-{len(samples)}"))
        samples.append(
            {
                "scan_ms": scan_ms,
                "parse_ms": parse_ms,
                "resolve_graph_ms": graph_ms,
                "validation_ms": validation_ms,
                "serialization_ms": serialization_ms,
                "db_write_ms": write_ms,
                "db_read_ms": read_ms,
                "peak_mib": peak / 1048576,
                "json_mib": len(payload.encode()) / 1048576,
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "files": len(scan.source_files),
            }
        )
    summary = {
        key: {
            "median": round(statistics.median(item[key] for item in samples), 3),
            "worst": round(max(item[key] for item in samples), 3),
        }
        for key in (
            "scan_ms",
            "parse_ms",
            "resolve_graph_ms",
            "validation_ms",
            "serialization_ms",
            "db_write_ms",
            "db_read_ms",
            "peak_mib",
            "json_mib",
        )
    }
    return {
        "name": name,
        "requested_files": count,
        "runs": runs,
        "counts": {key: samples[-1][key] for key in ("files", "nodes", "edges")},
        "summary": summary,
    }


def main():
    if OUTPUT.exists():
        if REPOSITORY not in OUTPUT.parents:
            raise RuntimeError("unsafe benchmark output")
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    try:
        results = [
            measure("small", 20, 3),
            measure("medium", 300, 3),
            measure("large", 1500, 1),
            measure("dense", 40, 2, dense_cycle=20),
            measure("definitions", 10, 2, definitions=100),
            measure("partial", 30, 2),
        ]
        print(
            json.dumps(
                {
                    "environment": {
                        "os": platform.platform(),
                        "python": sys.version.split()[0],
                    },
                    "results": results,
                },
                indent=2,
            )
        )
    finally:
        if REPOSITORY not in OUTPUT.parents:
            raise RuntimeError("unsafe benchmark cleanup")
        shutil.rmtree(OUTPUT)


if __name__ == "__main__":
    main()
