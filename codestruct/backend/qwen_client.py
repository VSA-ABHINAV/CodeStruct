"""Qwen Assistant Client (Phase 8).

Handles integration with local Ollama instance running qwen2.5-coder:3b:
- Injects selected symbol details (name, kind, docstring, source, relationships) as system context.
- Handles connection errors gracefully without crashing or throwing unhandled exceptions.
"""

from typing import Any, Dict, List, Optional
import requests

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
DEFAULT_MODEL = "qwen2.5-coder:3b"
DEFAULT_TIMEOUT = 30.0


def build_system_context(
    symbol_detail: Optional[Dict[str, Any]] = None,
    source_snippet: Optional[str] = None,
    graph_summary: Optional[Dict[str, Any]] = None
) -> str:
    """Build a comprehensive system prompt incorporating the selected symbol's real data
    and architectural context from the project graph."""
    base_instructions = (
        "You are CodeStruct Assistant, an expert AI programming assistant integrated "
        "into the CodeStruct code navigation environment.\n"
        "Be concise, clear, and directly reference the selected symbol, its role, methods, "
        "and relationships when answering the user's questions. You have access to the "
        "project's architectural structure including module/class/function counts and "
        "relationship summaries."
    )

    if not symbol_detail:
        return (
            f"{base_instructions}\n\n"
            "No symbol is currently selected in the project graph. Provide general code guidance."
        )

    # Extract symbol metadata
    name = symbol_detail.get("name", "Unknown")
    kind = symbol_detail.get("kind", "symbol")
    file_path = symbol_detail.get("file_path", "unknown")
    lineno = symbol_detail.get("lineno", 0)
    end_lineno = symbol_detail.get("end_lineno", lineno)
    docstring = symbol_detail.get("docstring") or "No docstring provided."
    fan_in = symbol_detail.get("fan_in", 0)
    fan_out = symbol_detail.get("fan_out", 0)

    # Format incoming edges
    incoming_list = symbol_detail.get("incoming") or []
    if incoming_list:
        incoming_str = ", ".join(
            f"{edge.get('name', edge.get('id', ''))} [{edge.get('type', 'rel')}]"
            for edge in incoming_list
        )
    else:
        incoming_str = "None"

    # Format outgoing edges
    outgoing_list = symbol_detail.get("outgoing") or []
    if outgoing_list:
        outgoing_str = ", ".join(
            f"{edge.get('name', edge.get('id', ''))} [{edge.get('type', 'rel')}]"
            for edge in outgoing_list
        )
    else:
        outgoing_str = "None"

    # Build architectural context from graph summary
    arch_parts = []
    if graph_summary:
        summary = graph_summary.get("summary", {})
        arch_parts.append(
            f"- Project overview: {summary.get('node_count', 0)} nodes, "
            f"{summary.get('edge_count', 0)} edges, "
            f"{summary.get('module_count', 0)} modules, "
            f"{summary.get('class_count', 0)} classes, "
            f"{summary.get('function_count', 0)} functions, "
            f"{summary.get('method_count', 0)} methods"
        )
        # Add high-level edge type breakdown
        edge_counts = {}
        for edge in graph_summary.get("edges", []):
            etype = edge.get("type", "unknown")
            edge_counts[etype] = edge_counts.get(etype, 0) + 1
        if edge_counts:
            edge_summary = ", ".join(
                f"{count} {etype} edges" for etype, count in edge_counts.items()
            )
            arch_parts.append(f"- Relationship types: {edge_summary}")

    # Format source lines from symbol detail
    source_lines = []
    if source_snippet and source_snippet.strip():
        source_lines.append(f"\nSource Code Snippet:\n```python\n{source_snippet.strip()}\n```")

    context_lines = [
        base_instructions,
        "\nThe user is currently inspecting a specific symbol in their codebase:",
        f"- Symbol Name: {name}",
        f"- Symbol Kind: {kind}",
        f"- Source Location: {file_path} (Lines {lineno}–{end_lineno})",
        f"- Docstring: {docstring}",
        f"- Fan-In ({fan_in} incoming relationships): {incoming_str}",
        f"- Fan-Out ({fan_out} outgoing relationships): {outgoing_str}",
    ]

    # Add architectural context if available
    if arch_parts:
        context_lines.append("\nProject architectural context:")
        context_lines.extend(arch_parts)

    if source_lines:
        context_lines.extend(source_lines)

    context_lines.append(
        "\nWhen responding to the user, directly refer to this selected symbol and answer "
        "in the context of this code and its architectural relationships. "
        "Consider the project structure (modules, classes, functions, and their relationships)"
        " when explaining concepts or patterns."
    )

    return "\n".join(context_lines)


def query_qwen(
    message: str,
    symbol_detail: Optional[Dict[str, Any]] = None,
    source_snippet: Optional[str] = None,
    graph_summary: Optional[Dict[str, Any]] = None,
    ollama_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Send a message to Ollama with injected symbol context and architectural overview.
    
    Returns the model's reply string on success, or a clear error string starting
    with '[Error]' on failure (graceful error handling without raising exceptions).
    """
    url = ollama_url or OLLAMA_CHAT_URL
    target_model = model or DEFAULT_MODEL

    system_prompt = build_system_context(symbol_detail, source_snippet, graph_summary)

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "stream": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code != 200:
            return (
                f"[Error] Ollama returned HTTP {response.status_code}: {response.text}"
            )
        data = response.json()
        reply = data.get("message", {}).get("content", "")
        if not reply:
            return "[Error] Received empty response content from Ollama."
        return reply.strip()

    except requests.exceptions.ConnectionError:
        return (
            f"[Error] Ollama is not running or unreachable at {url}. "
            f"Please ensure Ollama is running ('ollama serve') with model '{target_model}'."
        )
    except requests.exceptions.Timeout:
        return f"[Error] Request to Ollama timed out after {timeout} seconds."
    except requests.exceptions.RequestException as e:
        return f"[Error] Network communication with Ollama failed: {str(e)}"
    except Exception as e:
        return f"[Error] Unexpected failure during Ollama chat: {str(e)}"


def check_ollama_connection(tags_url: Optional[str] = None, timeout: float = 3.0) -> bool:
    """Quick check if Ollama server is responsive."""
    url = tags_url or OLLAMA_TAGS_URL
    try:
        res = requests.get(url, timeout=timeout)
        return res.status_code == 200
    except Exception:
        return False
