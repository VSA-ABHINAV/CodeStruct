"""Tests for Multi-LLM Provider Support, Fernet Key Encryption & Provider-Agnostic Safety Net."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

TESTS_DIR = Path(__file__).resolve().parent
CODESTRUCT_DIR = TESTS_DIR.parent
if str(CODESTRUCT_DIR) not in sys.path:
    sys.path.insert(0, str(CODESTRUCT_DIR))

from backend.advanced_architecture import clear_architecture_cache
from backend.llm_providers import _redact_secret, get_provider
from backend.main import app
from backend.model_config import (
    ModelConfigRecord,
    ModelRegistry,
    decrypt_api_key,
    encrypt_api_key,
    mask_api_key,
)
from backend.schemas import AdvancedArchitectureResponse

SAMPLE_PROJECT_DIR = CODESTRUCT_DIR / "sample_project"


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Isolate %APPDATA% and %LOCALAPPDATA% to tmp_path so tests never alter real config."""
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    roaming.mkdir()
    local.mkdir()
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    clear_architecture_cache()
    yield roaming, local
    clear_architecture_cache()


@pytest.fixture
def client(isolated_env):
    with TestClient(app) as c:
        yield c


def test_api_key_encryption_never_plaintext(isolated_env):
    """Verify Fernet encryption roundtrips with machine GUID and never stores plaintext on disk."""
    roaming, _ = isolated_env
    secret = "sk-proj-supersecret12345678abcd"

    blob = encrypt_api_key(secret, machine_id="machine-guid-1")
    assert blob.startswith("enc:v1:")
    assert secret not in blob

    # Roundtrip with matching machine ID
    assert decrypt_api_key(blob, machine_id="machine-guid-1") == secret
    # Different machine ID fails decryption cleanly
    assert decrypt_api_key(blob, machine_id="wrong-machine-guid") is None
    # Refuses non-encrypted string
    assert decrypt_api_key(secret, machine_id="machine-guid-1") is None

    # Save via ModelRegistry and verify disk JSON contains zero plaintext
    reg = ModelRegistry(machine_id="machine-guid-1")
    pub = reg.upsert_model(
        provider="openai",
        display_name="GPT-4o",
        model_name="gpt-4o",
        api_key=secret,
    )
    assert pub.has_key is True
    assert pub.masked_key == mask_api_key(secret)
    assert secret not in json.dumps(pub.model_dump())

    raw_disk = (roaming / "CodeStruct" / "models.json").read_text(encoding="utf-8")
    assert secret not in raw_disk, "Plaintext API key leaked onto disk!"
    assert "enc:v1:" in raw_disk


def test_redact_secret_prevents_error_leak():
    secret = "sk-ant-verysecret999"
    err = f"Auth failed for Bearer {secret} at api.anthropic.com"
    redacted = _redact_secret(err, secret)
    assert secret not in redacted
    assert "***REDACTED***" in redacted


def test_legacy_ollama_auto_migration(isolated_env):
    """When models.json is absent, ModelRegistry auto-migrates default Ollama config."""
    roaming, _ = isolated_env
    models_file = roaming / "CodeStruct" / "models.json"
    assert not models_file.exists()

    reg = ModelRegistry()
    models = reg.list_models()
    assert len(models) == 1
    assert models[0].id == "ollama-default"
    assert models[0].provider == "ollama"
    assert models[0].is_default_chat is True
    assert models[0].is_default_architecture is True
    assert models_file.is_file()


def test_model_crud_and_dual_defaults_api(client, isolated_env):
    """Verify /api/models CRUD, masking, and independent Chat vs Architecture defaults."""
    roaming, _ = isolated_env

    # 1. Add OpenAI, Anthropic, Gemini, Azure, and Custom models
    providers_to_add = [
        {
            "id": "mod-openai",
            "provider": "openai",
            "display_name": "OpenAI GPT-4o",
            "model_name": "gpt-4o",
            "api_key": "sk-openai-secret-key-1111",
        },
        {
            "id": "mod-anthropic",
            "provider": "anthropic",
            "display_name": "Claude 3.5 Sonnet",
            "model_name": "claude-3-5-sonnet-20241022",
            "api_key": "sk-ant-secret-key-2222",
        },
        {
            "id": "mod-gemini",
            "provider": "gemini",
            "display_name": "Gemini 1.5 Flash",
            "model_name": "gemini-1.5-flash",
            "api_key": "AIzaSySecretKey3333",
        },
        {
            "id": "mod-azure",
            "provider": "azure",
            "display_name": "Azure GPT-4o",
            "model_name": "gpt-4o",
            "api_key": "az-secret-key-4444",
            "base_url": "https://my-res.openai.azure.com",
            "deployment_name": "gpt4o-dep",
        },
        {
            "id": "mod-custom",
            "provider": "custom",
            "display_name": "LM Studio Local",
            "model_name": "local-llama3",
            "base_url": "http://localhost:1234/v1",
        },
    ]

    for p in providers_to_add:
        r = client.post("/api/models", json=p)
        assert r.status_code == 200, r.text
        data = r.json()
        if p.get("api_key"):
            assert data["has_key"] is True
            assert p["api_key"] not in json.dumps(data)

    # 2. Set independent defaults: OpenAI for Chat, Anthropic for Architecture
    r_chat_def = client.post("/api/models/mod-openai/set-default", json={"target": "chat"})
    assert r_chat_def.status_code == 200
    assert r_chat_def.json()["is_default_chat"] is True

    r_arch_def = client.post("/api/models/mod-anthropic/set-default", json={"target": "architecture"})
    assert r_arch_def.status_code == 200
    assert r_arch_def.json()["is_default_architecture"] is True

    # 3. GET /api/models lists all 6 (1 migrated ollama + 5 added) without plaintext keys
    r_list = client.get("/api/models")
    assert r_list.status_code == 200
    raw_list_text = r_list.text
    assert "sk-openai-secret-key-1111" not in raw_list_text
    assert "sk-ant-secret-key-2222" not in raw_list_text
    assert "AIzaSySecretKey3333" not in raw_list_text
    assert "az-secret-key-4444" not in raw_list_text

    listed = {m["id"]: m for m in r_list.json()["models"]}
    assert listed["mod-openai"]["is_default_chat"] is True
    assert listed["mod-openai"]["is_default_architecture"] is False
    assert listed["mod-anthropic"]["is_default_architecture"] is True
    assert listed["mod-anthropic"]["is_default_chat"] is False

    # 4. Delete custom model
    r_del = client.delete("/api/models/mod-custom")
    assert r_del.status_code == 200
    assert client.delete("/api/models/nonexistent-id").status_code == 404


def test_validate_endpoint_all_providers(client, isolated_env):
    """Verify POST /api/models/{id}/validate returns valid status and models cleanly."""
    client.post("/api/models", json={
        "id": "mod-oai-val",
        "provider": "openai",
        "display_name": "OpenAI Test",
        "model_name": "gpt-4o",
        "api_key": "sk-test-valid-1234",
    })
    client.post("/api/models", json={
        "id": "mod-oai-nokey",
        "provider": "openai",
        "display_name": "OpenAI NoKey",
        "model_name": "gpt-4o",
    })

    # Missing key returns valid=False with clean error
    r_nokey = client.post("/api/models/mod-oai-nokey/validate")
    assert r_nokey.status_code == 200
    assert r_nokey.json()["valid"] is False
    assert "Missing API key" in r_nokey.json()["error"]

    # Valid provider mocked
    with patch("backend.llm_providers.OpenAIProvider.validate_connection", return_value={"valid": True, "models": ["gpt-4o", "gpt-4o-mini"], "error": None}):
        r_ok = client.post("/api/models/mod-oai-val/validate")
        assert r_ok.status_code == 200
        assert r_ok.json()["valid"] is True
        assert "gpt-4o" in r_ok.json()["models"]


def test_llm_chat_routing_and_error_handling(client, isolated_env):
    """Verify POST /api/llm/chat routes to the chosen provider & injects symbol context."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    client.post("/api/models", json={
        "id": "mod-claude-chat",
        "provider": "anthropic",
        "display_name": "Claude Sonnet",
        "model_name": "claude-3-5-sonnet-20241022",
        "api_key": "sk-ant-chat-9999",
    })

    with patch("backend.llm_providers.AnthropicProvider.chat", return_value="Animal is the base class in sample_project.") as mock_chat:
        res = client.post("/api/llm/chat", json={
            "message": "Explain Animal",
            "context_symbol_id": "sample_project.Animal",
            "model_id": "mod-claude-chat",
        })
        assert res.status_code == 200
        assert res.json()["reply"] == "Animal is the base class in sample_project."
        mock_chat.assert_called_once()
        _, kwargs = mock_chat.call_args
        assert "Animal" in kwargs["system_prompt"]


def test_advanced_architecture_provider_agnostic_safety_net(client, isolated_env, caplog):
    """Verify Phase 19 validation safety net holds when running against a non-Ollama cloud provider."""
    analyze_res = client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})
    assert analyze_res.status_code == 200
    real_ids = {n["id"] for n in analyze_res.json()["nodes"]}

    client.post("/api/models", json={
        "id": "mod-gemini-arch",
        "provider": "gemini",
        "display_name": "Gemini Pro",
        "model_name": "gemini-1.5-pro",
        "api_key": "AIzaSyGeminiKey8888",
    })

    # Simulate Gemini inventing a fake symbol and omitting sample_project.Animal
    hallucinated_response = json.dumps({
        "components": [
            {
                "component_id": "comp_1",
                "name": "Derived Animals",
                "member_symbol_ids": [
                    "sample_project.Dog",
                    "sample_project.Cat",
                    "sample_project.InventedDragon",  # Invented!
                ],
                "role": "Domain Models",
                "rationale": "Concrete animal subclasses",
            }
        ],
        "unclustered_symbol_ids": [],
        "narrative": "Cloud LLM architectural summary.",
    })

    with caplog.at_level(logging.WARNING):
        with patch("backend.llm_providers.GeminiProvider.chat", return_value=hallucinated_response) as mock_gemini:
            res = client.post("/api/architecture/advanced", json={
                "force_refresh": True,
                "model_id": "mod-gemini-arch",
            })
            assert res.status_code == 200, res.text
            mock_gemini.assert_called_once()

    validated = AdvancedArchitectureResponse(**res.json())
    # Invented ID MUST be dropped and logged
    assert "sample_project.InventedDragon" not in validated.components[0].member_symbol_ids
    assert "Dropping invented symbol ID: 'sample_project.InventedDragon'" in caplog.text
    # Omitted real symbol MUST appear in unclustered_symbol_ids
    assert "sample_project.Animal" in validated.unclustered_symbol_ids
    # Total accounting == 100%
    accounted = set(validated.components[0].member_symbol_ids).union(set(validated.unclustered_symbol_ids))
    assert accounted == real_ids


def test_backward_compat_qwen_status(client, isolated_env):
    """Legacy /api/qwen/status still returns valid status shape."""
    res = client.get("/api/qwen/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("connected", "disconnected")
    assert "model" in data

