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


@pytest.mark.integration
def test_merge_runtime_trace_into_graph(tmp_path):
    src = tmp_path / "app.py"
    src.write_text(
        """
def step_one():
    return 1

def step_two():
    return 2

def pipeline():
    return step_one() + step_two()
""",
        encoding="utf-8",
    )

    policy = AnalysisPolicy()
    parsed = parse_project(tmp_path, policy)
    static_graph = build_graph(parsed)

    # Execute and trace the pipeline
    import importlib.util

    spec = importlib.util.spec_from_file_location("app_mod", src)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _, trace = trace_call(mod.pipeline, authorized_roots=(tmp_path,))

    unified_graph = merge_runtime_trace_into_graph(static_graph, trace)
    assert unified_graph.schema_version == "1.0.0"

    # Runtime evidence must be present in the unified graph
    runtime_evidences = [
        ev for ev in unified_graph.evidence if ev.origin is EvidenceOrigin.RUNTIME_TRACE
    ]
    assert len(runtime_evidences) >= 1

    # Check edges with runtime evidence
    runtime_edges = [
        e
        for e in unified_graph.edges
        if any(
            ev.origin is EvidenceOrigin.RUNTIME_TRACE
            for ev in unified_graph.evidence
            if ev.id in e.evidence_ids
        )
    ]
    assert len(runtime_edges) >= 1
    assert any(dict(e.attributes).get("runtime_calls") for e in runtime_edges)
