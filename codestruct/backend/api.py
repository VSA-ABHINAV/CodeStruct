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

from backend.advanced_architecture import MalformedLLMOutputError, cluster_architecture
from backend.analyzer import analyze_project, compute_impact
from backend.config import get_resource_base, load_config, save_config
from backend.llm_client import build_system_context, query_llm
from backend.llm_providers import get_provider
from backend.model_config import ModelRegistry
from backend.patterns import detect_patterns
from backend.qwen_client import check_ollama_connection, query_qwen
from backend.schemas import (
    AdvancedArchitectureRequest,
    AdvancedArchitectureResponse,
    AnalyzeRequest,
    ChatRequest,
    ChatResponse,
    ComponentCluster,
    Graph,
    ImpactResponse,
    ModelConfigCreate,
    ModelConfigPublic,
    ModelListResponse,
    OpenInEditorRequest,
    OpenInEditorResponse,
    PatternMatch,
    PatternsResponse,
    SetDefaultModelRequest,
    SourceResponse,
    SymbolDetail,
    SymbolEdge,
    ValidateModelResponse,
    WizardCompleteRequest,
    WizardPullRequest,
)
from backend.wizard import (
    get_task_state,
    run_system_checks,
    start_ollama_install_task,
    start_ollama_pull_task,
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
        resource_base = get_resource_base()

        if (workspace_root / raw_path).exists():
            resolved_path = (workspace_root / raw_path).resolve()
        elif (pkg_dir / raw_path).exists():
            resolved_path = (pkg_dir / raw_path).resolve()
        elif (resource_base / raw_path).exists():
            resolved_path = (resource_base / raw_path).resolve()
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


def _extract_chat_context(request: Request, context_symbol_id: Optional[str]):
    """Build symbol_detail, source_snippet, and graph_summary context for chat endpoints."""
    symbol_dict = None
    source_snippet = None
    graph_summary = None

    last_graph = get_stored_graph(request)
    if last_graph:
        summary = last_graph.get("summary", {})
        if summary:
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

        if context_symbol_id:
            detail = get_symbol_detail_from_graph(last_graph, context_symbol_id)
            if detail:
                symbol_dict = detail.model_dump()
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

    return symbol_dict, source_snippet, graph_summary


@router.post("/llm/chat", response_model=ChatResponse)
def chat_with_llm(
    request: Request,
    body: ChatRequest,
) -> ChatResponse:
    """Send user message to any configured LLM provider (or default chat model) with symbol context."""
    registry = ModelRegistry()
    rec = registry.resolve_model(model_id=body.model_id, feature="chat")
    if rec is None:
        return ChatResponse(
            reply="[Error] No model configured or enabled. Open Settings (⚙️) to add or enable an LLM model."
        )

    if body.model_id and rec.id != body.model_id:
        raise HTTPException(status_code=404, detail=f"Configured model not found or disabled: {body.model_id}")

    symbol_dict, source_snippet, graph_summary = _extract_chat_context(request, body.context_symbol_id)

    # Preserve legacy query_qwen behavior when default Ollama is active (ensures mock compatibility)
    if rec.provider == "ollama" and rec.id == "ollama-default":
        reply = query_qwen(
            message=body.message,
            symbol_detail=symbol_dict,
            source_snippet=source_snippet,
            graph_summary=graph_summary,
            model=rec.model_name,
        )
        return ChatResponse(reply=reply)

    system_prompt = build_system_context(symbol_dict, source_snippet, graph_summary)
    decrypted_key = registry.get_decrypted_api_key(rec.id)
    reply = query_llm(
        provider_config=rec,
        messages=[{"role": "user", "content": body.message}],
        system_prompt=system_prompt,
        model=rec.model_name,
        decrypted_api_key=decrypted_key,
    )
    return ChatResponse(reply=reply)


@router.post("/qwen/chat", response_model=ChatResponse)
def chat_with_qwen(
    request: Request,
    body: ChatRequest,
) -> ChatResponse:
    """Deprecated alias for /api/llm/chat (Phase 8 backward compatibility)."""
    return chat_with_llm(request, body)


@router.get("/qwen/status")
def get_qwen_status(request: Request) -> Dict[str, Any]:
    """Check active default chat model / Ollama status (backward compatible)."""
    registry = ModelRegistry()
    rec = registry.resolve_model(feature="chat")
    if rec and rec.provider != "ollama":
        has_key = bool(rec.api_key_encrypted)
        is_connected = rec.enabled and (has_key or rec.provider == "custom")
        return {
            "status": "connected" if is_connected else "disconnected",
            "model": rec.model_name,
            "display_name": rec.display_name,
            "provider": rec.provider,
        }

    is_connected = check_ollama_connection(timeout=1.0)
    request.app.state.ollama_connected = is_connected
    return {
        "status": "connected" if is_connected else "disconnected",
        "model": rec.model_name if rec else "qwen2.5-coder:3b",
        "display_name": rec.display_name if rec else "Ollama (qwen2.5-coder:3b)",
        "provider": "ollama",
    }


@router.get("/impact/{node_id:path}", response_model=ImpactResponse)
def get_impact(node_id: str, request: Request, max_depth: int = 5) -> ImpactResponse:
    last_graph = get_stored_graph(request)
    if not last_graph:
        raise HTTPException(status_code=400, detail="No project has been analyzed yet. Run POST /api/analyze first.")
    impacted = compute_impact(last_graph, node_id, max_depth=max_depth)
    return ImpactResponse(symbol_id=node_id, max_depth=max_depth, impacted=impacted)


@router.post("/architecture/advanced", response_model=AdvancedArchitectureResponse)
def post_advanced_architecture(
    request: Request,
    body: Optional[AdvancedArchitectureRequest] = None,
) -> AdvancedArchitectureResponse:
    """Analyze AST graph and cluster symbols into architectural components via configured LLM (Phase 19 + Multi-LLM)."""
    last_graph = get_stored_graph(request)
    if not last_graph:
        raise HTTPException(
            status_code=400,
            detail="No project has been analyzed yet. Run POST /api/analyze first.",
        )

    force_refresh = body.force_refresh if body else False
    requested_model_id = body.model_id if body else None

    registry = ModelRegistry()
    rec = registry.resolve_model(model_id=requested_model_id, feature="architecture")
    if requested_model_id and (rec is None or rec.id != requested_model_id):
        raise HTTPException(status_code=404, detail=f"Configured model not found or disabled: {requested_model_id}")

    decrypted_key = registry.get_decrypted_api_key(rec.id) if rec else None

    try:
        result = cluster_architecture(
            last_graph,
            force_refresh=force_refresh,
            timeout=90.0,
            provider_config=rec,
            decrypted_api_key=decrypted_key,
        )
        return AdvancedArchitectureResponse(**result)
    except MalformedLLMOutputError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM architectural clustering failed validation: {str(e)}"
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during architectural clustering: {str(e)}"
        )


# ---------------------------------------------------------------------------
# Multi-LLM Model Management Endpoints
# ---------------------------------------------------------------------------

@router.get("/models", response_model=ModelListResponse)
def list_configured_models() -> ModelListResponse:
    """List all configured LLM models with API keys masked (never exposed in plaintext)."""
    registry = ModelRegistry()
    models = [ModelConfigPublic(**m.model_dump()) for m in registry.list_models()]
    return ModelListResponse(models=models)


@router.post("/models", response_model=ModelConfigPublic)
def upsert_configured_model(body: ModelConfigCreate) -> ModelConfigPublic:
    """Add or update an LLM model configuration; API keys are immediately Fernet-encrypted."""
    registry = ModelRegistry()
    saved = registry.upsert_model(
        model_id=body.id,
        provider=body.provider,
        display_name=body.display_name,
        model_name=body.model_name,
        api_key=body.api_key,
        base_url=body.base_url,
        deployment_name=body.deployment_name,
        api_version=body.api_version,
        enabled=body.enabled,
        is_default_chat=body.is_default_chat,
        is_default_architecture=body.is_default_architecture,
    )
    return ModelConfigPublic(**saved.model_dump())


@router.delete("/models/{model_id}")
def delete_configured_model(model_id: str) -> Dict[str, Any]:
    """Delete a configured LLM model."""
    registry = ModelRegistry()
    removed = registry.delete_model(model_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    return {"deleted": True, "id": model_id}


@router.post("/models/{model_id}/validate", response_model=ValidateModelResponse)
def validate_configured_model(model_id: str) -> ValidateModelResponse:
    """Test provider connectivity and return available models without exposing credentials."""
    registry = ModelRegistry()
    rec = registry.get_record(model_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    decrypted_key = registry.get_decrypted_api_key(model_id)
    if rec.provider in ("openai", "anthropic", "gemini", "azure") and not decrypted_key:
        return ValidateModelResponse(
            valid=False,
            models=[],
            error=f"Missing API key for {rec.display_name}. Please configure an API key.",
        )

    provider = get_provider(rec, decrypted_api_key=decrypted_key)
    res = provider.validate_connection()
    return ValidateModelResponse(
        valid=bool(res.get("valid")),
        models=list(res.get("models") or []),
        error=res.get("error"),
    )


@router.post("/models/{model_id}/set-default", response_model=ModelConfigPublic)
def set_default_model(model_id: str, body: SetDefaultModelRequest) -> ModelConfigPublic:
    """Set the default model for Chat, Architecture, or both."""
    registry = ModelRegistry()
    updated = registry.set_default(model_id, target=body.target)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    return ModelConfigPublic(**updated.model_dump())


# ---------------------------------------------------------------------------
# First-Run Setup Wizard Endpoints
# ---------------------------------------------------------------------------

@router.get("/wizard/status")
def get_wizard_status(models_dir: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Return persisted config and live hardware/OS/Ollama readiness checks."""
    cfg = load_config()
    checks = run_system_checks(custom_models_dir=models_dir)
    return {
        "config": cfg,
        "system_checks": checks,
        "task_state": get_task_state(),
    }


@router.post("/wizard/complete")
def post_wizard_complete(body: WizardCompleteRequest, request: Request) -> Dict[str, Any]:
    """Persist First-Run Wizard selections to %APPDATA%\\CodeStruct\\config.json."""
    updates: Dict[str, Any] = {
        "first_run_completed": True,
        "ai_enabled": body.ai_enabled,
        "ollama_model": body.ollama_model.strip() or "qwen2.5-coder:3b",
    }
    if body.ollama_models_dir and body.ollama_models_dir.strip():
        target = Path(body.ollama_models_dir.strip()).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        updates["ollama_models_dir"] = str(target)
        os.environ["OLLAMA_MODELS"] = str(target)

    saved = save_config(updates)
    request.app.state.ollama_connected = check_ollama_connection(timeout=1.0)
    return {"saved": True, "config": saved}


@router.post("/wizard/ollama/install")
def post_wizard_ollama_install() -> Dict[str, Any]:
    """Trigger optional Ollama runtime installation in background."""
    return start_ollama_install_task()


@router.post("/wizard/ollama/pull")
def post_wizard_ollama_pull(body: WizardPullRequest) -> Dict[str, Any]:
    """Start Ollama daemon with custom OLLAMA_MODELS path and pull the LLM."""
    return start_ollama_pull_task(models_dir=body.models_dir, model_name=body.model_name)


@router.get("/wizard/ollama/task_status")
def get_wizard_ollama_task_status() -> Dict[str, Any]:
    """Return live status and logs for ongoing Ollama install/pull task."""
    return get_task_state()


@router.post("/wizard/browse_folder")
def post_wizard_browse_folder(request: Request) -> Dict[str, Any]:
    """Open native folder picker dialog via pywebview to choose custom storage/project path."""
    win = getattr(request.app.state, "webview_window", None)
    if win is None:
        return {"selected": None, "supported": False, "message": "Native dialog only available inside desktop window."}
    try:
        import webview
        dialog_type = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or getattr(webview, "FOLDER_DIALOG", 20)
        result = win.create_file_dialog(dialog_type)
        if result and len(result) > 0:
            return {"selected": str(result[0]), "supported": True}
        return {"selected": None, "supported": True}
    except Exception as e:
        return {"selected": None, "supported": False, "message": str(e)}
