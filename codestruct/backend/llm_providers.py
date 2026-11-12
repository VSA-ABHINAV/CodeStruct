"""Abstract & Concrete Multi-LLM Provider Implementations.

Supports:
- OllamaProvider (Local Ollama /api/chat and /api/tags)
- OpenAIProvider (OpenAI, Azure OpenAI, Custom OpenAI-Compatible endpoints)
- AnthropicProvider (Claude Messages API)
- GeminiProvider (Google Gemini via google-genai SDK)

Security: API keys are held only transiently in memory and redacted from all error strings/logs.
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional

import requests

from backend.model_config import ModelConfigRecord

logger = logging.getLogger("codestruct.llm_providers")


def _redact_secret(text: str, secret: Optional[str]) -> str:
    """Ensure raw API keys never leak into exception strings or logs."""
    if not text or not secret:
        return text
    return text.replace(secret, "***REDACTED***")


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, config: ModelConfigRecord, api_key: Optional[str] = None):
        self.config = config
        self.api_key = api_key

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> str:
        """Send chat messages to the provider and return the text reply or '[Error] ...'."""

    @abstractmethod
    def validate_connection(self) -> Dict[str, Any]:
        """Test connectivity and auth; return {'valid': bool, 'models': [...], 'error': str|None}."""

    @abstractmethod
    def list_models(self) -> List[str]:
        """Return list of available model identifiers from this provider."""


class OllamaProvider(LLMProvider):
    """Local Ollama REST API provider."""

    def _base_url(self) -> str:
        return (self.config.base_url or "http://localhost:11434").rstrip("/")

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> str:
        url = kwargs.get("ollama_url") or f"{self._base_url()}/api/chat"
        target_model = model or self.config.model_name or "qwen2.5-coder:3b"

        full_messages: List[Dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": target_model,
            "messages": full_messages,
            "stream": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=timeout)
            if response.status_code != 200:
                return f"[Error] Ollama returned HTTP {response.status_code}: {response.text}"
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

    def list_models(self) -> List[str]:
        url = f"{self._base_url()}/api/tags"
        try:
            res = requests.get(url, timeout=3.0)
            if res.status_code == 200:
                return [m.get("name", "") for m in res.json().get("models", []) if m.get("name")]
        except Exception:
            pass
        return []

    def validate_connection(self) -> Dict[str, Any]:
        url = f"{self._base_url()}/api/tags"
        try:
            res = requests.get(url, timeout=3.0)
            if res.status_code == 200:
                models = [m.get("name", "") for m in res.json().get("models", []) if m.get("name")]
                return {"valid": True, "models": models, "error": None}
            return {"valid": False, "models": [], "error": f"Ollama returned HTTP {res.status_code}"}
        except Exception as e:
            return {"valid": False, "models": [], "error": f"Cannot reach Ollama at {url}: {str(e)}"}


class OpenAIProvider(LLMProvider):
    """OpenAI, Azure OpenAI, and Custom OpenAI-Compatible provider."""

    def _build_client(self, timeout: float = 30.0) -> Any:
        import openai

        if self.config.provider == "azure":
            endpoint = self.config.base_url
            if not endpoint:
                raise ValueError("Azure OpenAI requires a Base URL / Endpoint.")
            if not self.api_key:
                raise ValueError("Azure OpenAI requires an API key.")
            return openai.AzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=endpoint,
                api_version=self.config.api_version or "2024-06-01",
                timeout=timeout,
            )

        key = self.api_key
        if self.config.provider == "openai" and not key:
            raise ValueError("OpenAI requires an API key.")
        if self.config.provider == "custom" and not key:
            # Some local OpenAI-compatible servers (LM Studio / vLLM) do not enforce a key
            key = "not-needed"

        kwargs: Dict[str, Any] = {"api_key": key, "timeout": timeout}
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        return openai.OpenAI(**kwargs)

    def _target_model(self, override: Optional[str] = None) -> str:
        if override:
            return override
        if self.config.provider == "azure" and self.config.deployment_name:
            return self.config.deployment_name
        return self.config.model_name or "gpt-4o-mini"

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> str:
        target_model = self._target_model(model)
        full_messages: List[Dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            client = self._build_client(timeout=timeout)
            resp = client.chat.completions.create(
                model=target_model,
                messages=full_messages,
            )
            content = resp.choices[0].message.content if resp.choices else ""
            if not content:
                return f"[Error] Received empty response from {self.config.provider}."
            return content.strip()
        except Exception as e:
            safe_err = _redact_secret(str(e), self.api_key)
            return f"[Error] {self.config.provider.upper()} request failed: {safe_err}"

    def list_models(self) -> List[str]:
        try:
            client = self._build_client(timeout=10.0)
            if self.config.provider == "azure":
                return [self._target_model()]
            page = client.models.list()
            return sorted([m.id for m in page.data if getattr(m, "id", None)])
        except Exception:
            return []

    def validate_connection(self) -> Dict[str, Any]:
        try:
            client = self._build_client(timeout=10.0)
            if self.config.provider == "azure":
                # Azure deployments typically validate via minimal chat completion
                client.chat.completions.create(
                    model=self._target_model(),
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                )
                return {"valid": True, "models": [self._target_model()], "error": None}

            page = client.models.list()
            models = sorted([m.id for m in page.data if getattr(m, "id", None)])
            return {"valid": True, "models": models, "error": None}
        except Exception as e:
            safe_err = _redact_secret(str(e), self.api_key)
            return {"valid": False, "models": [], "error": safe_err}


class AnthropicProvider(LLMProvider):
    """Anthropic Claude Messages API provider."""

    DEFAULT_ANTHROPIC_MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]

    def _build_client(self, timeout: float = 30.0) -> Any:
        import anthropic

        if not self.api_key:
            raise ValueError("Anthropic requires an API key.")
        kwargs: Dict[str, Any] = {"api_key": self.api_key, "timeout": timeout}
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        return anthropic.Anthropic(**kwargs)

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> str:
        target_model = model or self.config.model_name or "claude-3-5-sonnet-20241022"
        clean_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]
        try:
            client = self._build_client(timeout=timeout)
            req_kwargs: Dict[str, Any] = {
                "model": target_model,
                "max_tokens": 4096,
                "messages": clean_messages,
            }
            if system_prompt:
                req_kwargs["system"] = system_prompt
            resp = client.messages.create(**req_kwargs)
            parts = [blk.text for blk in resp.content if getattr(blk, "type", "") == "text" and getattr(blk, "text", None)]
            reply = "\n".join(parts).strip()
            if not reply:
                return "[Error] Received empty response from Anthropic."
            return reply
        except Exception as e:
            safe_err = _redact_secret(str(e), self.api_key)
            return f"[Error] Anthropic request failed: {safe_err}"

    def list_models(self) -> List[str]:
        try:
            client = self._build_client(timeout=10.0)
            if hasattr(client, "models"):
                page = client.models.list()
                ids = [m.id for m in page.data if getattr(m, "id", None)]
                if ids:
                    return ids
        except Exception:
            pass
        return list(self.DEFAULT_ANTHROPIC_MODELS)

    def validate_connection(self) -> Dict[str, Any]:
        try:
            client = self._build_client(timeout=10.0)
            if hasattr(client, "models"):
                page = client.models.list()
                models = [m.id for m in page.data if getattr(m, "id", None)]
                return {"valid": True, "models": models or list(self.DEFAULT_ANTHROPIC_MODELS), "error": None}
            # Fallback validation call
            client.messages.create(
                model=self.config.model_name or "claude-3-5-haiku-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"valid": True, "models": list(self.DEFAULT_ANTHROPIC_MODELS), "error": None}
        except Exception as e:
            safe_err = _redact_secret(str(e), self.api_key)
            return {"valid": False, "models": [], "error": safe_err}


class GeminiProvider(LLMProvider):
    """Google Gemini API provider using official google-genai SDK."""

    DEFAULT_GEMINI_MODELS = [
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]

    def _build_client(self) -> Any:
        from google import genai

        if not self.api_key:
            raise ValueError("Google Gemini requires an API key.")
        return genai.Client(api_key=self.api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> str:
        from google.genai import types

        target_model = model or self.config.model_name or "gemini-1.5-flash"
        # Format conversation messages for Gemini
        formatted_lines: List[str] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if len(messages) == 1 and role == "user":
                formatted_lines.append(content)
            else:
                formatted_lines.append(f"[{role.upper()}]: {content}")
        contents = "\n\n".join(formatted_lines)

        try:
            client = self._build_client()
            gen_config = types.GenerateContentConfig(system_instruction=system_prompt) if system_prompt else None
            resp = client.models.generate_content(
                model=target_model,
                contents=contents,
                config=gen_config,
            )
            reply = getattr(resp, "text", None) or ""
            if not reply.strip():
                return "[Error] Received empty response from Google Gemini."
            return reply.strip()
        except Exception as e:
            safe_err = _redact_secret(str(e), self.api_key)
            return f"[Error] Google Gemini request failed: {safe_err}"

    def list_models(self) -> List[str]:
        try:
            client = self._build_client()
            models: List[str] = []
            for m in client.models.list():
                name = getattr(m, "name", "")
                if name.startswith("models/"):
                    name = name[len("models/"):]
                actions = getattr(m, "supported_actions", None) or []
                if not actions or "generateContent" in actions:
                    if name:
                        models.append(name)
            return sorted(models) if models else list(self.DEFAULT_GEMINI_MODELS)
        except Exception:
            return list(self.DEFAULT_GEMINI_MODELS)

    def validate_connection(self) -> Dict[str, Any]:
        try:
            client = self._build_client()
            models: List[str] = []
            for m in client.models.list():
                name = getattr(m, "name", "")
                if name.startswith("models/"):
                    name = name[len("models/"):]
                if name and ("gemini" in name.lower() or "gemma" in name.lower()):
                    models.append(name)
            return {"valid": True, "models": sorted(models) or list(self.DEFAULT_GEMINI_MODELS), "error": None}
        except Exception as e:
            safe_err = _redact_secret(str(e), self.api_key)
            return {"valid": False, "models": [], "error": safe_err}


def get_provider(config: ModelConfigRecord, decrypted_api_key: Optional[str] = None) -> LLMProvider:
    """Factory returning the concrete LLMProvider instance for a ModelConfigRecord."""
    if config.provider == "ollama":
        return OllamaProvider(config, decrypted_api_key)
    if config.provider in ("openai", "azure", "custom"):
        return OpenAIProvider(config, decrypted_api_key)
    if config.provider == "anthropic":
        return AnthropicProvider(config, decrypted_api_key)
    if config.provider == "gemini":
        return GeminiProvider(config, decrypted_api_key)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")

