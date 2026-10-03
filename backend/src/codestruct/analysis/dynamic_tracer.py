"""Runtime execution tracing via sys.setprofile conforming to CodeStruct evidence architecture."""

from __future__ import annotations

import dis
import os
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from codestruct.graph.enums import (
    Confidence,
    EvidenceOrigin,
    RelationshipKind,
    ResolutionStatus,
)
from codestruct.graph.identifiers import edge_id, evidence_id, normalized_text_hash
from codestruct.graph.metrics import enrich_nodes_with_metrics
from codestruct.graph.model import (
    EvidenceRecord,
    GraphEdge,
    GraphNode,
    GraphResult,
    ResolutionRecord,
)
from codestruct.graph.validation import assert_valid_graph


@dataclass(frozen=True, slots=True)
class RuntimeCallEvent:
    """Represents a dynamically observed function call invocation."""

    caller_file: str
    caller_name: str
    caller_line: int
    callee_file: str
    callee_name: str
    callee_line: int
    call_count: int
    has_exception: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeTraceResult:
    """Aggregated results from a dynamic profiling session."""

    events: tuple[RuntimeCallEvent, ...]
    total_calls: int
    execution_time_seconds: float


class DynamicTracer:
    """Thread-safe runtime call tracer using sys.setprofile."""

    def __init__(
        self,
        authorized_roots: tuple[Path, ...] = (),
    ) -> None:
        self.authorized_roots = tuple(
            Path(os.path.realpath(os.fspath(root))) for root in authorized_roots
        )
        self._counts: dict[tuple[str, str, int, str, str, int], int] = defaultdict(int)
        self._exceptions: set[tuple[str, str, int]] = set()
        self._start_time: float = 0.0
        self._elapsed: float = 0.0
        self._total_calls: int = 0
        self._active: bool = False
        self._prev_profile: Any = None
        self._last_result: RuntimeTraceResult | None = None

    def _is_within_roots(self, path: Path) -> bool:
        if not self.authorized_roots:
            return True
        norm_path = os.path.normcase(os.path.realpath(os.fspath(path)))
        for root in self.authorized_roots:
            norm_root = os.path.normcase(os.path.realpath(os.fspath(root)))
            try:
                if os.path.commonpath((norm_path, norm_root)) == norm_root:
                    return True
            except ValueError:
                continue
        return False

    def _is_allowed_path(self, file_path: str) -> bool:
        if not file_path or file_path.startswith("<"):
            return False
        try:
            p = Path(os.path.realpath(file_path))
        except (ValueError, OSError):
            return False
        if not self._is_within_roots(p):
            return False
        posix = p.as_posix()
        if "site-packages" in posix or "dist-packages" in posix:
            return False
        return True

    def _profile_callback(self, frame: Any, event: str, arg: Any) -> None:
        if event == "call":
            code = frame.f_code
            callee_file = code.co_filename
            if not self._is_allowed_path(callee_file):
                return

            callee_name = code.co_name
            callee_line = code.co_firstlineno

            back = frame.f_back
            if back is not None:
                caller_code = back.f_code
                caller_file = caller_code.co_filename
                caller_name = caller_code.co_name
                caller_line = caller_code.co_firstlineno
            else:
                caller_file = "<entry>"
                caller_name = "<module>"
                caller_line = 1

            key = (
                caller_file,
                caller_name,
                caller_line,
                callee_file,
                callee_name,
                callee_line,
            )
            self._counts[key] += 1
            self._total_calls += 1

        elif event == "return":
            if arg is None and frame.f_lasti >= 0:
                op = dis.opname[frame.f_code.co_code[frame.f_lasti]]
                if op not in ("RETURN_VALUE", "RETURN_CONST"):
                    code = frame.f_code
                    callee_file = code.co_filename
                    if self._is_allowed_path(callee_file):
                        self._exceptions.add(
                            (callee_file, code.co_name, code.co_firstlineno)
                        )
        elif event == "exception":
            code = frame.f_code
            callee_file = code.co_filename
            if self._is_allowed_path(callee_file):
                self._exceptions.add((callee_file, code.co_name, code.co_firstlineno))

    def start(self) -> None:
        if self._active:
            return
        self._counts.clear()
        self._exceptions.clear()
        self._total_calls = 0
        self._start_time = time.perf_counter()
        self._active = True
        self._prev_profile = sys.getprofile()
        sys.setprofile(self._profile_callback)

    def stop(self) -> RuntimeTraceResult:
        if not self._active:
            return self._last_result or RuntimeTraceResult(
                events=(), total_calls=0, execution_time_seconds=0.0
            )
        sys.setprofile(self._prev_profile)
        self._elapsed = time.perf_counter() - self._start_time
        self._active = False

        events: list[RuntimeCallEvent] = []
        for key, count in self._counts.items():
            (
                caller_file,
                caller_name,
                caller_line,
                callee_file,
                callee_name,
                callee_line,
            ) = key
            has_exc = (callee_file, callee_name, callee_line) in self._exceptions
            events.append(
                RuntimeCallEvent(
                    caller_file=caller_file,
                    caller_name=caller_name,
                    caller_line=caller_line,
                    callee_file=callee_file,
                    callee_name=callee_name,
                    callee_line=callee_line,
                    call_count=count,
                    has_exception=has_exc,
                )
            )

        events.sort(
            key=lambda e: (e.caller_file, e.callee_file, e.callee_name, e.callee_line)
        )
        res = RuntimeTraceResult(
            events=tuple(events),
            total_calls=self._total_calls,
            execution_time_seconds=round(self._elapsed, 4),
        )
        self._last_result = res
        return res

    def __enter__(self) -> DynamicTracer:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


def trace_call(
    func: Callable[[], Any],
    authorized_roots: tuple[Path, ...] = (),
) -> tuple[Any, RuntimeTraceResult]:
    """Execute func under dynamic profile tracing and return (result, trace)."""
    tracer = DynamicTracer(authorized_roots=authorized_roots)
    tracer.start()
    try:
        val = func()
    finally:
        trace = tracer.stop()
    return val, trace


def _norm_path(path_str: str) -> str:
    return PurePosixPath(path_str.replace("\\", "/")).as_posix()


def merge_runtime_trace_into_graph(
    graph: GraphResult,
    trace: RuntimeTraceResult,
) -> GraphResult:
    """Combine static graph with observed runtime call events under EvidenceOrigin.RUNTIME_TRACE."""
    if not trace.events:
        return graph

    # Map nodes by normalized relative path and symbol name / line
    nodes_by_path_and_name: dict[tuple[str, str], list[GraphNode]] = defaultdict(list)
    for node in graph.nodes:
        if node.location:
            p = _norm_path(node.location.path)
            nodes_by_path_and_name[(p, node.name)].append(node)

    new_edges: dict[str, GraphEdge] = {e.id: e for e in graph.edges}
    new_evidence: dict[str, EvidenceRecord] = {ev.id: ev for ev in graph.evidence}

    def find_node(file_path: str, name: str) -> GraphNode | None:
        normalized_target = _norm_path(file_path)
        for (p, n), candidates in nodes_by_path_and_name.items():
            if n == name and (
                normalized_target.endswith(p) or p.endswith(normalized_target)
            ):
                return candidates[0]
        return None

    # Track caller-callee pairs already connected via CALLS
    calls_edge_by_pair: dict[tuple[str, str], GraphEdge] = {}
    for edge in new_edges.values():
        if edge.kind is RelationshipKind.CALLS and edge.target_id:
            calls_edge_by_pair[(edge.source_id, edge.target_id)] = edge

    for event in trace.events:
        caller = find_node(event.caller_file, event.caller_name)
        callee = find_node(event.callee_file, event.callee_name)

        if caller is None or callee is None or caller.id == callee.id:
            continue

        loc = caller.location
        if loc is None:
            continue

        call_hash = normalized_text_hash(
            f"runtime:{caller.qualified_name}->{callee.qualified_name}"
        )
        ev_id = evidence_id(
            EvidenceOrigin.RUNTIME_TRACE,
            loc.source_unit_id,
            loc.span,
            "runtime_call",
            call_hash,
        )

        evidence_rec = EvidenceRecord(
            id=ev_id,
            origin=EvidenceOrigin.RUNTIME_TRACE,
            observation_kind="runtime_call",
            location=loc,
            observed_text_hash=call_hash,
            excerpt=None,
            explanation=f"Observed {event.call_count} dynamic runtime invocation(s) during execution.",
            expression=f"{caller.name}() -> {callee.name}()",
        )
        new_evidence[ev_id] = evidence_rec

        pair = (caller.id, callee.id)
        if pair in calls_edge_by_pair:
            existing = calls_edge_by_pair[pair]
            merged_ev = tuple(sorted(set(existing.evidence_ids) | {ev_id}))
            attrs_dict = dict(existing.attributes)
            attrs_dict["runtime_calls"] = str(
                int(attrs_dict.get("runtime_calls", 0)) + event.call_count
            )
            updated_edge = replace(
                existing,
                evidence_ids=merged_ev,
                attributes=tuple(sorted(attrs_dict.items())),
            )
            new_edges[existing.id] = updated_edge
            calls_edge_by_pair[pair] = updated_edge
        else:
            e_id = edge_id(
                RelationshipKind.CALLS,
                caller.id,
                callee.id,
                ResolutionStatus.RESOLVED,
                "runtime_profile",
            )
            created_edge = GraphEdge(
                id=e_id,
                kind=RelationshipKind.CALLS,
                source_id=caller.id,
                target_id=callee.id,
                target_reference=None,
                resolution=ResolutionRecord(
                    ResolutionStatus.RESOLVED,
                    Confidence.EXACT,
                    "DYNAMIC_RUNTIME_OBSERVATION",
                ),
                evidence_ids=(ev_id,),
                attributes=(("runtime_calls", str(event.call_count)),),
            )
            new_edges[e_id] = created_edge
            calls_edge_by_pair[pair] = created_edge

    # Re-enrich nodes with updated graph metrics
    edges_tuple = tuple(new_edges.values())
    enriched_nodes = enrich_nodes_with_metrics(graph.nodes, edges_tuple)

    # Recompute summary counts
    def count(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(Counter(values).items()))

    summary = replace(
        graph.summary,
        edges_total=len(new_edges),
        evidence_total=len(new_evidence),
        edges_by_kind=count(e.kind.value for e in new_edges.values()),
        edges_by_resolution=count(
            e.resolution.status.value for e in new_edges.values()
        ),
        edges_by_confidence=count(
            e.resolution.confidence.value for e in new_edges.values()
        ),
    )

    merged_graph = replace(
        graph,
        nodes=enriched_nodes,
        edges=edges_tuple,
        evidence=tuple(new_evidence.values()),
        summary=summary,
    )
    assert_valid_graph(merged_graph)
    return merged_graph
