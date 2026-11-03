"""Tests for CodeStruct Backend API Layer (Phase 2).

Validates the endpoints specified in Section 4.3 using FastAPI's TestClient:
- POST /api/analyze
- GET /api/symbol/{node_id}
- GET /api/source
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure codestruct package root is in sys.path
TESTS_DIR = Path(__file__).resolve().parent
CODESTRUCT_DIR = TESTS_DIR.parent
if str(CODESTRUCT_DIR) not in sys.path:
    sys.path.insert(0, str(CODESTRUCT_DIR))

from backend.main import app
from backend.schemas import ChatResponse, Graph, SourceResponse, SymbolDetail

SAMPLE_PROJECT_DIR = CODESTRUCT_DIR / "sample_project"


@pytest.fixture(scope="module")
def client():
    """Create a TestClient instance for the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


def test_analyze_endpoint_sample_project(client):
    """POST /api/analyze returns valid Graph JSON matching Section 4.1 with node_count: 16."""
    response = client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})
    assert response.status_code == 200, f"Analysis failed: {response.text}"

    data = response.json()

    # Validate against Pydantic schema
    graph = Graph(**data)
    assert graph.summary.node_count == 16, f"Expected node_count 16, got {graph.summary.node_count}"
    assert graph.summary.module_count == 1
    assert graph.summary.class_count == 4
    assert graph.summary.function_count == 2
    assert graph.summary.method_count == 9

    # Check edges
    edge_types = {e.type for e in graph.edges}
    assert "inherits" in edge_types
    assert "defines" in edge_types
    assert "constructs" in edge_types
    assert "calls" in edge_types


def test_symbol_endpoint_dog_inherits(client):
    """GET /api/symbol/sample_project.Dog includes inherits edge to sample_project.Animal."""
    # Ensure sample project is analyzed
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    response = client.get("/api/symbol/sample_project.Dog")
    assert response.status_code == 200, f"Symbol lookup failed: {response.text}"

    data = response.json()

    # Validate against Pydantic schema
    symbol = SymbolDetail(**data)
    assert symbol.id == "sample_project.Dog"
    assert symbol.name == "Dog"
    assert symbol.kind == "class"

    # Outgoing must include inherits to Animal
    inherits_edges = [
        edge for edge in symbol.outgoing
        if edge.type == "inherits" and edge.id == "sample_project.Animal"
    ]
    assert len(inherits_edges) == 1, (
        f"Expected outgoing inherits edge to sample_project.Animal, found: {symbol.outgoing}"
    )

    # Fan out must be at least 1 (inherits Animal + defines fetch + defines speak)
    assert symbol.fan_out >= 1
    assert symbol.fan_in >= 1  # defines from sample_project


def test_symbol_endpoint_animal_details(client):
    """GET /api/symbol/sample_project.Animal returns 3 methods under outgoing and correct fan counts."""
    # Ensure sample project is analyzed
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    response = client.get("/api/symbol/sample_project.Animal")
    assert response.status_code == 200, f"Symbol lookup failed: {response.text}"

    data = response.json()
    symbol = SymbolDetail(**data)
    assert symbol.id == "sample_project.Animal"
    assert symbol.name == "Animal"
    assert symbol.kind == "class"
    assert symbol.fan_in == 3  # defines from sample_project, inherits from Dog, inherits from Cat
    assert symbol.fan_out == 3  # defines __init__, speak, describe

    outgoing_names = {e.name for e in symbol.outgoing}
    assert {"__init__", "speak", "describe"}.issubset(outgoing_names)
    for edge in symbol.outgoing:
        if edge.name in {"__init__", "speak", "describe"}:
            assert edge.type == "defines"

    assert symbol.docstring == "Base class for all zoo animals."


def test_symbol_endpoint_main_calls_build_zoo(client):
    """GET /api/symbol/sample_project.main includes calls edge to build_zoo."""
    # Ensure sample project is analyzed
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    response = client.get("/api/symbol/sample_project.main")
    assert response.status_code == 200, f"Symbol lookup failed: {response.text}"

    data = response.json()
    symbol = SymbolDetail(**data)
    assert symbol.id == "sample_project.main"
    assert symbol.name == "main"
    assert symbol.kind == "function"
    assert symbol.fan_in == 1  # defines from sample_project
    assert symbol.fan_out == 1  # calls build_zoo

    calls_edges = [
        edge for edge in symbol.outgoing
        if edge.type == "calls" and edge.id == "sample_project.build_zoo"
    ]
    assert len(calls_edges) == 1
    assert symbol.docstring == "Entry point."


def test_symbol_endpoint_not_found(client):
    """GET /api/symbol/{node_id} returns 404 for an unknown symbol."""
    response = client.get("/api/symbol/non_existent.symbol.id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_source_endpoint_valid_range(client):
    """GET /api/source returns highlighted HTML for a valid file and line range."""
    # Ensure sample project is analyzed
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    response = client.get("/api/source?file_path=sample_project.py&start=4&end=16")
    assert response.status_code == 200, f"Source retrieval failed: {response.text}"

    data = response.json()

    # Validate against Pydantic schema
    source = SourceResponse(**data)
    assert len(source.html.strip()) > 0
    assert source.start == 4
    assert source.end == 16
    assert "Animal" in source.html
    assert "highlight" in source.html


def test_source_endpoint_invalid_file_4xx(client):
    """GET /api/source returns clean 404 (not 500) for an invalid file path."""
    response = client.get("/api/source?file_path=does_not_exist_anywhere.py&start=1&end=10")
    assert response.status_code == 404
    assert "file not found" in response.json()["detail"].lower()


def test_source_endpoint_invalid_line_range_4xx(client):
    """GET /api/source returns clean 400 for an inverted line range."""
    response = client.get("/api/source?file_path=sample_project.py&start=30&end=10")
    assert response.status_code == 400
    assert "invalid line range" in response.json()["detail"].lower()


def test_source_endpoint_animal_speak_slice(client):
    """GET /api/source returns slice with speak method and correct line IDs."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})
    response = client.get("/api/source?file_path=sample_project.py&start=6&end=17")
    assert response.status_code == 200
    data = response.json()
    source = SourceResponse(**data)
    assert source.start == 6
    assert source.end == 17
    assert 'id="line-11"' in source.html
    assert "speak" in source.html
    assert 'id="line-12"' in source.html


def test_source_endpoint_dog_fetch_slice(client):
    """GET /api/source returns slice with fetch method and correct line IDs."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})
    response = client.get("/api/source?file_path=sample_project.py&start=16&end=27")
    assert response.status_code == 200
    data = response.json()
    source = SourceResponse(**data)
    assert source.start == 16
    assert source.end == 27
    assert 'id="line-21"' in source.html
    assert "fetch" in source.html
    assert 'id="line-22"' in source.html


def test_source_endpoint_build_zoo_slice(client):
    """GET /api/source returns slice with build_zoo function and correct line IDs."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})
    response = client.get("/api/source?file_path=sample_project.py&start=43&end=58")
    assert response.status_code == 200
    data = response.json()
    source = SourceResponse(**data)
    assert source.start == 43
    assert source.end == 58
    assert 'id="line-48"' in source.html
    assert "build_zoo" in source.html
    assert 'id="line-53"' in source.html


def test_chat_endpoint_with_symbol_context(client):
    """POST /api/qwen/chat returns context-aware reply mentioning the selected symbol."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})
    response = client.post(
        "/api/qwen/chat",
        json={"message": "explain this", "context_symbol_id": "sample_project.Animal"},
    )
    assert response.status_code == 200
    data = response.json()
    chat_resp = ChatResponse(**data)
    assert len(chat_resp.reply.strip()) > 0
    # Must reference Animal in the reply
    assert "Animal" in chat_resp.reply


def test_chat_endpoint_ollama_down_graceful_error(client, monkeypatch):
    """POST /api/qwen/chat handles unreachable Ollama gracefully without crashing or 500."""
    import backend.qwen_client as qc
    # Point to an unreachable port to simulate Ollama down
    monkeypatch.setattr(qc, "OLLAMA_CHAT_URL", "http://127.0.0.1:59999/api/chat")

    response = client.post(
        "/api/qwen/chat",
        json={"message": "explain this", "context_symbol_id": "sample_project.Animal"},
    )
    assert response.status_code == 200
    data = response.json()
    chat_resp = ChatResponse(**data)
    assert chat_resp.reply.startswith("[Error]")
    assert "unreachable" in chat_resp.reply.lower() or "not running" in chat_resp.reply.lower()


def test_chat_endpoint_recovery_after_down(client, monkeypatch):
    """POST /api/qwen/chat recovers seamlessly once Ollama is back up, with no app restart."""
    import backend.qwen_client as qc
    # First: simulate down
    monkeypatch.setattr(qc, "OLLAMA_CHAT_URL", "http://127.0.0.1:59999/api/chat")
    res_down = client.post("/api/qwen/chat", json={"message": "test", "context_symbol_id": None})
    assert res_down.status_code == 200
    assert res_down.json()["reply"].startswith("[Error]")

    # Second: simulate recovery (restore default URL)
    monkeypatch.undo()
    res_up = client.post(
        "/api/qwen/chat",
        json={"message": "explain this", "context_symbol_id": "sample_project.Animal"},
    )
    assert res_up.status_code == 200
    reply = res_up.json()["reply"]
    assert not reply.startswith("[Error]")
    assert "Animal" in reply


def test_analyze_endpoint_empty_path_400(client):
    """POST /api/analyze returns clean 400 for an empty or whitespace path."""
    response = client.post("/api/analyze", json={"project_path": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"].lower()


def test_analyze_endpoint_invalid_path_400(client):
    """POST /api/analyze returns clean 400 for a non-existent project path."""
    response = client.post("/api/analyze", json={"project_path": "this/path/absolutely/does/not/exist"})
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"].lower()


def test_analyze_endpoint_custom_path(client, tmp_path):
    """POST /api/analyze accepts arbitrary custom project paths and updates symbol/source state."""
    # Create custom project directory with 2 modules
    proj_dir = tmp_path / "custom_service"
    proj_dir.mkdir()

    calc_file = proj_dir / "calculator.py"
    calc_file.write_text(
        '"""Calculator module."""\n\n'
        "class Calculator:\n"
        '    """Performs arithmetic."""\n'
        "    def add(self, a, b):\n"
        "        return a + b\n\n"
        "def compute_total(calc, x, y):\n"
        "    return calc.add(x, y)\n",
        encoding="utf-8",
    )

    runner_file = proj_dir / "runner.py"
    runner_file.write_text(
        '"""Runner module."""\n\n'
        "from calculator import Calculator, compute_total\n\n"
        "def run():\n"
        "    calc = Calculator()\n"
        "    return compute_total(calc, 10, 20)\n",
        encoding="utf-8",
    )

    # 1. Analyze custom project
    response = client.post("/api/analyze", json={"project_path": str(proj_dir)})
    assert response.status_code == 200, f"Analysis failed: {response.text}"
    data = response.json()
    graph = Graph(**data)

    # Check node summary
    assert graph.summary.module_count == 2
    assert graph.summary.class_count == 1
    assert graph.summary.method_count == 1
    assert graph.summary.function_count == 2
    assert graph.summary.node_count == 6

    # 2. Check /api/symbol/{id} against the new project's data WITHOUT re-analyzing
    sym_res = client.get("/api/symbol/calculator.Calculator")
    assert sym_res.status_code == 200
    sym_data = SymbolDetail(**sym_res.json())
    assert sym_data.name == "Calculator"
    assert sym_data.kind == "class"
    assert sym_data.docstring == "Performs arithmetic."
    assert any(edge.name == "add" and edge.type == "defines" for edge in sym_data.outgoing)

    # 3. Check /api/source works against the new project's files WITHOUT re-analyzing
    src_res = client.get("/api/source", params={"file_path": "calculator.py", "start": 3, "end": 6})
    assert src_res.status_code == 200
    src_data = SourceResponse(**src_res.json())
    assert src_data.start == 3
    assert src_data.end == 6
    assert "Calculator" in src_data.html
    assert "line-3" in src_data.html


def test_analyze_endpoint_root_project_file(client, tmp_path):
    """POST /api/analyze accepts a single .py file as a project and serves symbol & source."""
    single_file = tmp_path / "standalone.py"
    single_file.write_text(
        '"""Standalone single-file module."""\n\n'
        "def standalone_func(val):\n"
        '    """Returns negated value."""\n'
        "    return -val\n",
        encoding="utf-8",
    )

    response = client.post("/api/analyze", json={"project_path": str(single_file)})
    assert response.status_code == 200
    data = response.json()
    graph = Graph(**data)
    assert graph.summary.module_count == 1
    assert graph.summary.function_count == 1
    assert graph.summary.node_count == 2

    # Symbol lookup
    sym_res = client.get("/api/symbol/standalone.standalone_func")
    assert sym_res.status_code == 200
    sym = SymbolDetail(**sym_res.json())
    assert sym.name == "standalone_func"
    assert sym.docstring == "Returns negated value."

    # Source lookup
    src_res = client.get("/api/source", params={"file_path": "standalone.py", "start": 3, "end": 5})
    assert src_res.status_code == 200
    src_data = SourceResponse(**src_res.json())
    assert "standalone_func" in src_data.html
    assert "line-3" in src_data.html


def test_analyze_endpoint_empty_directory_warning(client, tmp_path):
    """POST /api/analyze on directory with no .py files returns 200 with 0 nodes and warning."""
    empty_dir = tmp_path / "empty_project"
    empty_dir.mkdir()

    response = client.post("/api/analyze", json={"project_path": str(empty_dir)})
    assert response.status_code == 200
    data = response.json()
    graph = Graph(**data)
    assert graph.summary.node_count == 0
    assert len(graph.errors) == 1
    assert "No .py files found" in graph.errors[0].message


def test_analyze_endpoint_non_python_file_400(client, tmp_path):
    """POST /api/analyze on non-python file returns HTTP 400."""
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("Hello world", encoding="utf-8")

    response = client.post("/api/analyze", json={"project_path": str(txt_file)})
    assert response.status_code == 400
    assert "must be a directory or a .py file" in response.json()["detail"].lower() or "not a directory" in response.json()["detail"].lower()


def test_analyze_endpoint_broken_file_handled_in_errors(client, tmp_path):
    """POST /api/analyze surfaces broken .py file in errors array while rendering valid code."""
    good_file = tmp_path / "valid.py"
    good_file.write_text("def good_func():\n    return 42\n", encoding="utf-8")

    bad_file = tmp_path / "broken.py"
    bad_file.write_text("def broken_syntax( :\n", encoding="utf-8")

    response = client.post("/api/analyze", json={"project_path": str(tmp_path)})
    assert response.status_code == 200
    data = response.json()
    graph = Graph(**data)

    # Valid file parsed into nodes
    func_names = {n.name for n in graph.nodes}
    assert "good_func" in func_names

    # Broken file recorded in errors
    error_files = [e.file_path for e in graph.errors]
    assert any("broken.py" in ef for ef in error_files)


def test_qwen_status_endpoint(client):
    """GET /api/qwen/status returns valid status ('connected' or 'disconnected')."""
    response = client.get("/api/qwen/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("connected", "disconnected")
    assert data.get("model") == "qwen2.5-coder:3b"


def test_open_in_editor_endpoint_success(client, monkeypatch):
    """POST /api/open_in_editor launches external editor with resolved path."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    import backend.api
    launched_calls = []

    def mock_launch(path):
        launched_calls.append(path)
        return {"launched": True, "file_path": str(path)}

    monkeypatch.setattr(backend.api, "launch_in_editor", mock_launch)

    response = client.post("/api/open_in_editor", json={"file_path": "sample_project.py"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["launched"] is True
    assert "sample_project.py" in data["file_path"]
    assert len(launched_calls) == 1


def test_open_in_editor_endpoint_missing_file_404(client):
    """POST /api/open_in_editor returns HTTP 404 for missing file without crashing."""
    response = client.post("/api/open_in_editor", json={"file_path": "non_existent_file_abc123.py"})
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "File not found" in data["detail"]


def test_symbol_detail_instability_metric(client):
    """GET /api/symbol/{id} includes correct instability metric across multiple symbols."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    # Symbol 1: sample_project.Dog -> fan_out=3, fan_in=2 => instability = 3/5 = 0.60
    resp_dog = client.get("/api/symbol/sample_project.Dog")
    assert resp_dog.status_code == 200
    dog = SymbolDetail(**resp_dog.json())
    assert dog.fan_out == 3
    assert dog.fan_in == 2
    assert dog.instability == 0.60

    # Symbol 2: sample_project.Animal -> fan_out=3, fan_in=3 => instability = 3/6 = 0.50
    resp_animal = client.get("/api/symbol/sample_project.Animal")
    assert resp_animal.status_code == 200
    animal = SymbolDetail(**resp_animal.json())
    assert animal.fan_out == 3
    assert animal.fan_in == 3
    assert animal.instability == 0.50

    # Symbol 3: sample_project (module) -> fan_out=6, fan_in=0 => instability = 6/6 = 1.00
    resp_mod = client.get("/api/symbol/sample_project")
    assert resp_mod.status_code == 200
    mod = SymbolDetail(**resp_mod.json())
    assert mod.fan_out == 6
    assert mod.fan_in == 0
    assert mod.instability == 1.00

    # Symbol 4: sample_project.Zoo.add_animal -> fan_out=0, fan_in=2 => instability = 0/2 = 0.00
    resp_method = client.get("/api/symbol/sample_project.Zoo.add_animal")
    assert resp_method.status_code == 200
    method = SymbolDetail(**resp_method.json())
    assert method.fan_out == 0
    assert method.fan_in == 2
    assert method.instability == 0.00





