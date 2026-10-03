"""Focused unit and integration tests for static resolution correctness (CS-018, CS-019)."""

from pathlib import Path

from codestruct.analysis import AnalysisPolicy, PythonAstParser, scan_project
from codestruct.analysis.models import ProjectParseResult
from codestruct.graph.builder import build_graph
from codestruct.graph.enums import Confidence, RelationshipKind, ResolutionStatus


def parse_and_build(root_path: Path, compute_metrics: bool = False):
    policy = AnalysisPolicy(authorized_roots=(root_path,))
    scan = scan_project(root_path, policy)
    parser = PythonAstParser()
    files = [parser.parse(root_path, sf, policy) for sf in scan.source_files]
    diagnostics = list(scan.diagnostics)
    for f in files:
        diagnostics.extend(f.diagnostics)
    parsed = ProjectParseResult(
        scan=scan,
        files=tuple(files),
        diagnostics=tuple(diagnostics),
    )
    return build_graph(parsed, compute_metrics=compute_metrics)


def test_lexical_scope_resolution(tmp_path: Path):
    """CS-018: Enclosing lexical scope search for nested and local functions."""
    code = (
        "def outer():\n"
        "    def helper():\n"
        "        pass\n"
        "    helper()\n"
        "def caller():\n"
        "    outer()\n"
    )
    (tmp_path / "scopes.py").write_text(code, encoding="utf-8")
    graph = parse_and_build(tmp_path)

    # Verify calls edge from outer to helper is resolved
    call_edges = [
        e
        for e in graph.edges
        if e.kind is RelationshipKind.CALLS
        and e.resolution.status is ResolutionStatus.RESOLVED
    ]
    assert len(call_edges) >= 2
    edge_map = {(e.source_id, e.target_id): e for e in call_edges}

    outer_node = next(n for n in graph.nodes if n.name == "outer")
    helper_node = next(n for n in graph.nodes if n.name == "helper")
    caller_node = next(n for n in graph.nodes if n.name == "caller")

    assert (outer_node.id, helper_node.id) in edge_map
    assert (caller_node.id, outer_node.id) in edge_map


def test_inheritance_and_base_method_resolution(tmp_path: Path):
    """CS-018/CS-019: Resolve inherited methods via self.method() and multi-dot class inheritance."""
    code_a = (
        "class Base:\n"
        "    def base_method(self):\n"
        "        pass\n"
        "class Middle(Base):\n"
        "    def middle_method(self):\n"
        "        self.base_method()\n"
        "class Derived(Middle):\n"
        "    def derived_method(self):\n"
        "        self.middle_method()\n"
        "        self.base_method()\n"
    )
    (tmp_path / "hierarchy.py").write_text(code_a, encoding="utf-8")
    graph = parse_and_build(tmp_path)

    # Check inheritance edges
    inherits_edges = [e for e in graph.edges if e.kind is RelationshipKind.INHERITS]
    assert len(inherits_edges) == 2
    for e in inherits_edges:
        assert e.resolution.status is ResolutionStatus.RESOLVED

    # Check call edges from derived_method and middle_method
    base_m = next(n for n in graph.nodes if n.name == "base_method")
    mid_m = next(n for n in graph.nodes if n.name == "middle_method")
    der_m = next(n for n in graph.nodes if n.name == "derived_method")

    call_targets = {
        (e.source_id, e.target_id)
        for e in graph.edges
        if e.kind is RelationshipKind.CALLS
        and e.resolution.status is ResolutionStatus.RESOLVED
    }
    assert (mid_m.id, base_m.id) in call_targets
    assert (der_m.id, mid_m.id) in call_targets
    assert (der_m.id, base_m.id) in call_targets


def test_multi_dot_attribute_and_cross_module_inheritance(tmp_path: Path):
    """CS-018: Multi-dot module import and inheritance (e.g. pkg.sub.Base)."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "base_mod.py").write_text(
        "class Component:\n    def render(self):\n        pass\n",
        encoding="utf-8",
    )
    (pkg / "app.py").write_text(
        "import pkg.base_mod\n"
        "class MyComponent(pkg.base_mod.Component):\n"
        "    def run(self):\n"
        "        self.render()\n",
        encoding="utf-8",
    )

    graph = parse_and_build(tmp_path)
    inherits_edges = [
        e
        for e in graph.edges
        if e.kind is RelationshipKind.INHERITS
        and e.resolution.status is ResolutionStatus.RESOLVED
    ]
    assert len(inherits_edges) == 1
    my_comp = next(n for n in graph.nodes if n.name == "MyComponent")
    base_comp = next(n for n in graph.nodes if n.name == "Component")
    assert inherits_edges[0].source_id == my_comp.id
    assert inherits_edges[0].target_id == base_comp.id

    run_m = next(n for n in graph.nodes if n.name == "run")
    render_m = next(n for n in graph.nodes if n.name == "render")
    call_targets = {
        (e.source_id, e.target_id)
        for e in graph.edges
        if e.kind is RelationshipKind.CALLS
        and e.resolution.status is ResolutionStatus.RESOLVED
    }
    assert (run_m.id, render_m.id) in call_targets


def test_type_stub_shadowing_and_fallback(tmp_path: Path):
    """CS-019: .pyi stub files are resolved alongside .py source files without executing code."""
    (tmp_path / "service.py").write_text(
        "def perform_work():\n    return 42\n",
        encoding="utf-8",
    )
    (tmp_path / "service.pyi").write_text(
        "def perform_work() -> int: ...\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "import service\ndef entry():\n    service.perform_work()\n",
        encoding="utf-8",
    )

    graph = parse_and_build(tmp_path)
    entry_node = next(n for n in graph.nodes if n.name == "entry")
    py_work_node = next(
        n
        for n in graph.nodes
        if n.name == "perform_work" and n.location and n.location.path == "service.py"
    )

    calls = [
        e
        for e in graph.edges
        if e.kind is RelationshipKind.CALLS
        and e.source_id == entry_node.id
        and e.resolution.status is ResolutionStatus.RESOLVED
    ]
    assert len(calls) >= 1
    assert calls[0].target_id == py_work_node.id


def test_import_aliases_and_aliased_calls(tmp_path: Path):
    """CS-019: Resolve aliased module imports (import math as m) and from imports (from pkg import fn as my_fn)."""
    (tmp_path / "math_lib.py").write_text(
        "def compute_sqrt(x):\n    return x ** 0.5\n", encoding="utf-8"
    )
    (tmp_path / "main.py").write_text(
        "import math_lib as ml\n"
        "from math_lib import compute_sqrt as sqrt_alias\n"
        "def run():\n"
        "    ml.compute_sqrt(16)\n"
        "    sqrt_alias(25)\n",
        encoding="utf-8",
    )
    graph = parse_and_build(tmp_path)
    run_node = next(n for n in graph.nodes if n.name == "run")
    sqrt_node = next(n for n in graph.nodes if n.name == "compute_sqrt")

    resolved_calls = [
        e
        for e in graph.edges
        if e.kind is RelationshipKind.CALLS
        and e.source_id == run_node.id
        and e.resolution.status is ResolutionStatus.RESOLVED
    ]
    assert len(resolved_calls) >= 1
    target_ids = {e.target_id for e in resolved_calls}
    assert sqrt_node.id in target_ids


def test_class_constructor_and_instantiation(tmp_path: Path):
    """CS-019: Resolve class instantiation (e.g. srv = Service()) to class and constructor."""
    code = (
        "class Service:\n"
        "    def __init__(self):\n"
        "        pass\n"
        "    def serve(self):\n"
        "        pass\n"
        "def start():\n"
        "    s = Service()\n"
    )
    (tmp_path / "service_app.py").write_text(code, encoding="utf-8")
    graph = parse_and_build(tmp_path)

    start_node = next(n for n in graph.nodes if n.name == "start")
    service_class = next(n for n in graph.nodes if n.name == "Service")

    # Start should have a call/construct resolution to Service
    calls_and_constructs = [
        e
        for e in graph.edges
        if e.source_id == start_node.id
        and e.kind in (RelationshipKind.CALLS, RelationshipKind.CONSTRUCTS)
        and e.resolution.status is ResolutionStatus.RESOLVED
    ]
    assert len(calls_and_constructs) >= 1
    target_ids = {e.target_id for e in calls_and_constructs}
    assert service_class.id in target_ids


def test_lexical_shadowing_and_duplicate_names(tmp_path: Path):
    """CS-019: Innermost lexical scope takes precedence when duplicate names exist in nested scopes."""
    code = (
        "def shadow_fn():\n"
        "    return 'outer'\n\n"
        "def outer_scope():\n"
        "    def shadow_fn():\n"
        "        return 'inner'\n"
        "    shadow_fn()\n"
    )
    (tmp_path / "shadow.py").write_text(code, encoding="utf-8")
    graph = parse_and_build(tmp_path)

    outer_scope_node = next(n for n in graph.nodes if n.name == "outer_scope")
    inner_shadow = next(
        n
        for n in graph.nodes
        if n.name == "shadow_fn" and n.parent_id == outer_scope_node.id
    )

    resolved_calls = [
        e
        for e in graph.edges
        if e.kind is RelationshipKind.CALLS
        and e.source_id == outer_scope_node.id
        and e.resolution.status is ResolutionStatus.RESOLVED
    ]
    assert len(resolved_calls) >= 1
    assert resolved_calls[0].target_id == inner_shadow.id


def test_type_annotations_do_not_produce_false_calls(tmp_path: Path):
    """CS-019: Type annotations in signatures and variable declarations must not be treated as runtime calls."""
    code = (
        "class Request:\n    pass\n"
        "class Response:\n    pass\n"
        "def handle(req: Request) -> Response:\n"
        "    total: int = 100\n"
        "    return Response()\n"
    )
    (tmp_path / "types_test.py").write_text(code, encoding="utf-8")
    graph = parse_and_build(tmp_path)

    handle_node = next(n for n in graph.nodes if n.name == "handle")
    req_class = next(n for n in graph.nodes if n.name == "Request")

    # handle() calls Response() constructor, but should NOT have a CALLS relationship to Request
    req_calls = [
        e
        for e in graph.edges
        if e.kind is RelationshipKind.CALLS
        and e.source_id == handle_node.id
        and e.target_id == req_class.id
    ]
    assert len(req_calls) == 0, "Type annotation parameter must not create a CALLS edge"


def test_unsupported_dynamic_expressions_preserve_unresolved_status(
    tmp_path: Path,
):
    """CS-019: Dynamic and unsupported expressions preserve UNRESOLVED / SYNTACTIC_ONLY status without guessing."""
    code = (
        "import importlib\n"
        "def dynamic_loader(mod_name):\n"
        "    mod = importlib.import_module(mod_name)\n"
        "    getattr(mod, 'target_fn')()\n"
    )
    (tmp_path / "dynamic_app.py").write_text(code, encoding="utf-8")
    graph = parse_and_build(tmp_path)

    loader_node = next(n for n in graph.nodes if n.name == "dynamic_loader")

    # Edges from dynamic_loader must preserve non-resolved status
    unresolved_or_syntactic = [
        e
        for e in graph.edges
        if e.source_id == loader_node.id
        and e.resolution.status
        in (ResolutionStatus.UNRESOLVED, ResolutionStatus.SYNTACTIC_ONLY)
    ]
    assert len(unresolved_or_syntactic) >= 1
    for edge in unresolved_or_syntactic:
        assert edge.resolution.status is not ResolutionStatus.RESOLVED
        assert edge.resolution.confidence in (
            Confidence.UNKNOWN,
            Confidence.LOW,
        )


def test_evidence_and_location_fidelity(tmp_path: Path):
    """CS-019: Evidence records and source locations match exact AST line/column spans."""
    code = "def worker():\n    pass\n\ndef manager():\n    worker()\n"
    (tmp_path / "evidence_fidelity.py").write_text(code, encoding="utf-8")
    graph = parse_and_build(tmp_path)

    manager_node = next(n for n in graph.nodes if n.name == "manager")
    worker_node = next(n for n in graph.nodes if n.name == "worker")

    call_edge = next(
        e
        for e in graph.edges
        if e.kind is RelationshipKind.CALLS
        and e.source_id == manager_node.id
        and e.target_id == worker_node.id
    )

    # Edge has evidence
    assert len(call_edge.evidence_ids) >= 1
    ev_id = call_edge.evidence_ids[0]
    ev_rec = next(ev for ev in graph.evidence if ev.id == ev_id)

    assert ev_rec.location is not None
    assert ev_rec.location.path == "evidence_fidelity.py"
    # manager calls worker at line 5
    assert ev_rec.location.span.start_line == 5
