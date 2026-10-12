"""Bounded retrieval layer for grounding architectural explanations in source and graph evidence.

Assembles bounded authorized source code snippets, canonical graph relationships,
runtime profiling observations, architecture metrics, and evidence identifiers.
Enforces strict project-root containment and sensitive/secret file exclusions.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Sensitive file and token patterns that must NEVER be retrieved or included
SECRET_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"^id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$", re.IGNORECASE),
    re.compile(
        r"(secret|credential|password|token|api_key|private_key)", re.IGNORECASE
    ),
    re.compile(r"^\.(htpasswd|netrc)$", re.IGNORECASE),
)

SECRET_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pem",
        ".key",
        ".pfx",
        ".p12",
        ".pkcs12",
        ".crt",
        ".cer",
        ".der",
    }
)

BINARY_OR_UNSAFE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pyc",
        ".pyd",
        ".so",
        ".dll",
        ".exe",
        ".bin",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
    }
)

SENSITIVE_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        ".ssh",
        ".gnupg",
        ".aws",
        ".azure",
        ".kube",
    }
)


def is_secret_or_sensitive(file_path: str | Path) -> bool:
    """Return True if the given path matches sensitive, secret, or binary file criteria."""
    p = Path(file_path)
    # Check directory parts
    for part in p.parts[:-1]:
        part_clean = part.strip().lower()
        if part_clean in SENSITIVE_DIR_NAMES:
            return True
        for pat in SECRET_NAME_PATTERNS:
            if pat.search(part_clean):
                return True

    filename = p.name.strip()
    suffix = p.suffix.lower()

    if suffix in SECRET_EXTENSIONS or suffix in BINARY_OR_UNSAFE_EXTENSIONS:
        return True

    for pattern in SECRET_NAME_PATTERNS:
        if pattern.search(filename):
            return True

    return False


def is_safe_path_contained(
    candidate_path: str | Path,
    project_root: str | Path,
) -> Path | None:
    """Safely verify that candidate_path resolves strictly within project_root.

    Rejects directory traversal (e.g. '../'), absolute paths outside root,
    symlinks or reparse points escaping the root, and non-existent files.
    Returns the resolved Path if safe and existent, otherwise None.
    """
    if not candidate_path or not project_root:
        return None

    cand_str = str(candidate_path).strip()
    if "\x00" in cand_str:
        return None

    try:
        root_path = Path(project_root).resolve(strict=True)
    except (OSError, RuntimeError):
        return None

    if not root_path.is_dir():
        return None

    # Handle candidate path
    p = Path(cand_str)
    if p.is_absolute():
        target = p
    else:
        target = root_path / p

    try:
        resolved_target = target.resolve(strict=True)
    except (OSError, RuntimeError):
        return None

    # Containment check via relative_to
    try:
        resolved_target.relative_to(root_path)
    except ValueError:
        return None

    # Additional case-normalization check for Windows
    if os.name == "nt":
        norm_root = os.path.normcase(str(root_path))
        norm_target = os.path.normcase(str(resolved_target))
        if not norm_target.startswith(norm_root):
            return None

    if not resolved_target.is_file():
        return None

    return resolved_target


@dataclass(frozen=True, slots=True)
class SourceSnippet:
    """Bounded source code snippet retrieved for an architectural entity."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    byte_count: int
    line_count: int
    is_truncated: bool = False


@dataclass(frozen=True, slots=True)
class CanonicalEvidenceItem:
    """A canonical observation or fact from static analysis or runtime tracing."""

    id: str
    origin: str
    observation_kind: str
    location: dict[str, Any] | str | None = None
    excerpt: str | None = None
    explanation: str | None = None
    observed_text_hash: str | None = None
    expression: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievedEvidenceContext:
    """Full architectural context assembled by the bounded retrieval layer."""

    node_id: str
    name: str
    qualified_name: str
    kind: str
    file_path: str | None = None
    line: int | None = None
    end_line: int | None = None
    docstring: str | None = None
    source_snippet: SourceSnippet | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    importers: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    inherits: list[str] = field(default_factory=list)
    inherited_by: list[str] = field(default_factory=list)
    runtime_stats: dict[str, Any] = field(default_factory=dict)
    evidence_items: list[CanonicalEvidenceItem] = field(default_factory=list)
    canonical_evidence_ids: set[str] = field(default_factory=set)


def retrieve_source_snippet(
    project_root: str | Path | None,
    file_path: str | None,
    line: int | None = None,
    end_line: int | None = None,
    max_lines: int = 60,
    max_bytes: int = 4096,
) -> SourceSnippet | None:
    """Retrieve an authorized, bounded source code snippet surrounding the entity line span.

    Enforces project-root containment, sensitive/secret file exclusions, line limits,
    and byte caps.
    """
    if project_root is None or file_path is None:
        return None

    if is_secret_or_sensitive(file_path):
        return None

    resolved_path = is_safe_path_contained(file_path, project_root)
    if resolved_path is None:
        return None

    try:
        file_size = resolved_path.stat().st_size
    except OSError:
        return None

    # Safety cap: skip files exceeding 2MB
    if file_size > 2 * 1024 * 1024:
        return None

    try:
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, UnicodeError):
        return None

    if not lines:
        return SourceSnippet(
            file_path=str(file_path),
            start_line=1,
            end_line=1,
            content="",
            byte_count=0,
            line_count=0,
            is_truncated=False,
        )

    total_lines = len(lines)
    if line is None or line < 1:
        start_line_num = 1
        end_line_num = min(total_lines, max_lines)
    else:
        start_line_num = min(line, total_lines)
        if end_line is None or end_line < start_line_num:
            end_line_num = start_line_num
        else:
            end_line_num = min(end_line, total_lines)

        # Context window: +/- 3 lines around the entity span
        ctx_start = max(1, start_line_num - 3)
        ctx_end = min(total_lines, end_line_num + 3)

        # Enforce max_lines bound
        if (ctx_end - ctx_start + 1) > max_lines:
            ctx_end = ctx_start + max_lines - 1

        start_line_num = ctx_start
        end_line_num = ctx_end

    selected_lines = lines[start_line_num - 1 : end_line_num]
    raw_content = "".join(selected_lines)
    encoded = raw_content.encode("utf-8")
    is_truncated = False

    if len(encoded) > max_bytes:
        is_truncated = True
        truncated_bytes = encoded[:max_bytes]
        content = (
            truncated_bytes.decode("utf-8", errors="ignore")
            + "\n# [TRUNCATED: byte limit reached]"
        )
    else:
        content = raw_content

    return SourceSnippet(
        file_path=str(file_path),
        start_line=start_line_num,
        end_line=end_line_num,
        content=content,
        byte_count=len(content.encode("utf-8")),
        line_count=len(selected_lines),
        is_truncated=is_truncated,
    )


def retrieve_evidence_context(
    graph: dict[str, Any],
    node_id: str,
    project_root: str | Path | None = None,
    max_evidence_items: int = 25,
) -> RetrievedEvidenceContext:
    """Assemble all authorized source, graph, metric, runtime, and evidence facts for a node."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    target_node = None
    node_name_map: dict[str, str] = {}
    for node in nodes:
        nid = node.get("id")
        qname = node.get("qualified_name") or node.get("name") or nid
        if nid:
            node_name_map[nid] = qname
        if nid == node_id:
            target_node = node

    if target_node is None:
        raise KeyError(f"Node '{node_id}' not found in graph")

    name = target_node.get("name", "")
    qualified_name = target_node.get("qualified_name", name)
    kind = target_node.get("kind", "unknown")

    # Canonical location resolution
    location = target_node.get("location") or target_node.get("source_location") or {}
    file_path = (
        location.get("path")
        or location.get("file_path")
        or target_node.get("file_path")
    )
    span = (
        location.get("span")
        if isinstance(location, dict) and isinstance(location.get("span"), dict)
        else {}
    )
    start_point = (
        span.get("start")
        if isinstance(span, dict) and isinstance(span.get("start"), dict)
        else {}
    )
    end_point = (
        span.get("end")
        if isinstance(span, dict) and isinstance(span.get("end"), dict)
        else {}
    )
    line = (
        location.get("start_line")
        or location.get("line")
        or (span.get("start_line") if isinstance(span, dict) else None)
        or (start_point.get("line") if isinstance(start_point, dict) else None)
        or (span.get("line") if isinstance(span, dict) else None)
        or target_node.get("line")
    )
    end_line = (
        location.get("end_line")
        or (span.get("end_line") if isinstance(span, dict) else None)
        or (end_point.get("line") if isinstance(end_point, dict) else None)
        or target_node.get("end_line")
    )

    # Retrieve bounded source snippet (safely contained)
    source_snippet = retrieve_source_snippet(
        project_root=project_root,
        file_path=file_path,
        line=line,
        end_line=end_line,
    )

    # Extract node attributes & metrics
    attributes_raw = target_node.get("attributes", {})
    attributes: dict[str, Any] = {}
    if isinstance(attributes_raw, dict):
        attributes = dict(attributes_raw)
    elif isinstance(attributes_raw, list):
        for item in attributes_raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                attributes[str(item[0])] = item[1]
            elif isinstance(item, dict) and "key" in item:
                attributes[str(item["key"])] = item.get("value")

    metrics: dict[str, Any] = {}
    int_keys: dict[str, str] = {
        "fan_in": "fan_in",
        "fan_out": "fan_out",
        "component": "component_id",
        "component_id": "component_id",
        "community": "community_id",
        "community_id": "community_id",
        "ca": "ca",
        "ce": "ce",
    }
    float_keys: dict[str, str] = {
        "instability": "instability",
        "degree_centrality": "degree_centrality",
        "centrality": "degree_centrality",
        "betweenness_centrality": "betweenness_centrality",
        "module_instability": "module_instability",
        "cohesion": "cohesion",
        "relational_density": "relational_density",
    }
    for raw_k, val in attributes.items():
        if raw_k in int_keys:
            try:
                metrics[int_keys[raw_k]] = int(val)
            except (ValueError, TypeError):
                pass
        elif raw_k in float_keys:
            try:
                metrics[float_keys[raw_k]] = float(val)
            except (ValueError, TypeError):
                pass
        elif raw_k == "in_cycle":
            metrics["in_cycle"] = val is True or str(val).lower() == "true"

    # Runtime statistics
    runtime_stats: dict[str, Any] = {}
    runtime_keys = (
        "runtime_calls",
        "runtime_invocations",
        "runtime_exceptions",
        "runtime_duration_ms",
        "runtime_calls_out",
    )
    for rk in runtime_keys:
        if rk in attributes:
            runtime_stats[rk] = attributes[rk]

    docstring = attributes.get("docstring")

    # Group incoming and outgoing relationships (strictly resolved dependencies only)
    callers: list[str] = []
    callees: list[str] = []
    importers: list[str] = []
    imports: list[str] = []
    inherits: list[str] = []
    inherited_by: list[str] = []
    incident_evidence_ids: set[str] = set()

    for edge in edges:
        source_id = edge.get("source_id") or edge.get("source")
        target_id = edge.get("target_id") or edge.get("target")
        edge_kind = str(edge.get("kind") or edge.get("type") or "").upper()
        res_status = str(
            edge.get("resolution_status")
            or (
                edge.get("resolution", {}).get("status")
                if isinstance(edge.get("resolution"), dict)
                else ""
            )
            or ""
        ).lower()

        # Collect evidence from defining containment
        if (source_id == target_node.get("parent_id") and target_id == node_id) or (
            target_id == node_id and edge_kind in ("DEFINES", "DEFINE")
        ):
            for evid in edge.get("evidence_ids", []):
                incident_evidence_ids.add(str(evid))

        # Only RESOLVED dependencies count towards architectural dependency network
        if res_status in (
            "unresolved",
            "ambiguous",
            "syntactic_only",
            "not_applicable",
        ):
            continue

        if source_id == node_id and target_id is not None and target_id != node_id:
            dest_name = node_name_map.get(target_id, str(target_id))
            if edge_kind in ("CALL", "CALLS"):
                callees.append(dest_name)
                for evid in edge.get("evidence_ids", []):
                    incident_evidence_ids.add(str(evid))
            elif edge_kind in ("IMPORT", "IMPORTS"):
                imports.append(dest_name)
                for evid in edge.get("evidence_ids", []):
                    incident_evidence_ids.add(str(evid))
            elif edge_kind in ("INHERIT", "INHERITS"):
                inherits.append(dest_name)
                for evid in edge.get("evidence_ids", []):
                    incident_evidence_ids.add(str(evid))

        if target_id == node_id and source_id is not None and source_id != node_id:
            src_name = node_name_map.get(source_id, str(source_id))
            if edge_kind in ("CALL", "CALLS"):
                callers.append(src_name)
                for evid in edge.get("evidence_ids", []):
                    incident_evidence_ids.add(str(evid))
            elif edge_kind in ("IMPORT", "IMPORTS"):
                importers.append(src_name)
                for evid in edge.get("evidence_ids", []):
                    incident_evidence_ids.add(str(evid))
            elif edge_kind in ("INHERIT", "INHERITS"):
                inherited_by.append(src_name)
                for evid in edge.get("evidence_ids", []):
                    incident_evidence_ids.add(str(evid))

    # Index graph evidence items
    evidence_index: dict[str, dict[str, Any]] = {}
    for ev in graph.get("evidence", []):
        if isinstance(ev, dict):
            eid = str(ev.get("evidence_id") or ev.get("id") or "")
            if eid:
                evidence_index[eid] = ev

    # Also collect evidence attached directly to target node
    for ev_id in target_node.get("evidence_ids", []):
        incident_evidence_ids.add(str(ev_id))

    collected_evidence_items: list[CanonicalEvidenceItem] = []
    canonical_evidence_ids: set[str] = set()

    # Bounded collection up to max_evidence_items
    for eid in sorted(incident_evidence_ids)[:max_evidence_items]:
        canonical_evidence_ids.add(eid)
        ev_dict = evidence_index.get(eid)
        if ev_dict:
            collected_evidence_items.append(
                CanonicalEvidenceItem(
                    id=eid,
                    origin=str(ev_dict.get("origin", "STATIC_AST")),
                    observation_kind=str(
                        ev_dict.get("observation_kind", "declaration")
                    ),
                    location=ev_dict.get("location"),
                    excerpt=ev_dict.get("excerpt"),
                    explanation=ev_dict.get("explanation"),
                    observed_text_hash=ev_dict.get("observed_text_hash"),
                    expression=ev_dict.get("expression"),
                )
            )
        else:
            collected_evidence_items.append(
                CanonicalEvidenceItem(
                    id=eid,
                    origin="STATIC_AST",
                    observation_kind="graph_relationship",
                )
            )

    return RetrievedEvidenceContext(
        node_id=node_id,
        name=name,
        qualified_name=qualified_name,
        kind=kind,
        file_path=file_path,
        line=line,
        end_line=end_line,
        docstring=docstring,
        source_snippet=source_snippet,
        metrics=metrics,
        callers=sorted(set(callers)),
        callees=sorted(set(callees)),
        importers=sorted(set(importers)),
        imports=sorted(set(imports)),
        inherits=sorted(set(inherits)),
        inherited_by=sorted(set(inherited_by)),
        runtime_stats=runtime_stats,
        evidence_items=collected_evidence_items,
        canonical_evidence_ids=canonical_evidence_ids,
    )
