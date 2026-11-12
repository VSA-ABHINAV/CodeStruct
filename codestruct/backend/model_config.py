"""Encrypted Multi-LLM Model Configuration & Persistence (AppData/models.json).

Uses Fernet symmetric encryption with PBKDF2-HMAC-SHA256 (100,000 iterations)
key derivation bound to the host machine's unique cryptographic identifier.
API keys are never written to disk, logs, cache, or API responses in plaintext.
"""

import base64
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel, Field

from backend.config import get_app_data_dir, load_config

logger = logging.getLogger("codestruct.model_config")

ProviderType = Literal["ollama", "openai", "anthropic", "gemini", "azure", "custom"]


def get_machine_guid() -> str:
    """Retrieve a stable host machine identifier across Windows, Linux, and macOS."""
    if sys.platform == "win32":
        try:
            import winreg

            key_path = r"SOFTWARE\Microsoft\Cryptography"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                val, _ = winreg.QueryValueEx(key, "MachineGuid")
                if val and str(val).strip():
                    return str(val).strip()
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            p = Path(candidate)
            if p.is_file():
                text = p.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    return text
    elif sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                text=True,
                timeout=2.0,
            )
            for line in out.splitlines():
                if "IOPlatformUUID" in line and "=" in line:
                    return line.split("=")[-1].strip().strip('"')
        except Exception:
            pass

    # Fallback deterministic identifier
    return f"{platform.node()}-{uuid.getnode()}"


def _derive_fernet_key(machine_id: str, salt: bytes) -> bytes:
    """Derive a URL-safe base64 32-byte Fernet key using PBKDF2-HMAC-SHA256 (100k iterations)."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = kdf.derive(machine_id.encode("utf-8"))
    return base64.urlsafe_b64encode(key)


def encrypt_api_key(plaintext_key: str, machine_id: Optional[str] = None) -> str:
    """Encrypt an API key using Fernet with a per-secret random 16-byte salt."""
    if not plaintext_key:
        return ""
    mid = machine_id or get_machine_guid()
    salt = os.urandom(16)
    fernet_key = _derive_fernet_key(mid, salt)
    token = Fernet(fernet_key).encrypt(plaintext_key.encode("utf-8")).decode("ascii")
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    return f"enc:v1:{salt_b64}:{token}"


def decrypt_api_key(encrypted_blob: Optional[str], machine_id: Optional[str] = None) -> Optional[str]:
    """Decrypt a stored Fernet-encrypted API key blob. Never accepts plaintext."""
    if not encrypted_blob:
        return None
    if not encrypted_blob.startswith("enc:v1:"):
        logger.warning("[ModelConfig] Encountered non-encrypted key format; refusing plaintext usage.")
        return None
    try:
        _, _, salt_b64, token = encrypted_blob.split(":", 3)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        mid = machine_id or get_machine_guid()
        fernet_key = _derive_fernet_key(mid, salt)
        decrypted = Fernet(fernet_key).decrypt(token.encode("ascii")).decode("utf-8")
        return decrypted
    except (ValueError, InvalidToken, Exception) as e:
        logger.error(f"[ModelConfig] Failed to decrypt stored API key: {type(e).__name__}")
        return None


def mask_api_key(plaintext_or_none: Optional[str]) -> str:
    """Return safely masked representation of an API key (e.g. sk-****abcd)."""
    if not plaintext_or_none:
        return ""
    s = plaintext_or_none.strip()
    if len(s) <= 6:
        return "****"
    if len(s) <= 10:
        return f"{s[:2]}****{s[-2:]}"
    return f"{s[:3]}****{s[-4:]}"


class ModelConfigRecord(BaseModel):
    """Internal persisted model configuration record (keys always encrypted on disk)."""
    id: str
    provider: ProviderType
    display_name: str
    model_name: str
    api_key_encrypted: Optional[str] = None
    masked_key: str = ""
    base_url: Optional[str] = None
    deployment_name: Optional[str] = None
    api_version: Optional[str] = None
    enabled: bool = True
    is_default_chat: bool = False
    is_default_architecture: bool = False


class ModelConfigPublicView(BaseModel):
    """Safe API view returned to frontend (NEVER exposes raw or encrypted keys)."""
    id: str
    provider: ProviderType
    display_name: str
    model_name: str
    has_key: bool = False
    masked_key: str = ""
    base_url: Optional[str] = None
    deployment_name: Optional[str] = None
    api_version: Optional[str] = None
    enabled: bool = True
    is_default_chat: bool = False
    is_default_architecture: bool = False


def get_models_file_path() -> Path:
    """Return path to %APPDATA%\\CodeStruct\\models.json."""
    return get_app_data_dir() / "models.json"


class ModelRegistry:
    """CRUD registry and encrypted persistence manager for configured LLM models."""

    def __init__(self, models_path: Optional[Path] = None, machine_id: Optional[str] = None):
        self._path_override = models_path
        self._machine_id = machine_id

    @property
    def file_path(self) -> Path:
        return self._path_override if self._path_override is not None else get_models_file_path()

    def _migrate_from_legacy_config(self) -> List[ModelConfigRecord]:
        """Auto-migrate existing Ollama configuration if models.json does not yet exist."""
        cfg = load_config()
        ollama_host = cfg.get("ollama_host", "http://localhost:11434")
        ollama_model = cfg.get("ollama_model", "qwen2.5-coder:3b")
        default_ollama = ModelConfigRecord(
            id="ollama-default",
            provider="ollama",
            display_name=f"Ollama ({ollama_model})",
            model_name=ollama_model,
            api_key_encrypted=None,
            masked_key="",
            base_url=ollama_host,
            enabled=True,
            is_default_chat=True,
            is_default_architecture=True,
        )
        return [default_ollama]

    def _load_records(self) -> List[ModelConfigRecord]:
        path = self.file_path
        if not path.exists():
            records = self._migrate_from_legacy_config()
            self._save_records(records)
            return records
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            items = raw.get("models", []) if isinstance(raw, dict) else []
            records = [ModelConfigRecord(**item) for item in items]
            if not records:
                records = self._migrate_from_legacy_config()
                self._save_records(records)
            return records
        except Exception as e:
            logger.error(f"[ModelRegistry] Error reading models.json: {e}")
            return self._migrate_from_legacy_config()

    def _save_records(self, records: List[ModelConfigRecord]) -> None:
        path = self.file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "models": [r.model_dump() for r in records],
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def to_public(rec: ModelConfigRecord) -> ModelConfigPublicView:
        return ModelConfigPublicView(
            id=rec.id,
            provider=rec.provider,
            display_name=rec.display_name,
            model_name=rec.model_name,
            has_key=bool(rec.api_key_encrypted),
            masked_key=rec.masked_key or ("****" if rec.api_key_encrypted else ""),
            base_url=rec.base_url,
            deployment_name=rec.deployment_name,
            api_version=rec.api_version,
            enabled=rec.enabled,
            is_default_chat=rec.is_default_chat,
            is_default_architecture=rec.is_default_architecture,
        )

    def list_models(self, enabled_only: bool = False) -> List[ModelConfigPublicView]:
        records = self._load_records()
        if enabled_only:
            records = [r for r in records if r.enabled]
        return [self.to_public(r) for r in records]

    def get_record(self, model_id: str) -> Optional[ModelConfigRecord]:
        for r in self._load_records():
            if r.id == model_id:
                return r
        return None

    def get_decrypted_api_key(self, model_id: str) -> Optional[str]:
        rec = self.get_record(model_id)
        if not rec or not rec.api_key_encrypted:
            return None
        return decrypt_api_key(rec.api_key_encrypted, machine_id=self._machine_id)

    def upsert_model(
        self,
        *,
        provider: ProviderType,
        display_name: str,
        model_name: str,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        deployment_name: Optional[str] = None,
        api_version: Optional[str] = None,
        enabled: bool = True,
        is_default_chat: bool = False,
        is_default_architecture: bool = False,
    ) -> ModelConfigPublicView:
        records = self._load_records()
        target_id = (model_id or "").strip() or f"{provider}-{uuid.uuid4().hex[:8]}"

        existing_idx = next((i for i, r in enumerate(records) if r.id == target_id), None)
        existing_enc_key = records[existing_idx].api_key_encrypted if existing_idx is not None else None
        existing_masked = records[existing_idx].masked_key if existing_idx is not None else ""

        # Handle encryption: if a non-empty api_key is provided, encrypt it; otherwise keep existing
        if api_key is not None and api_key.strip():
            clean_key = api_key.strip()
            enc_key = encrypt_api_key(clean_key, machine_id=self._machine_id)
            masked = mask_api_key(clean_key)
        else:
            enc_key = existing_enc_key
            masked = existing_masked

        # Enforce unique defaults if requested
        if is_default_chat:
            for r in records:
                r.is_default_chat = False
        if is_default_architecture:
            for r in records:
                r.is_default_architecture = False

        new_rec = ModelConfigRecord(
            id=target_id,
            provider=provider,
            display_name=display_name.strip() or model_name.strip(),
            model_name=model_name.strip(),
            api_key_encrypted=enc_key,
            masked_key=masked,
            base_url=base_url.strip() if base_url and base_url.strip() else None,
            deployment_name=deployment_name.strip() if deployment_name and deployment_name.strip() else None,
            api_version=api_version.strip() if api_version and api_version.strip() else None,
            enabled=enabled,
            is_default_chat=is_default_chat,
            is_default_architecture=is_default_architecture,
        )

        if existing_idx is not None:
            records[existing_idx] = new_rec
        else:
            records.append(new_rec)

        self._save_records(records)
        return self.to_public(new_rec)

    def delete_model(self, model_id: str) -> bool:
        records = self._load_records()
        filtered = [r for r in records if r.id != model_id]
        if len(filtered) == len(records):
            return False
        # Re-assign defaults if deleted model held them and others exist
        if filtered:
            if not any(r.is_default_chat for r in filtered):
                filtered[0].is_default_chat = True
            if not any(r.is_default_architecture for r in filtered):
                filtered[0].is_default_architecture = True
        self._save_records(filtered)
        return True

    def set_default(self, model_id: str, target: Literal["chat", "architecture", "both"]) -> Optional[ModelConfigPublicView]:
        records = self._load_records()
        found = None
        for r in records:
            if r.id == model_id:
                found = r
                break
        if not found:
            return None

        if target in ("chat", "both"):
            for r in records:
                r.is_default_chat = (r.id == model_id)
        if target in ("architecture", "both"):
            for r in records:
                r.is_default_architecture = (r.id == model_id)

        self._save_records(records)
        return self.to_public(found)

    def resolve_model(
        self,
        model_id: Optional[str] = None,
        feature: Literal["chat", "architecture"] = "chat",
    ) -> Optional[ModelConfigRecord]:
        records = [r for r in self._load_records() if r.enabled]
        if not records:
            return None
        if model_id:
            for r in records:
                if r.id == model_id:
                    return r
        if feature == "chat":
            for r in records:
                if r.is_default_chat:
                    return r
        else:
            for r in records:
                if r.is_default_architecture:
                    return r
        return records[0]

