"""API route handlers for CodeStruct (Phase 2).

Implements the three core analysis endpoints specified in Section 4.3:
- POST /api/analyze: Runs static analysis and stores result in app state
- GET /api/symbol/{node_id}: Returns Symbol Detail (inspector panel) with fan-in/fan-out
- GET /api/source: Returns Pygments-highlighted HTML slice for Code Viewer
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer, get_lexer_for_filename

from backend.analyzer import analyze_project, compute_impact
from backend.patterns import detect_patterns
from backend.qwen_client import check_ollama_connection, query_qwen
from backend.schemas import (
    AnalyzeRequest,
    ChatRequest,
    ChatResponse,
    Graph,
    ImpactResponse,
    OpenInEditorRequest,
    OpenInEditorResponse,
    PatternMatch,
    PatternsResponse,
    SourceResponse,
    SymbolDetail,
    SymbolEdge,
)

router = APIRouter(prefix="/api")

# Module-level store fallback for last analysis
_LAST_GRAPH: Optional[Dict[str, Any]] = None


def get_stored_graph(request: Request) -> Optional[Dict[str, Any]]:
    """Retrieve last analysis graph from app state or module fallback."""
    if hasattr(request.app.state, "last_graph") and request.app.state.last_graph:
        return request.app.state.last_graph
    return _LAST_GRAPH


def set_stored_graph(request: Request, graph: Dict[str, Any]) -> None:
    """Save last analysis graph to app state and module fallback."""
    request.app.state.last_graph = graph
    global _LAST_GRAPH
    _LAST_GRAPH = graph


@router.post("/analyze", response_model=Graph)
def post_analyze(payload: AnalyzeRequest, request: Request) -> Graph:
    """Analyze a Python project directory or file and cache the resulting graph in app state (Phase 11)."""
    raw_path = payload.project_path.strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="Project path cannot be empty.")

    candidate = Path(raw_path)

    # Resolution order for paths:
    # 1. If absolute, check candidate directly
    # 2. If relative, resolve relative to workspace root (D:\CodeStruct) first
    # 3. Fall back to package root (codestruct), then current working directory
    resolved_path: Optional[Path] = None
    if candidate.is_absolute():
        if candidate.exists():
            resolved_path = candidate.resolve()
    else:
        pkg_dir = Path(__file__).resolve().parent.parent  # .../codestruct
        workspace_root = pkg_dir.parent  # .../CodeStruct

        if (workspace_root / raw_path).exists():
            resolved_path = (workspace_root / raw_path).resolve()
        elif (pkg_dir / raw_path).exists():
            resolved_path = (pkg_dir / raw_path).resolve()
        elif (Path.cwd() / raw_path).exists():
            resolved_path = (Path.cwd() / raw_path).resolve()
        elif candidate.exists():
            resolved_path = candidate.resolve()

    if resolved_path is None or not resolved_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Project path does not exist: {raw_path}",
        )

    # Validate path is a directory or a .py file
    if resolved_path.is_file() and resolved_path.suffix != ".py":
        raise HTTPException(
            status_code=400,
            detail=f"Project path must be a directory or a .py file: {raw_path}",
        )

    if not resolved_path.is_dir() and not resolved_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Project path is not a directory and contains no .py files: {raw_path}",
        )

    result = analyze_project(str(resolved_path), force_refresh=payload.force_refresh)
    set_stored_graph(request, result)
    return Graph(**result)


def get_symbol_detail_from_graph(last_graph: Dict[str, Any], node_id: str) -> Optional[SymbolDetail]:
    """Helper to compute SymbolDetail from a stored graph for a specific node_id."""
    node_map = {n["id"]: n for n in last_graph.get("nodes", [])}
    if node_id not in node_map:
        for nid, node in node_map.items():
            if node.get("name") == node_id or nid.endswith("." + node_id):
                node_id = nid
                break
    target_node = node_map.get(node_id)
    if not target_node:
        return None

    incoming: list[SymbolEdge] = []
    outgoing: list[SymbolEdge] = []

    for edge in last_graph.get("edges", []):
        # Incoming edges: target == node_id
        if edge["target"] == node_id:
            src_id = edge["source"]
            src_node = node_map.get(src_id)
            src_name = src_node["name"] if src_node else src_id
            incoming.append(SymbolEdge(id=src_id, name=src_name, type=edge["type"]))
        # Outgoing edges: source == node_id
        if edge["source"] == node_id:
            tgt_id = edge["target"]
            tgt_node = node_map.get(tgt_id)
            tgt_name = tgt_node["name"] if tgt_node else tgt_id
            outgoing.append(SymbolEdge(id=tgt_id, name=tgt_name, type=edge["type"]))

    total_edges = len(incoming) + len(outgoing)
    instability = round(len(outgoing) / total_edges, 2) if total_edges > 0 else 0.0

    return SymbolDetail(
        id=target_node["id"],
        name=target_node["name"],
        kind=target_node["kind"],
        file_path=target_node["file_path"],
        lineno=target_node["lineno"],
        end_lineno=target_node["end_lineno"],
        docstring=target_node["docstring"],
        fan_in=len(incoming),
        fan_out=len(outgoing),
        incoming=incoming,
        outgoing=outgoing,
        instability=instability,
    )


def launch_in_editor(target_file: Path) -> None:
    """Launch a file with the system default external editor (fire-and-forget)."""
    if sys.platform == "win32":
        os.startfile(str(target_file))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target_file)])
    else:
        subprocess.Popen(["xdg-open", str(target_file)])


@router.post("/open_in_editor", response_model=OpenInEditorResponse)
def open_in_editor(payload: OpenInEditorRequest, request: Request) -> OpenInEditorResponse:
    """Open a file from the analyzed project in the system's default editor (Phase 12)."""
    last_graph = get_stored_graph(request)
    if not last_graph:
        raise HTTPException(
            status_code=400,
            detail="No project has been analyzed yet. Run POST /api/analyze first.",
        )

    project_root = Path(last_graph["project_root"]).resolve()

    file_path_str = payload.file_path.strip()
    if not file_path_str:
        raise HTTPException(status_code=400, detail="File path cannot be empty.")

    # Resolve target file path (same resolution logic as /api/source)
    if project_root.is_file():
        if file_path_str in (project_root.name, project_root.as_posix(), ""):
            target_file = project_root
        else:
            target_file = (project_root.parent / file_path_str).resolve()
    else:
        target_file = (project_root / file_path_str).resolve()

    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path_str}")

    # Fire-and-forget external launch via OS default handler
    try:
        launch_in_editor(target_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch editor: {e}")

    return OpenInEditorResponse(launched=True, file_path=str(target_file))


@router.get("/symbol/{node_id:path}", response_model=SymbolDetail)
def get_symbol_detail(node_id: str, request: Request) -> SymbolDetail:
    """Compute and return symbol details including fan-in, fan-out, incoming, and outgoing edges."""
    last_graph = get_stored_graph(request)
    if not last_graph:
        raise HTTPException(
            status_code=400,
            detail="No project has been analyzed yet. Run POST /api/analyze first.",
        )

    detail = get_symbol_detail_from_graph(last_graph, node_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {node_id}")

    return detail


@router.get("/patterns", response_model=PatternsResponse)
def get_patterns(request: Request) -> PatternsResponse:
    """Retrieve detected design patterns for the currently analyzed project (Phase 13)."""
    last_graph = get_stored_graph(request)
    if not last_graph:
        return PatternsResponse(patterns=[])

    raw_patterns = last_graph.get("patterns")
    if raw_patterns is None:
        ast_trees = last_graph.get("_ast_trees", {})
        raw_patterns = detect_patterns(last_graph, ast_trees)
        last_graph["patterns"] = raw_patterns

    return PatternsResponse(patterns=[PatternMatch(**p) for p in raw_patterns])


@router.get("/source", response_model=SourceResponse)
def get_source_slice(
    request: Request,
    file_path: str = Query(..., description="File path relative to the analyzed project_root"),
    start: Optional[int] = Query(None, description="1-based start line"),
    end: Optional[int] = Query(None, description="1-based end line"),
) -> SourceResponse:
    """Read a slice of source code and return syntax-highlighted HTML rendered by Pygments."""
    last_graph = get_stored_graph(request)
    if not last_graph:
        raise HTTPException(
            status_code=400,
            detail="No project has been analyzed yet. Run POST /api/analyze first.",
        )

    project_root = Path(last_graph["project_root"]).resolve()

    # Resolve target file path
    if project_root.is_file():
        # Project was a single file
        if file_path in (project_root.name, project_root.as_posix(), ""):
            target_file = project_root
        else:
            target_file = (project_root.parent / file_path).resolve()
    else:
        target_file = (project_root / file_path).resolve()

    # Validate file existence
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    # Read content
    try:
        content = target_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = target_file.read_text(encoding="latin-1")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

    lines = content.splitlines()
    total_lines = len(lines)

    start_line = 1 if (start is None or start < 1) else start
    end_line = total_lines if (end is None or end > total_lines) else end

    if start_line > end_line and total_lines > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid line range: start ({start_line}) cannot be greater than end ({end_line})",
        )

    if total_lines == 0:
        sliced_code = ""
        start_line = 1
        end_line = 1
    else:
        sliced_lines = lines[start_line - 1 : end_line]
        sliced_code = "\n".join(sliced_lines)

    # Highlight via Pygments
    try:
        lexer = get_lexer_for_filename(target_file.name, stripnl=False)
    except Exception:
        lexer = PythonLexer(stripnl=False)

    formatter = HtmlFormatter(
        nowrap=False,
        linespans="line",
        linenos="inline",
        linenostart=start_line,
        style="one-dark",
    )
    highlighted_html = highlight(sliced_code, lexer, formatter)

    return SourceResponse(html=highlighted_html, start=start_line, end=end_line)


@router.post("/qwen/chat", response_model=ChatResponse)
def chat_with_qwen(
    request: Request,
    body: ChatRequest,
) -> ChatResponse:
    """Send user message to local Ollama Qwen assistant with symbol context and architectural overview (Phase 8)."""
    symbol_dict = None
    source_snippet = None
    graph_summary = None

    last_graph = get_stored_graph(request)
    if last_graph:
        # Build architectural summary from the stored graph
        summary = last_graph.get("summary", {})
        if summary:
            edge_counts: Dict[str, int] = {}
            for edge in last_graph.get("edges", []):
                etype = edge.get("type", "unknown")
                edge_counts[etype] = edge_counts.get(etype, 0) + 1

            graph_summary = {
                "summary": {
                    "node_count": summary.get("node_count", 0),
                    "edge_count": summary.get("edge_count", 0),
                    "module_count": summary.get("module_count", 0),
                    "class_count": summary.get("class_count", 0),
                    "function_count": summary.get("function_count", 0),
                    "method_count": summary.get("method_count", 0),
                },
                "edges": last_graph.get("edges", []),
            }

        if body.context_symbol_id:
            detail = get_symbol_detail_from_graph(last_graph, body.context_symbol_id)
            if detail:
                symbol_dict = detail.model_dump()
                # Attempt to extract raw source code snippet for context
                try:
                    project_root = Path(last_graph["project_root"]).resolve()
                    if project_root.is_file():
                        target_file = (
                            project_root
                            if detail.file_path in (project_root.name, project_root.as_posix(), "")
                            else (project_root.parent / detail.file_path).resolve()
                        )
                    else:
                        target_file = (project_root / detail.file_path).resolve()

                    if target_file.is_file():
                        lines = target_file.read_text(encoding="utf-8").splitlines()
                        sliced = lines[max(0, detail.lineno - 1) : detail.end_lineno]
                        source_snippet = "\n".join(sliced)
                except Exception:
                    source_snippet = None

    reply = query_qwen(
        message=body.message,
        symbol_detail=symbol_dict,
        source_snippet=source_snippet,
        graph_summary=graph_summary,
    )
    return ChatResponse(reply=reply)


@router.get("/qwen/status")
def get_qwen_status(request: Request) -> Dict[str, Any]:
    """Check Ollama service status for startup validation and panel indicator (Phase 9)."""
    is_connected = check_ollama_connection(timeout=1.0)
    request.app.state.ollama_connected = is_connected
    return {
        "status": "connected" if is_connected else "disconnected",
        "model": "qwen2.5-coder:3b",
    }


@router.get("/impact/{node_id:path}", response_model=ImpactResponse)
def get_impact(node_id: str, request: Request, max_depth: int = 5) -> ImpactResponse:
    last_graph = get_stored_graph(request)
    if not last_graph:
        raise HTTPException(status_code=400, detail="No project has been analyzed yet. Run POST /api/analyze first.")
    impacted = compute_impact(last_graph, node_id, max_depth=max_depth)
    return ImpactResponse(symbol_id=node_id, max_depth=max_depth, impacted=impacted)
