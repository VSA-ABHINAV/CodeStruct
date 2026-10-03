"""Spawn-safe worker entry point; analyzed source is parsed, never imported."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codestruct.analysis import AnalysisPolicy, PythonAstParser, scan_project
from codestruct.analysis.models import ProjectParseResult
from codestruct.graph import build_graph, graph_to_dict


def run_analysis_worker(
    project_root: str, policy_data: dict[str, Any], progress, cancel, output
) -> None:
    try:
        policy = AnalysisPolicy(
            authorized_roots=tuple(
                Path(value) for value in policy_data["authorized_roots"]
            ),
            include_patterns=tuple(policy_data["include_patterns"]),
            exclude_patterns=tuple(policy_data["exclude_patterns"]),
            max_depth=policy_data["max_depth"],
            max_files=policy_data["max_files"],
            max_file_size=policy_data["max_file_size"],
            single_file_name=policy_data.get("single_file_name"),
            compute_metrics=policy_data.get("compute_metrics", False),
        )
        progress.put(("scanning", 15, "SCANNING_PROJECT"))
        scan = scan_project(project_root, policy, cancel.is_set)
        if cancel.is_set() or scan.cancelled:
            output.put({"kind": "cancelled"})
            return
        progress.put(("parsing", 35, "PARSING_FILES"))
        parser = PythonAstParser()
        root = Path(project_root).resolve(strict=True)
        files = []
        diagnostics = list(scan.diagnostics)
        for source_file in scan.source_files:
            if cancel.is_set():
                output.put({"kind": "cancelled"})
                return
            parsed_file = parser.parse(root, source_file, policy, cancel.is_set)
            files.append(parsed_file)
            diagnostics.extend(parsed_file.diagnostics)
        parsed = ProjectParseResult(
            scan=scan,
            files=tuple(files),
            diagnostics=tuple(diagnostics),
            cancelled=cancel.is_set(),
        )
        progress.put(("resolving", 70, "RESOLVING_RELATIONSHIPS"))
        if cancel.is_set():
            output.put({"kind": "cancelled"})
            return
        progress.put(("building_graph", 85, "BUILDING_GRAPH"))
        graph = graph_to_dict(
            build_graph(parsed, compute_metrics=policy.compute_metrics)
        )

        if cancel.is_set():
            output.put({"kind": "cancelled"})
            return
        metadata = graph.get("metadata")
        partial = bool(metadata.get("partial")) if isinstance(metadata, dict) else False
        output.put(
            {
                "kind": "result",
                "graph": graph,
                "partial": partial,
            }
        )
    except BaseException:
        output.put(
            {
                "kind": "error",
                "code": "WORKER_FAILED",
                "message": "The analysis worker could not complete safely.",
            }
        )
