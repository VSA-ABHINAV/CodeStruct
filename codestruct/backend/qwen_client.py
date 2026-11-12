"""Deprecated Qwen Assistant Client Wrapper (Phase 8 -> Refactored to llm_client.py).

Preserved for 100% backward compatibility with legacy callers and tests
(/api/qwen/chat, /api/qwen/status). Delegates core context building to
backend.llm_client and routes Ollama calls through OllamaProvider.
"""

from typing import Any, Dict, Optional
import requests

from backend.config import load_config
from backend.llm_client import DEFAULT_TIMEOUT, build_system_context
from backend.llm_providers import OllamaProvider
from backend.model_config import ModelConfigRecord

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
DEFAULT_MODEL = "qwen2.5-coder:3b"


def query_qwen(
    message: str,
    symbol_detail: Optional[Dict[str, Any]] = None,
    source_snippet: Optional[str] = None,
    graph_summary: Optional[Dict[str, Any]] = None,
    ollama_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    system_prompt: Optional[str] = None,
) -> str:
    """Deprecated wrapper preserving Phase 8 signature; delegates to OllamaProvider."""
    cfg = load_config()
    cfg_host = cfg.get("ollama_host", "http://localhost:11434").rstrip("/")
    default_chat = OLLAMA_CHAT_URL if OLLAMA_CHAT_URL != "http://localhost:11434/api/chat" else f"{cfg_host}/api/chat"
    target_url = ollama_url or default_chat
    target_model = model or cfg.get("ollama_model", DEFAULT_MODEL)

    if system_prompt is None:
        system_prompt = build_system_context(symbol_detail, source_snippet, graph_summary)

    rec = ModelConfigRecord(
        id="ollama-legacy",
        provider="ollama",
        display_name=f"Ollama ({target_model})",
        model_name=target_model,
        base_url=cfg_host,
    )
    provider = OllamaProvider(rec)
    return provider.chat(
        messages=[{"role": "user", "content": message}],
        system_prompt=system_prompt,
        model=target_model,
        timeout=timeout,
        ollama_url=target_url,
    )


def check_ollama_connection(tags_url: Optional[str] = None, timeout: float = 3.0) -> bool:
    """Quick check if Ollama server is responsive."""
    if tags_url:
        url = tags_url
    elif OLLAMA_TAGS_URL != "http://localhost:11434/api/tags":
        url = OLLAMA_TAGS_URL
    else:
        cfg_host = load_config().get("ollama_host", "http://localhost:11434").rstrip("/")
        url = f"{cfg_host}/api/tags"
    try:
        res = requests.get(url, timeout=timeout)
        return res.status_code == 200
    except Exception:
        return False
