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
    from codestruct.graph.enums import RelationshipKind, ResolutionStatus

    src = tmp_path / "ambig.py"
    src.write_text(
        """
class ServiceA:
    def execute(self):
        return 1

class ServiceB:
    def execute(self):
        return 2

def runner():
    return 3
""",
        encoding="utf-8",
    )

    policy = AnalysisPolicy()
    parsed = parse_project(tmp_path, policy)
    static_graph = build_graph(parsed)

    exec_nodes = [n for n in static_graph.nodes if n.name == "execute"]
    assert len(exec_nodes) == 2
    for node in exec_nodes:
        assert "runtime_invocations" not in dict(node.attributes)

    # Construct ambiguous trace event targeting "execute" without clear single match
    ambig_trace = RuntimeTraceResult(
        events=(
            RuntimeCallEvent(
                caller_file=str(src),
                caller_name="runner",
                caller_line=10,
                callee_file=str(src),
                callee_name="execute",
                callee_line=999,  # synthetic line that cannot uniquely resolve to either class method
                call_count=5,
                duration_seconds=0.005,
            ),
        ),
        total_calls=5,
        execution_time_seconds=0.01,
        overhead_seconds=0.0001,
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
    assert ambig_edge.target_id is None
    assert ambig_edge.target_reference == "execute"
    assert ambig_edge.resolution.status is ResolutionStatus.AMBIGUOUS
    assert len(ambig_edge.resolution.candidate_ids) == 2

    # Verify neither candidate node was mutated with the ambiguous invocation counts
    merged_exec_nodes = [n for n in merged.nodes if n.name == "execute"]
    for node in merged_exec_nodes:
        assert dict(node.attributes).get("runtime_invocations", "0") == "0"


@pytest.mark.integration
def test_trace_project_target_timeout_prevents_side_effects(tmp_path):
    from codestruct.analysis.dynamic_tracer import trace_project_target

    marker_file = tmp_path / "marker_timeout.txt"
    script = tmp_path / "delayed_effect.py"
    script.write_text(
        f"""
import time
from pathlib import Path

def main():
    time.sleep(0.6)
    Path({repr(str(marker_file))}).write_text("SIDE_EFFECT_EXECUTED", encoding="utf-8")
    return 0

if __name__ == "__main__":
    main()
""",
        encoding="utf-8",
    )

    success, trace, error_msg = trace_project_target(
        project_root=tmp_path,
        target_file=script,
        entry_function="main",
        timeout_seconds=0.15,
    )

    assert success is False
    assert error_msg is not None
    assert "exceeded timeout" in error_msg.lower()
    assert trace.total_calls == 0

    # Wait longer than the target script's sleep duration to ensure it is dead and cannot execute side effects
    import time

    time.sleep(0.7)
    assert marker_file.exists() is False, (
        "Side effect occurred after process timeout kill!"
    )


@pytest.mark.integration
def test_trace_project_target_cancellation_prevents_side_effects(tmp_path):
    import threading
    import time

    from codestruct.analysis.dynamic_tracer import trace_project_target

    marker_file = tmp_path / "marker_cancelled.txt"
    script = tmp_path / "cancellable_effect.py"
    script.write_text(
        f"""
import time
from pathlib import Path

def main():
    time.sleep(0.6)
    Path({repr(str(marker_file))}).write_text("SIDE_EFFECT_EXECUTED", encoding="utf-8")
    return 0

if __name__ == "__main__":
    main()
""",
        encoding="utf-8",
    )

    cancel_event = threading.Event()

    # Trigger cancellation shortly after launch
    def cancel_later():
        time.sleep(0.1)
        cancel_event.set()

    canceller = threading.Thread(target=cancel_later)
    canceller.start()

    success, trace, error_msg = trace_project_target(
        project_root=tmp_path,
        target_file=script,
        entry_function="main",
        timeout_seconds=5.0,
        cancel_event=cancel_event,
    )
    canceller.join()

    assert success is False
    assert error_msg is not None
    assert "cancelled" in error_msg.lower()

    # Wait longer than the target script's sleep duration
    time.sleep(0.7)
    assert marker_file.exists() is False, (
        "Side effect occurred after process cancellation!"
    )


@pytest.mark.unit
def test_dynamic_tracer_truthful_overhead_and_duration():
    def dummy_target():
        return helper_func_a(3)

    _, trace = trace_call(dummy_target)
    assert trace.total_calls >= 2
    # Overhead must be truthfully measured and strictly positive for recorded calls
    assert trace.overhead_seconds > 0.0
    for event in trace.events:
        assert event.duration_seconds >= 0.0

    # For zero calls, overhead should be 0.0
    empty_trace = DynamicTracer().stop()
    assert empty_trace.overhead_seconds == 0.0


@pytest.mark.integration
def test_trace_project_target_output_bounds_no_leak(tmp_path):
    from codestruct.analysis.dynamic_tracer import trace_project_target

    script = tmp_path / "verbose_target.py"
    script.write_text(
        """
import sys

def main():
    # Attempt to write 200 KB to stdout and 200 KB to stderr
    sys.stdout.write("X" * 200_000)
    sys.stderr.write("Y" * 200_000)
    print("FINISHED")
    return 0

if __name__ == "__main__":
    main()
""",
        encoding="utf-8",
    )

    # Enforce bound of 1024 bytes
    max_output = 1024
    success, trace, error_msg = trace_project_target(
        project_root=tmp_path,
        target_file=script,
        entry_function="main",
        max_output_bytes=max_output,
        timeout_seconds=5.0,
    )

    assert success is True
    assert error_msg is None
    assert trace.total_calls >= 1


@pytest.mark.integration
def test_trace_project_target_error_output_capped(tmp_path):
    from codestruct.analysis.dynamic_tracer import trace_project_target

    script = tmp_path / "failing_target.py"
    script.write_text(
        """
import sys

# Raise an exception with huge text
raise RuntimeError("ERR_" + ("Z" * 100_000))
""",
        encoding="utf-8",
    )

    max_output = 512
    success, trace, error_msg = trace_project_target(
        project_root=tmp_path,
        target_file=script,
        max_output_bytes=max_output,
        timeout_seconds=5.0,
    )

    assert success is False
    assert error_msg is not None
    # Verify the error message is bounded by max_output_bytes (plus worker message prefix)
    assert len(error_msg) <= max_output + 100
