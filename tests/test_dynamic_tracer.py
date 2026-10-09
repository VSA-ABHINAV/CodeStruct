"""Tests for dynamic analysis tracer and unified graph merging."""

from __future__ import annotations

import pytest
from codestruct.analysis.dynamic_tracer import (
    DynamicTracer,
    merge_runtime_trace_into_graph,
    trace_call,
)
from codestruct.analysis.policy import AnalysisPolicy
from codestruct.analysis.python_parser import parse_project
from codestruct.graph.builder import build_graph
from codestruct.graph.enums import EvidenceOrigin


def helper_func_b(val: int) -> int:
    return val * 2


def helper_func_a(val: int) -> int:
    return helper_func_b(val) + 1


def failing_func():
    raise ValueError("intentional error")


@pytest.mark.unit
def test_dynamic_tracer_captures_function_calls():
    def target():
        return helper_func_a(5)

    res, trace = trace_call(target)
    assert res == 11
    assert trace.total_calls >= 2

    # Verify helper_func_a called helper_func_b
    events = [
        e for e in trace.events if e.callee_name in ("helper_func_a", "helper_func_b")
    ]
    assert len(events) >= 1
    callee_names = {e.callee_name for e in events}
    assert "helper_func_b" in callee_names


@pytest.mark.unit
def test_dynamic_tracer_captures_exceptions():
    tracer = DynamicTracer()
    tracer.start()
    try:
        failing_func()
    except ValueError:
        pass
    finally:
        trace = tracer.stop()

    failing_events = [e for e in trace.events if e.callee_name == "failing_func"]
    assert len(failing_events) >= 1
    assert failing_events[0].has_exception is True


@pytest.mark.unit
def test_dynamic_tracer_respects_authorized_roots(tmp_path):
    # A root directory outside tmp_path should not be traced when restricted
    inside_dir = tmp_path / "inside"
    inside_dir.mkdir()
    inside_file = inside_dir / "worker.py"
    inside_file.write_text("def work(): return 42\n", encoding="utf-8")

    import importlib.util

    spec = importlib.util.spec_from_file_location("worker_mod", inside_file)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Authorized only for inside_dir
    tracer = DynamicTracer(authorized_roots=(inside_dir,))
    with tracer:
        val = mod.work()
    assert val == 42
    trace = tracer.stop()
    work_events = [e for e in trace.events if e.callee_name == "work"]
    assert len(work_events) >= 1


@pytest.mark.unit
def test_dynamic_tracer_captures_multithreading():
    import threading

    def worker():
        return helper_func_b(10)

    tracer = DynamicTracer()
    with tracer:
        t = threading.Thread(target=worker)
        t.start()
        t.join()
    trace = tracer.stop()

    worker_events = [e for e in trace.events if e.callee_name == "helper_func_b"]
    assert len(worker_events) >= 1
    assert len(trace.threads_observed) >= 1


@pytest.mark.unit
def test_dynamic_tracer_generator_does_not_mark_exception():
    def gen_func():
        yield 1
        yield 2

    tracer = DynamicTracer()
    with tracer:
        for _ in gen_func():
            pass
    trace = tracer.stop()

    gen_events = [e for e in trace.events if e.callee_name == "gen_func"]
    assert len(gen_events) >= 1
    # Generator suspension / normal return should not be marked as exception
    assert all(e.has_exception is False for e in gen_events)


@pytest.mark.integration
def test_merge_runtime_trace_recursion_and_self_loops(tmp_path):
    src = tmp_path / "recursion.py"
    src.write_text(
        """
def fact(n: int) -> int:
    if n <= 1:
        return 1
    return n * fact(n - 1)
""",
        encoding="utf-8",
    )

    policy = AnalysisPolicy()
    parsed = parse_project(tmp_path, policy)
    static_graph = build_graph(parsed)

    import importlib.util

    spec = importlib.util.spec_from_file_location("rec_mod", src)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _, trace = trace_call(lambda: mod.fact(4), authorized_roots=(tmp_path,))
    assert trace.total_calls >= 4

    unified_graph = merge_runtime_trace_into_graph(static_graph, trace)
    # Check self-loop edge for recursive call
    rec_edges = [
        e
        for e in unified_graph.edges
        if e.source_id == e.target_id and dict(e.attributes).get("recursive") == "true"
    ]
    assert len(rec_edges) == 1
    assert int(dict(rec_edges[0].attributes).get("runtime_calls", 0)) >= 3

    # Check node attributes populated
    fact_node = next(n for n in unified_graph.nodes if n.name == "fact")
    assert int(dict(fact_node.attributes).get("runtime_invocations", 0)) >= 4


@pytest.mark.integration
def test_merge_runtime_trace_method_disambiguation(tmp_path):
    src = tmp_path / "methods.py"
    src.write_text(
        """
class ServiceA:
    def process(self):
        return "A"

class ServiceB:
    def process(self):
        return "B"

def run_app():
    a = ServiceA()
    b = ServiceB()
    return a.process() + b.process()
""",
        encoding="utf-8",
    )

    policy = AnalysisPolicy()
    parsed = parse_project(tmp_path, policy)
    static_graph = build_graph(parsed)

    import importlib.util

    spec = importlib.util.spec_from_file_location("methods_mod", src)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _, trace = trace_call(mod.run_app, authorized_roots=(tmp_path,))
    unified_graph = merge_runtime_trace_into_graph(static_graph, trace)

    # Verify both ServiceA.process and ServiceB.process are targeted correctly
    node_names = {n.id: n.name for n in unified_graph.nodes}
    node_qual_names = {n.id: n.qualified_name for n in unified_graph.nodes}
    app_edges = [
        e
        for e in unified_graph.edges
        if node_names.get(e.source_id) == "run_app"
        and any(
            ev.origin is EvidenceOrigin.RUNTIME_TRACE
            for ev in unified_graph.evidence
            if ev.id in e.evidence_ids
        )
    ]
    target_names = {node_qual_names.get(e.target_id) for e in app_edges}
    assert "methods.ServiceA.process" in target_names
    assert "methods.ServiceB.process" in target_names


@pytest.mark.integration
def test_merge_runtime_trace_repeat_runs_refresh_metrics(tmp_path):
    src = tmp_path / "pipeline.py"
    src.write_text(
        """
def task_a():
    return 10

def task_b():
    return 20

def orchestrate():
    return task_a() + task_b()
""",
        encoding="utf-8",
    )

    policy = AnalysisPolicy()
    parsed = parse_project(tmp_path, policy)
    static_graph = build_graph(parsed)

    import importlib.util

    spec = importlib.util.spec_from_file_location("pipe_mod", src)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # First trace run
    _, trace_1 = trace_call(mod.orchestrate, authorized_roots=(tmp_path,))
    graph_1 = merge_runtime_trace_into_graph(static_graph, trace_1)

    node_names_1 = {n.id: n.name for n in graph_1.nodes}
    edge_a_1 = next(
        e
        for e in graph_1.edges
        if node_names_1.get(e.source_id) == "orchestrate"
        and node_names_1.get(e.target_id) == "task_a"
    )
    assert dict(edge_a_1.attributes)["runtime_calls"] == "1"

    # Second trace run
    _, trace_2 = trace_call(mod.orchestrate, authorized_roots=(tmp_path,))
    graph_2 = merge_runtime_trace_into_graph(graph_1, trace_2)

    node_names_2 = {n.id: n.name for n in graph_2.nodes}
    edge_a_2 = next(
        e
        for e in graph_2.edges
        if node_names_2.get(e.source_id) == "orchestrate"
        and node_names_2.get(e.target_id) == "task_a"
    )
    # Summed runtime calls without duplicate edges
    assert dict(edge_a_2.attributes)["runtime_calls"] == "2"

    # Node metrics are present and refreshed
    orch_node = next(n for n in graph_2.nodes if n.name == "orchestrate")
    assert "fan_out" in dict(orch_node.attributes)
    assert dict(orch_node.attributes)["runtime_invocations"] == "2"


@pytest.mark.integration
def test_trace_project_target(tmp_path):
    from codestruct.analysis.dynamic_tracer import trace_project_target

    target = tmp_path / "script.py"
    target.write_text(
        """
import sys

def compute(x):
    return x * 3

def main():
    val = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    return compute(val)

if __name__ == "__main__":
    res = main()
""",
        encoding="utf-8",
    )

    success, trace, error_msg = trace_project_target(
        project_root=tmp_path,
        target_file=target,
        entry_function="main",
        args=["7"],
        timeout_seconds=5.0,
    )

    assert success is True
    assert error_msg is None
    assert trace.total_calls >= 2
    callees = {e.callee_name for e in trace.events}
    assert "main" in callees or "compute" in callees


@pytest.mark.integration
def test_merge_runtime_trace_ambiguity_retention(tmp_path):
    from codestruct.analysis.dynamic_tracer import (
        RuntimeCallEvent,
        RuntimeTraceResult,
        merge_runtime_trace_into_graph,
    )
    from codestruct.graph.enums import RelationshipKind

    src = tmp_path / "ambig.py"
    src.write_text(
        """
def target():
    return 1

def runner():
    return 2
""",
        encoding="utf-8",
    )

    policy = AnalysisPolicy()
    parsed = parse_project(tmp_path, policy)
    static_graph = build_graph(parsed)

    # Construct synthetic ambiguous trace event where callee line doesn't match single definition
    ambig_trace = RuntimeTraceResult(
        events=(
            RuntimeCallEvent(
                caller_file=str(src),
                caller_name="runner",
                caller_line=6,
                callee_file=str(src),
                callee_name="target",
                callee_line=999,  # synthetic non-matching line to simulate ambiguous resolution
                call_count=5,
            ),
        ),
        total_calls=5,
        execution_time_seconds=0.01,
        overhead_seconds=0.0,
        threads_observed=(1,),
        exceptions_observed=0,
    )

    merged = merge_runtime_trace_into_graph(static_graph, ambig_trace)
    calls_edges = [e for e in merged.edges if e.kind is RelationshipKind.CALLS]
    assert len(calls_edges) >= 1
    ambig_edge = next(
        e for e in calls_edges if dict(e.attributes).get("runtime_calls") == "5"
    )
    assert ambig_edge is not None
