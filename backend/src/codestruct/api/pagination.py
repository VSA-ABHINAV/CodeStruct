"""Opaque, integrity-checked graph cursors and deterministic slices."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast

_CURSOR_CONTEXT = b"codestruct-v1-local-cursor"


def encode_cursor(graph_id: str, offset: int, filters: Mapping[str, object]) -> str:
    body = json.dumps(
        {"g": graph_id, "o": offset, "f": filters},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    signature = hashlib.sha256(_CURSOR_CONTEXT + body).hexdigest()[:24].encode()
    return base64.urlsafe_b64encode(body + b"." + signature).decode().rstrip("=")


def decode_cursor(value: str, graph_id: str, filters: Mapping[str, object]) -> int:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        body, signature = raw.rsplit(b".", 1)
        if (
            signature
            != hashlib.sha256(_CURSOR_CONTEXT + body).hexdigest()[:24].encode()
        ):
            raise ValueError
        data = json.loads(body)
        if data != {"g": graph_id, "o": data.get("o"), "f": filters}:
            raise ValueError
        offset = data["o"]
        if not isinstance(offset, int) or offset < 0:
            raise ValueError
        return offset
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid graph cursor") from error


def slice_graph(
    graph: dict[str, object],
    *,
    limit: int,
    cursor: str | None,
    node_kind: str | None,
    edge_kind: str | None,
    resolution_status: str | None,
) -> dict[str, object]:
    filters: dict[str, object] = {
        "node_kind": node_kind,
        "edge_kind": edge_kind,
        "resolution_status": resolution_status,
        "limit": limit,
    }
    graph_nodes = cast(list[dict[str, Any]], graph["nodes"])
    graph_edges = cast(list[dict[str, Any]], graph["edges"])
    graph_evidence = cast(list[dict[str, Any]], graph["evidence"])
    metadata = cast(dict[str, Any], graph["metadata"])
    nodes = [
        item for item in graph_nodes if node_kind is None or item["kind"] == node_kind
    ]
    edges = [
        item
        for item in graph_edges
        if (edge_kind is None or item["kind"] == edge_kind)
        and (
            resolution_status is None or item["resolution_status"] == resolution_status
        )
    ]
    graph_id = str(metadata["graph_id"])
    offset = decode_cursor(cursor, graph_id, filters) if cursor else 0
    page_nodes = nodes[offset : offset + limit]
    included = {item["id"] for item in page_nodes}
    page_edges = [
        item
        for item in edges
        if item["source_id"] in included or item.get("target_id") in included
    ]
    endpoint_ids = {
        value
        for edge in page_edges
        for value in (edge["source_id"], edge.get("target_id"))
        if value
    }
    by_id = {item["id"]: item for item in graph_nodes}
    page_nodes = sorted(
        {
            item["id"]: item
            for item in [
                *page_nodes,
                *(by_id[value] for value in endpoint_ids if value in by_id),
            ]
        }.values(),
        key=lambda item: item["id"],
    )
    next_offset = offset + limit
    result = dict(graph)
    result["nodes"] = page_nodes
    result["edges"] = page_edges
    result["evidence"] = [
        item
        for item in graph_evidence
        if item["evidence_id"]
        in {evidence for edge in page_edges for evidence in edge["evidence_ids"]}
    ]
    result["page"] = {
        "returned_nodes": len(page_nodes),
        "total_nodes": len(nodes),
        "returned_edges": len(page_edges),
        "total_edges": len(edges),
        "next_cursor": encode_cursor(graph_id, next_offset, filters)
        if next_offset < len(nodes)
        else None,
        "partial_load": offset > 0 or next_offset < len(nodes),
    }
    return result
