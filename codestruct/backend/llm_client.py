"""Generic Multi-LLM Client (Refactored from qwen_client.py).

Routes requests through any configured LLMProvider (Ollama, OpenAI, Anthropic,
Google Gemini, Azure OpenAI, Custom OpenAI-compatible) while injecting symbol
and architectural context. Handles errors gracefully without exposing API keys.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.llm_providers import get_provider
from backend.model_config import ModelConfigRecord, ModelRegistry

logger = logging.getLogger("codestruct.llm_client")

DEFAULT_TIMEOUT = 30.0


def build_system_context(
    symbol_detail: Optional[Dict[str, Any]] = None,
    source_snippet: Optional[str] = None,
    graph_summary: Optional[Dict[str, Any]] = None,
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

    name = symbol_detail.get("name", "Unknown")
    kind = symbol_detail.get("kind", "symbol")
    file_path = symbol_detail.get("file_path", "unknown")
    lineno = symbol_detail.get("lineno", 0)
    end_lineno = symbol_detail.get("end_lineno", lineno)
    docstring = symbol_detail.get("docstring") or "No docstring provided."
    fan_in = symbol_detail.get("fan_in", 0)
    fan_out = symbol_detail.get("fan_out", 0)

    incoming_list = symbol_detail.get("incoming") or []
    if incoming_list:
        incoming_str = ", ".join(
            f"{edge.get('name', edge.get('id', ''))} [{edge.get('type', 'rel')}]"
            for edge in incoming_list
        )
    else:
        incoming_str = "None"

    outgoing_list = symbol_detail.get("outgoing") or []
    if outgoing_list:
        outgoing_str = ", ".join(
            f"{edge.get('name', edge.get('id', ''))} [{edge.get('type', 'rel')}]"
            for edge in outgoing_list
        )
    else:
        outgoing_str = "None"

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
        edge_counts: Dict[str, int] = {}
        for edge in graph_summary.get("edges", []):
            etype = edge.get("type", "unknown")
            edge_counts[etype] = edge_counts.get(etype, 0) + 1
        if edge_counts:
            edge_summary = ", ".join(
                f"{count} {etype} edges" for etype, count in edge_counts.items()
            )
            arch_parts.append(f"- Relationship types: {edge_summary}")

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


def query_llm(
    provider_config: ModelConfigRecord,
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    decrypted_api_key: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> str:
    """Send a chat request to any configured LLM provider.
    
    Returns the model's reply string on success, or an error string starting with '[Error]'.
    """
    if not provider_config.enabled:
        return f"[Error] Model '{provider_config.display_name}' is disabled in Settings."

    # Guard missing API keys for cloud providers before dispatching network calls
    if provider_config.provider in ("openai", "anthropic", "gemini", "azure") and not decrypted_api_key:
        return (
            f"[Error] Missing or unreadable API key for {provider_config.display_name} "
            f"({provider_config.provider}). Please open Settings (⚙️) and re-enter the API key."
        )

    try:
        provider = get_provider(provider_config, decrypted_api_key=decrypted_api_key)
        return provider.chat(
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            timeout=timeout,
            **kwargs,
        )
    except Exception as e:
        logger.error(f"[LLM Client] Provider invocation failed: {type(e).__name__}")
        return f"[Error] LLM provider failure: {str(e)}"

