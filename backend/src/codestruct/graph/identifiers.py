"""Deterministic graph identities and privacy-preserving fingerprints."""

from __future__ import annotations

import base64
import hashlib
import json
import unicodedata

from .enums import EvidenceOrigin, NodeKind, RelationshipKind, ResolutionStatus
from .model import SourceSpan


class GraphIdentityCollisionError(RuntimeError):
    """Two unequal semantic records produced the same canonical identifier."""


def _normalized(value: object) -> str:
    return unicodedata.normalize("NFC", str(value))


def stable_digest(prefix: str, *parts: object, length: int = 26) -> str:
    encoded = "\x1f".join(_normalized(part) for part in parts).encode("utf-8")
    digest = base64.b32encode(hashlib.sha256(encoded).digest()).decode("ascii")
    return f"{prefix}_{digest.rstrip('=').lower()[:length]}"


def content_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def node_id(kind: NodeKind, *semantic_key: object) -> str:
    return stable_digest("n", kind.value, *semantic_key)


def edge_id(
    kind: RelationshipKind,
    source_id: str,
    target_key: str,
    status: ResolutionStatus,
    discriminator: str,
) -> str:
    return stable_digest(
        "e", kind.value, source_id, target_key, status.value, discriminator
    )


def evidence_id(
    origin: EvidenceOrigin,
    source_unit_id: str,
    span: SourceSpan,
    observation_kind: str,
    observed_hash: str | None,
) -> str:
    return stable_digest(
        "v",
        origin.value,
        source_unit_id,
        span.start_line,
        span.start_column,
        span.end_line or "",
        span.end_column or "",
        observation_kind,
        observed_hash or "",
    )


def diagnostic_id(
    code: str,
    phase: str,
    source_unit_id: str = "",
    span: SourceSpan | None = None,
    discriminator: str = "",
) -> str:
    return stable_digest(
        "d",
        code,
        phase,
        source_unit_id,
        span.start_line if span else "",
        span.start_column if span else "",
        discriminator,
    )


def normalized_text_hash(expression: str | None) -> str | None:
    if expression is None:
        return None
    normalized = " ".join(expression.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
