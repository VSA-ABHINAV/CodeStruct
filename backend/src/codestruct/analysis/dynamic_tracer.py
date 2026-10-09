"""Runtime execution tracing via sys.setprofile conforming to CodeStruct evidence architecture."""

from __future__ import annotations

import dis
import os
import sys
import threading
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
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
    thread_id: int = 0
    has_exception: bool = False
    duration_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class RuntimeTraceResult:
    """Aggregated results from a dynamic profiling session."""

    events: tuple[RuntimeCallEvent, ...]
    total_calls: int
    execution_time_seconds: float
    overhead_seconds: float = 0.0
    threads_observed: tuple[int, ...] = ()
    exceptions_observed: int = 0


class DynamicTracer:
    """Thread-safe runtime call tracer using sys.setprofile and threading.setprofile."""

    def __init__(
        self,
        authorized_roots: tuple[Path, ...] = (),
        max_events: int = 50000,
    ) -> None:
        self.authorized_roots = tuple(
            Path(os.path.realpath(os.fspath(root))) for root in authorized_roots
        )
        self.max_events = max_events
        self._lock = threading.RLock()
        self._counts: dict[tuple[str, str, int, str, str, int, int], int] = defaultdict(
            int
        )
        self._exceptions: set[tuple[str, str, int, int]] = set()
        self._threads: set[int] = set()
        self._start_time: float = 0.0
        self._elapsed: float = 0.0
        self._total_calls: int = 0
        self._active: bool = False
        self._prev_sys_profile: Any = None
        self._prev_threading_profile: Any = None
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
        with self._lock:
            if not self._active:
                return

            tid = threading.get_ident()
            self._threads.add(tid)

            if event == "call":
                if self._total_calls >= self.max_events:
                    return

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
                    tid,
                )
                self._counts[key] += 1
                self._total_calls += 1

            elif event == "return":
                code = frame.f_code
                flags = code.co_flags
                # Generator / coroutine flags in Python (CO_GENERATOR 0x20, CO_COROUTINE 0x80, CO_ASYNC_GENERATOR 0x200)
                is_generator_or_coro = bool(flags & (0x20 | 0x80 | 0x200))
                if not is_generator_or_coro and arg is None and frame.f_lasti >= 0:
                    try:
                        op = dis.opname[code.co_code[frame.f_lasti]]
                        if op not in ("RETURN_VALUE", "RETURN_CONST"):
                            callee_file = code.co_filename
                            if self._is_allowed_path(callee_file):
                                self._exceptions.add(
                                    (
                                        callee_file,
                                        code.co_name,
                                        code.co_firstlineno,
                                        tid,
                                    )
                                )
                    except (IndexError, KeyError, ValueError):
                        pass

            elif event == "exception":
                code = frame.f_code
                exc_type = arg[0] if isinstance(arg, tuple) and len(arg) > 0 else None
                # Ignore normal control flow exceptions in iterators / generators
                if exc_type not in (StopIteration, StopAsyncIteration, GeneratorExit):
                    callee_file = code.co_filename
                    if self._is_allowed_path(callee_file):
                        self._exceptions.add(
                            (callee_file, code.co_name, code.co_firstlineno, tid)
                        )

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._counts.clear()
            self._exceptions.clear()
            self._threads.clear()
            self._total_calls = 0
            self._start_time = time.perf_counter()
            self._active = True
            self._prev_sys_profile = sys.getprofile()
            try:
                self._prev_threading_profile = threading.getprofile()
            except AttributeError:
                self._prev_threading_profile = None
            sys.setprofile(self._profile_callback)
            try:
                threading.setprofile(self._profile_callback)
            except AttributeError:
                pass

    def stop(self) -> RuntimeTraceResult:
        with self._lock:
            if not self._active:
                return self._last_result or RuntimeTraceResult(
                    events=(), total_calls=0, execution_time_seconds=0.0
                )
            try:
                sys.setprofile(self._prev_sys_profile)
            except Exception:  # noqa: BLE001
                sys.setprofile(None)
            try:
                if hasattr(threading, "setprofile"):
                    threading.setprofile(self._prev_threading_profile)
            except Exception:  # noqa: BLE001, S110
                pass

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
                    tid,
                ) = key
                has_exc = (
                    callee_file,
                    callee_name,
                    callee_line,
                    tid,
                ) in self._exceptions
                events.append(
                    RuntimeCallEvent(
                        caller_file=caller_file,
                        caller_name=caller_name,
                        caller_line=caller_line,
                        callee_file=callee_file,
                        callee_name=callee_name,
                        callee_line=callee_line,
                        call_count=count,
                        thread_id=tid,
                        has_exception=has_exc,
                    )
                )

            events.sort(
                key=lambda e: (
                    e.caller_file,
                    e.callee_file,
                    e.callee_name,
                    e.callee_line,
                    e.thread_id,
                )
            )
            res = RuntimeTraceResult(
                events=tuple(events),
                total_calls=self._total_calls,
                execution_time_seconds=round(self._elapsed, 4),
                threads_observed=tuple(sorted(self._threads)),
                exceptions_observed=len(self._exceptions),
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
    max_events: int = 50000,
) -> tuple[Any, RuntimeTraceResult]:
    """Execute func under dynamic profile tracing and return (result, trace)."""
    tracer = DynamicTracer(authorized_roots=authorized_roots, max_events=max_events)
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

    # Index nodes by normalized relative path and name / line
    nodes_by_path_and_name: dict[tuple[str, str], list[GraphNode]] = defaultdict(list)
    nodes_by_id: dict[str, GraphNode] = {}
    for node in graph.nodes:
        nodes_by_id[node.id] = node
        if node.location:
            p = _norm_path(node.location.path)
            nodes_by_path_and_name[(p, node.name)].append(node)

    new_edges: dict[str, GraphEdge] = {e.id: e for e in graph.edges}
    new_evidence: dict[str, EvidenceRecord] = {ev.id: ev for ev in graph.evidence}

    # Disambiguate and find target node with qualified line matching (CS-013)
    def find_node(
        file_path: str, name: str, line: int
    ) -> tuple[GraphNode | None, Confidence, str, tuple[str, ...]]:
        normalized_target = _norm_path(file_path)
        matching_candidates: list[GraphNode] = []
        for (p, n), candidates in nodes_by_path_and_name.items():
            if n == name and (
                normalized_target.endswith(p)
                or p.endswith(normalized_target)
                or normalized_target == p
            ):
                matching_candidates.extend(candidates)

        if not matching_candidates:
            return None, Confidence.UNKNOWN, "NO_CANDIDATES", ()

        if len(matching_candidates) == 1:
            return (
                matching_candidates[0],
                Confidence.EXACT,
                "DYNAMIC_RUNTIME_OBSERVATION",
                (),
            )

        # Disambiguate by definition line span
        line_matches = [
            c
            for c in matching_candidates
            if c.location
            and (
                c.location.span.start_line == line
                or (
                    c.location.span.start_line
                    <= line
                    <= (c.location.span.end_line or c.location.span.start_line)
                )
            )
        ]
        if len(line_matches) == 1:
            return line_matches[0], Confidence.EXACT, "DYNAMIC_RUNTIME_OBSERVATION", ()

        # Retain ambiguity if multiple same-named symbols cannot be resolved (CS-013)
        candidate_ids = tuple(c.id for c in matching_candidates)
        return (
            matching_candidates[0],
            Confidence.LOW,
            "AMBIGUOUS_RUNTIME_MATCH",
            candidate_ids,
        )

    # Track caller-callee pairs already connected via CALLS
    calls_edge_by_pair: dict[tuple[str, str], GraphEdge] = {}
    for edge in new_edges.values():
        if edge.kind is RelationshipKind.CALLS and edge.target_id:
            calls_edge_by_pair[(edge.source_id, edge.target_id)] = edge

    # Track node-level runtime invocation counts and exceptions (CS-014)
    node_invocations: Counter[str] = Counter()
    node_calls_out: Counter[str] = Counter()
    node_exceptions: set[str] = set()

    for event in trace.events:
        caller, caller_conf, caller_reason, caller_cands = find_node(
            event.caller_file, event.caller_name, event.caller_line
        )
        callee, callee_conf, callee_reason, callee_cands = find_node(
            event.callee_file, event.callee_name, event.callee_line
        )

        if callee is not None:
            node_invocations[callee.id] += event.call_count
            if event.has_exception:
                node_exceptions.add(callee.id)
        if caller is not None:
            node_calls_out[caller.id] += event.call_count

        if caller is None or callee is None:
            continue

        loc = caller.location
        if loc is None:
            continue

        is_recursive = caller.id == callee.id
        call_hash = normalized_text_hash(
            f"runtime:{caller.qualified_name}->{callee.qualified_name}:line{event.callee_line}"
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
            explanation=(
                f"Observed {event.call_count} dynamic runtime invocation(s)"
                + (" [recursive]" if is_recursive else "")
                + f" on thread {event.thread_id}."
            ),
            expression=f"{caller.name}() -> {callee.name}()"
            + (" [recursive]" if is_recursive else ""),
        )
        new_evidence[ev_id] = evidence_rec

        pair = (caller.id, callee.id)
        if pair in calls_edge_by_pair:
            existing = calls_edge_by_pair[pair]
            merged_ev = tuple(sorted(set(existing.evidence_ids) | {ev_id}))
            attrs_dict = dict(existing.attributes)
            current_calls = int(attrs_dict.get("runtime_calls", 0))
            attrs_dict["runtime_calls"] = str(current_calls + event.call_count)
            if is_recursive:
                attrs_dict["recursive"] = "true"
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
                ResolutionStatus.RESOLVED
                if callee_conf is Confidence.EXACT
                else ResolutionStatus.AMBIGUOUS,
                "runtime_profile",
            )
            edge_attrs = [("runtime_calls", str(event.call_count))]
            if is_recursive:
                edge_attrs.append(("recursive", "true"))
            created_edge = GraphEdge(
                id=e_id,
                kind=RelationshipKind.CALLS,
                source_id=caller.id,
                target_id=callee.id,
                target_reference=None,
                resolution=ResolutionRecord(
                    ResolutionStatus.RESOLVED
                    if callee_conf is Confidence.EXACT
                    else ResolutionStatus.AMBIGUOUS,
                    callee_conf,
                    callee_reason,
                    candidate_ids=callee_cands,
                ),
                evidence_ids=(ev_id,),
                attributes=tuple(sorted(edge_attrs)),
            )
            new_edges[e_id] = created_edge
            calls_edge_by_pair[pair] = created_edge

    # Attach node-level runtime statistics to node attributes (CS-014)
    updated_nodes: list[GraphNode] = []
    for node in graph.nodes:
        attrs_dict = dict(node.attributes)
        if node.id in node_invocations:
            attrs_dict["runtime_invocations"] = str(
                int(attrs_dict.get("runtime_invocations", 0))
                + node_invocations[node.id]
            )
        if node.id in node_calls_out:
            attrs_dict["runtime_calls_out"] = str(
                int(attrs_dict.get("runtime_calls_out", 0)) + node_calls_out[node.id]
            )
        if node.id in node_exceptions:
            attrs_dict["runtime_exception"] = "true"

        updated_nodes.append(
            replace(
                node,
                attributes=tuple(sorted(attrs_dict.items())),
            )
        )

    # Re-enrich nodes with freshly recomputed graph metrics over combined edges (CS-014)
    edges_tuple = tuple(new_edges.values())
    nodes_tuple = tuple(updated_nodes)
    enriched_nodes = enrich_nodes_with_metrics(nodes_tuple, edges_tuple)

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


def trace_project_target(
    project_root: Path,
    target_file: str | Path,
    entry_function: str | None = None,
    args: Sequence[str] | None = None,
    timeout_seconds: float = 30.0,
    max_events: int = 50_000,
) -> tuple[bool, RuntimeTraceResult, str | None]:
    """Executes a target python script or module under DynamicTracer within authorized project root.

    Returns:
        (success, trace_result, error_message)
    """
    import runpy
    import threading
    import time

    resolved_root = Path(project_root).resolve()
    target_path = (
        resolved_root / target_file
        if not Path(target_file).is_absolute()
        else Path(target_file)
    )
    resolved_target = target_path.resolve()

    if not resolved_target.is_relative_to(resolved_root):
        return (
            False,
            RuntimeTraceResult((), 0, 0.0, 0.0, (), 0),
            f"Target file {target_file} is outside project root.",
        )
    if not resolved_target.is_file():
        return (
            False,
            RuntimeTraceResult((), 0, 0.0, 0.0, (), 0),
            f"Target file not found: {target_file}",
        )

    tracer = DynamicTracer(
        authorized_roots=(resolved_root,),
        max_events=max_events,
    )

    orig_argv = list(sys.argv)
    orig_path = list(sys.path)
    if str(resolved_root) not in sys.path:
        sys.path.insert(0, str(resolved_root))
    sys.argv = [str(resolved_target)] + list(args or [])

    result_holder: dict[str, Any] = {
        "trace": None,
        "error": None,
        "success": False,
    }

    start_time = time.monotonic()

    def _exec():
        tracer.start()
        try:
            mod_globals = runpy.run_path(str(resolved_target), run_name="__main__")
            if (
                entry_function
                and entry_function in mod_globals
                and callable(mod_globals[entry_function])
            ):
                mod_globals[entry_function]()
            result_holder["success"] = True
        except Exception as exc:
            result_holder["error"] = str(exc)
            result_holder["success"] = False
        finally:
            result_holder["trace"] = tracer.stop()

    exec_thread = threading.Thread(target=_exec, daemon=True)
    exec_thread.start()
    exec_thread.join(timeout=timeout_seconds)

    elapsed = time.monotonic() - start_time

    # Restore sys.argv and sys.path
    sys.argv = orig_argv
    sys.path = orig_path

    if exec_thread.is_alive():
        tracer.stop()
        return (
            False,
            RuntimeTraceResult((), 0, elapsed, 0.0, (), 0),
            f"Target execution exceeded timeout of {timeout_seconds}s",
        )

    trace = result_holder["trace"]
    if trace is None:
        trace = RuntimeTraceResult((), 0, elapsed, 0.0, (), 0)

    return (
        result_holder["success"],
        trace,
        result_holder["error"],
    )
