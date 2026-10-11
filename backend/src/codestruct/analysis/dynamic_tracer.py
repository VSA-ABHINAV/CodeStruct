# ruff: noqa: S110, S603, S607
"""Runtime execution tracing via sys.setprofile conforming to CodeStruct evidence architecture."""

from __future__ import annotations

import dis
import json
import os
import subprocess
import sys
import tempfile
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
        self._durations: dict[tuple[str, str, int, str, str, int, int], float] = (
            defaultdict(float)
        )
        self._call_stacks: dict[int, list[tuple[Any, float]]] = defaultdict(list)
        self._exceptions: set[tuple[str, str, int, int]] = set()
        self._threads: set[int] = set()
        self._start_time: float = 0.0
        self._elapsed: float = 0.0
        self._hook_overhead: float = 0.0
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
        t_hook_start = time.perf_counter()
        try:
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
                    self._call_stacks[tid].append((key, time.perf_counter()))

                elif event in ("return", "c_return"):
                    stack = self._call_stacks.get(tid)
                    if stack:
                        key, t_entry = stack.pop()
                        call_duration = max(0.0, time.perf_counter() - t_entry)
                        self._durations[key] += call_duration

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

                elif event in ("exception", "c_exception"):
                    stack = self._call_stacks.get(tid)
                    if stack:
                        key, t_entry = stack[-1]
                        call_duration = max(0.0, time.perf_counter() - t_entry)
                        self._durations[key] += call_duration

                    code = frame.f_code
                    exc_type = (
                        arg[0] if isinstance(arg, tuple) and len(arg) > 0 else None
                    )
                    # Ignore normal control flow exceptions in iterators / generators
                    if exc_type not in (
                        StopIteration,
                        StopAsyncIteration,
                        GeneratorExit,
                    ):
                        callee_file = code.co_filename
                        if self._is_allowed_path(callee_file):
                            self._exceptions.add(
                                (callee_file, code.co_name, code.co_firstlineno, tid)
                            )
        finally:
            t_hook_end = time.perf_counter()
            self._hook_overhead += max(0.0, t_hook_end - t_hook_start)

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._counts.clear()
            self._durations.clear()
            self._call_stacks.clear()
            self._exceptions.clear()
            self._threads.clear()
            self._total_calls = 0
            self._hook_overhead = 0.0
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
                duration = round(self._durations.get(key, 0.0), 6)
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
                        duration_seconds=duration,
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
            overhead = round(self._hook_overhead, 6)
            if self._total_calls > 0 and overhead == 0.0 and self._hook_overhead > 0:
                overhead = 0.000001
            res = RuntimeTraceResult(
                events=tuple(events),
                total_calls=self._total_calls,
                execution_time_seconds=round(self._elapsed, 4),
                overhead_seconds=overhead,
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

        # Retain ambiguity without assigning an arbitrary candidate (CS-013/CS-014)
        candidate_ids = tuple(c.id for c in matching_candidates)
        return (
            None,
            Confidence.LOW,
            "AMBIGUOUS_RUNTIME_MATCH",
            candidate_ids,
        )

    # Track caller-callee pairs already connected via CALLS
    calls_edge_by_pair: dict[tuple[str, str | None], GraphEdge] = {}
    for edge in new_edges.values():
        if edge.kind is RelationshipKind.CALLS:
            calls_edge_by_pair[(edge.source_id, edge.target_id)] = edge

    # Track node-level runtime invocation counts and exceptions (CS-014)
    node_invocations: Counter[str] = Counter()
    node_calls_out: Counter[str] = Counter()
    node_exceptions: set[str] = set()

    for event in trace.events:
        caller, _caller_conf, _caller_reason, _caller_cands = find_node(
            event.caller_file, event.caller_name, event.caller_line
        )
        callee, callee_conf, callee_reason, callee_cands = find_node(
            event.callee_file, event.callee_name, event.callee_line
        )

        # Only assign node-level statistics to uniquely resolved nodes
        if callee is not None:
            node_invocations[callee.id] += event.call_count
            if event.has_exception:
                node_exceptions.add(callee.id)
        if caller is not None:
            node_calls_out[caller.id] += event.call_count

        if caller is None:
            continue

        loc = caller.location
        if loc is None:
            continue

        is_recursive = callee is not None and caller.id == callee.id
        callee_label = (
            callee.qualified_name if callee is not None else event.callee_name
        )
        call_hash = normalized_text_hash(
            f"runtime:{caller.qualified_name}->{callee_label}:line{event.callee_line}"
        )
        ev_id = evidence_id(
            EvidenceOrigin.RUNTIME_TRACE,
            loc.source_unit_id,
            loc.span,
            "runtime_call",
            call_hash,
        )

        explanation = (
            f"Observed {event.call_count} dynamic runtime invocation(s)"
            + (" [recursive]" if is_recursive else "")
            + f" on thread {event.thread_id} (duration={event.duration_seconds:.6f}s)."
        )
        if callee is None and callee_cands:
            explanation += f" [Ambiguous between {len(callee_cands)} candidates]"

        evidence_rec = EvidenceRecord(
            id=ev_id,
            origin=EvidenceOrigin.RUNTIME_TRACE,
            observation_kind="runtime_call",
            location=loc,
            observed_text_hash=call_hash,
            excerpt=None,
            explanation=explanation,
            expression=f"{caller.name}() -> {event.callee_name}()"
            + (" [recursive]" if is_recursive else ""),
        )
        new_evidence[ev_id] = evidence_rec

        target_node_id = callee.id if callee is not None else None
        pair = (caller.id, target_node_id)
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
            status = (
                ResolutionStatus.RESOLVED
                if (callee is not None and callee_conf is Confidence.EXACT)
                else ResolutionStatus.AMBIGUOUS
            )
            target_key = (
                callee.id
                if callee is not None
                else f"ambig:{event.callee_name}:{event.callee_line}"
            )
            e_id = edge_id(
                RelationshipKind.CALLS,
                caller.id,
                target_key,
                status,
                "runtime_profile",
            )
            edge_attrs = [("runtime_calls", str(event.call_count))]
            if is_recursive:
                edge_attrs.append(("recursive", "true"))
            if callee is None and callee_cands:
                edge_attrs.append(
                    ("ambiguous_candidates", ",".join(sorted(callee_cands)))
                )

            created_edge = GraphEdge(
                id=e_id,
                kind=RelationshipKind.CALLS,
                source_id=caller.id,
                target_id=target_node_id,
                target_reference=event.callee_name if target_node_id is None else None,
                resolution=ResolutionRecord(
                    status,
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


def _get_process_tree_pids(root_pid: int) -> set[int]:
    """Discover root_pid and all its descendant PIDs."""
    if sys.platform != "win32":
        return {root_pid}
    try:
        import ctypes
        import ctypes.wintypes

        kernel32 = ctypes.windll.kernel32
        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1).value

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.wintypes.DWORD),
                ("cntUsage", ctypes.wintypes.DWORD),
                ("th32ProcessID", ctypes.wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.wintypes.ULONG)),
                ("th32ModuleID", ctypes.wintypes.DWORD),
                ("cntThreads", ctypes.wintypes.DWORD),
                ("th32ParentProcessID", ctypes.wintypes.DWORD),
                ("pcPriClassBase", ctypes.wintypes.LONG),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        h = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if h == INVALID_HANDLE_VALUE:
            return {root_pid}
        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if not kernel32.Process32FirstW(h, ctypes.byref(pe)):
                return {root_pid}
            parent_map: dict[int, list[int]] = {}
            while True:
                parent_map.setdefault(pe.th32ParentProcessID, []).append(
                    pe.th32ProcessID
                )
                if not kernel32.Process32NextW(h, ctypes.byref(pe)):
                    break
            descendants = {root_pid}
            queue_pids = [root_pid]
            while queue_pids:
                curr = queue_pids.pop(0)
                for child in parent_map.get(curr, []):
                    if child not in descendants:
                        descendants.add(child)
                        queue_pids.append(child)
            return descendants
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return {root_pid}


def _kill_process_tree(pid: int) -> None:
    """Terminates process and all descendant processes fail-closed."""
    if pid <= 0:
        return
    tree_pids = _get_process_tree_pids(pid)
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
        for p in tree_pids:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(p)],
                    capture_output=True,
                    check=False,
                )
            except Exception:
                pass
    else:
        for p in tree_pids:
            try:
                os.kill(p, 9)
            except OSError:
                pass


def trace_project_target(
    project_root: Path,
    target_file: str | Path,
    entry_function: str | None = None,
    args: Sequence[str] | None = None,
    timeout_seconds: float = 30.0,
    max_events: int = 50_000,
    max_output_bytes: int = 65536,
    cancel_event: threading.Event | None = None,
) -> tuple[bool, RuntimeTraceResult, str | None]:
    """Executes a target python script or module under DynamicTracer in an isolated child process.

    Returns:
        (success, trace_result, error_message)
    """
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

    with tempfile.TemporaryDirectory(prefix="codestruct_rt_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        payload_file = tmp_path / "payload.json"
        result_file = tmp_path / "result.json"

        payload = {
            "project_root": str(resolved_root),
            "target_file": str(resolved_target),
            "entry_function": entry_function,
            "args": list(args or []),
            "max_events": max_events,
            "max_output_bytes": max_output_bytes,
            "result_file": str(result_file),
        }
        with open(payload_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        # Set PYTHONPATH so child process can find codestruct
        env = dict(os.environ)
        src_path = str(Path(__file__).resolve().parents[2])
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{src_path}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else src_path
        )

        start_time = time.monotonic()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "codestruct.analysis.runtime_worker",
                str(payload_file),
            ],
            cwd=str(resolved_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        timed_out = False
        cancelled = False
        deadline = start_time + timeout_seconds

        while True:
            ret = proc.poll()
            if ret is not None:
                break
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.01)

        elapsed = time.monotonic() - start_time

        if timed_out or cancelled:
            _kill_process_tree(proc.pid)
            try:
                proc.wait(timeout=2.0)
            except Exception:
                pass
            msg = (
                f"Target execution exceeded timeout of {timeout_seconds}s"
                if timed_out
                else "Session cancelled"
            )
            return (
                False,
                RuntimeTraceResult((), 0, round(elapsed, 4), 0.0, (), 0),
                msg,
            )

        if not result_file.is_file():
            stderr_text = (
                proc.stderr.read().decode("utf-8", errors="replace")
                if proc.stderr
                else ""
            )
            return (
                False,
                RuntimeTraceResult((), 0, round(elapsed, 4), 0.0, (), 0),
                f"Worker process failed to produce trace output: {stderr_text.strip()}",
            )

        try:
            with open(result_file, encoding="utf-8") as f:
                res_data = json.load(f)
        except Exception as e:
            return (
                False,
                RuntimeTraceResult((), 0, round(elapsed, 4), 0.0, (), 0),
                f"Failed to read trace results: {e}",
            )

        events = tuple(
            RuntimeCallEvent(
                caller_file=e["caller_file"],
                caller_name=e["caller_name"],
                caller_line=e["caller_line"],
                callee_file=e["callee_file"],
                callee_name=e["callee_name"],
                callee_line=e["callee_line"],
                call_count=e["call_count"],
                thread_id=e["thread_id"],
                has_exception=e["has_exception"],
                duration_seconds=e["duration_seconds"],
            )
            for e in res_data.get("events", [])
        )
        trace_res = RuntimeTraceResult(
            events=events,
            total_calls=res_data.get("total_calls", 0),
            execution_time_seconds=res_data.get(
                "execution_time_seconds", round(elapsed, 4)
            ),
            overhead_seconds=res_data.get("overhead_seconds", 0.0),
            threads_observed=tuple(res_data.get("threads_observed", ())),
            exceptions_observed=res_data.get("exceptions_observed", 0),
        )

        return (
            res_data.get("success", False),
            trace_res,
            res_data.get("error"),
        )
