"""Tests for type stub (.pyi) discovery, AST parsing, and symbol resolution."""

from __future__ import annotations

import tempfile
from pathlib import Path

from codestruct.analysis.policy import AnalysisPolicy
from codestruct.analysis.python_parser import PythonAstParser
from codestruct.analysis.scanner import derive_module_name, scan_project
from codestruct.graph.enums import NodeKind
from codestruct.graph.model import GraphNode, SourceReference, SourceSpan
from codestruct.graph.resolver import SymbolIndex


def test_derive_module_name_pyi() -> None:
    assert derive_module_name("typing_extensions.pyi") == "typing_extensions"
    assert derive_module_name("pkg/service.pyi") == "pkg.service"
    assert derive_module_name("pkg/__init__.pyi") == "pkg"


def test_scan_project_with_type_stubs() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "module_a.py").write_text("def run(): pass\n", encoding="utf-8")
        (root / "module_b.pyi").write_text(
            "def typed_fn(x: int) -> str: ...\n", encoding="utf-8"
        )
        pkg_dir = root / "stubbed_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.pyi").write_text("__all__ = ['api']\n", encoding="utf-8")

        policy = AnalysisPolicy(authorized_roots=(root,))
        result = scan_project(root, policy)

        file_paths = {sf.relative_path for sf in result.source_files}
        assert "module_a.py" in file_paths
        assert "module_b.pyi" in file_paths
        assert "stubbed_pkg/__init__.pyi" in file_paths

        # Verify package recognition
        stub_init = next(
            sf
            for sf in result.source_files
            if sf.relative_path == "stubbed_pkg/__init__.pyi"
        )
        assert stub_init.is_package is True
        assert stub_init.module_name == "stubbed_pkg"


def test_parse_type_stub_ast() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        stub_file = root / "stubs.pyi"
        stub_content = (
            "from typing import Protocol\n\n"
            "class Greeter(Protocol):\n"
            "    def greet(self, name: str) -> str: ...\n"
        )
        stub_file.write_text(stub_content, encoding="utf-8")

        policy = AnalysisPolicy(authorized_roots=(root,))
        scan_res = scan_project(root, policy)
        sf = scan_res.source_files[0]

        parser = PythonAstParser()
        parse_res = parser.parse(root, sf, policy)

        assert parse_res.parsed is True
        class_names = [c.name for c in parse_res.classes]
        assert "Greeter" in class_names
        function_names = [f.name for f in parse_res.functions]
        assert "greet" in function_names


def test_lookup_index_prioritizes_implementation_over_stub() -> None:
    py_node = GraphNode(
        id="mod-py",
        kind=NodeKind.MODULE,
        name="service",
        qualified_name="pkg.service",
        location=SourceReference(
            source_unit_id="src-1", path="pkg/service.py", span=SourceSpan(1, 0, 1, 0)
        ),
    )
    pyi_node = GraphNode(
        id="mod-pyi",
        kind=NodeKind.MODULE,
        name="service",
        qualified_name="pkg.service",
        location=SourceReference(
            source_unit_id="src-2", path="pkg/service.pyi", span=SourceSpan(1, 0, 1, 0)
        ),
    )

    index = SymbolIndex((pyi_node, py_node))
    modules = index.modules("pkg.service")
    assert len(modules) == 2
    # The .py implementation node must be first
    assert modules[0].id == "mod-py"
    assert modules[1].id == "mod-pyi"


def test_stub_only_module_build_graph() -> None:
    """CS-018: A stub-only module (.pyi without .py) is parsed and represented as a valid module in the graph."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "types_extra.pyi").write_text(
            "class ExtraPayload:\n"
            "    data: dict[str, str]\n"
            "    def validate(self) -> bool: ...\n",
            encoding="utf-8",
        )
        (root / "main.py").write_text(
            "import types_extra\ndef check():\n    p = types_extra.ExtraPayload()\n",
            encoding="utf-8",
        )

        policy = AnalysisPolicy(authorized_roots=(root,))
        scan = scan_project(root, policy)
        parser = PythonAstParser()
        files = [parser.parse(root, sf, policy) for sf in scan.source_files]
        diagnostics = list(scan.diagnostics)
        for f in files:
            diagnostics.extend(f.diagnostics)
        from codestruct.analysis.models import ProjectParseResult
        from codestruct.graph.builder import build_graph

        parsed = ProjectParseResult(
            scan=scan, files=tuple(files), diagnostics=tuple(diagnostics)
        )
        graph = build_graph(parsed)

        # ExtraPayload class should exist from the .pyi file
        stub_class = next(n for n in graph.nodes if n.name == "ExtraPayload")
        assert stub_class.location is not None
        assert stub_class.location.path == "types_extra.pyi"


def test_external_stub_boundary_resolution() -> None:
    """CS-018: External stdlib/third-party imports are marked with external boundaries without importing or executing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "worker.py").write_text(
            "import os\nimport sys\ndef get_info():\n    return os.name, sys.version\n",
            encoding="utf-8",
        )

        policy = AnalysisPolicy(authorized_roots=(root,))
        scan = scan_project(root, policy)
        parser = PythonAstParser()
        files = [parser.parse(root, sf, policy) for sf in scan.source_files]
        diagnostics = list(scan.diagnostics)
        for f in files:
            diagnostics.extend(f.diagnostics)
        from codestruct.analysis.models import ProjectParseResult
        from codestruct.graph.builder import build_graph
        from codestruct.graph.enums import RelationshipKind, ResolutionStatus

        parsed = ProjectParseResult(
            scan=scan, files=tuple(files), diagnostics=tuple(diagnostics)
        )
        graph = build_graph(parsed)

        # Verify os and sys are resolved to external modules
        import_edges = [
            e
            for e in graph.edges
            if e.kind is RelationshipKind.IMPORTS
            and e.resolution.status is ResolutionStatus.RESOLVED
        ]
        assert len(import_edges) >= 2
