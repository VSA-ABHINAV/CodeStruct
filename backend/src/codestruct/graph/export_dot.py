"""Graphviz DOT export generation for CodeStruct architecture graphs."""

from __future__ import annotations

import re
from typing import Any

# Color and styling palette matching CodeStruct's visual design tokens
NODE_KIND_STYLES = {
    "class": {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": "#eff6ff",
        "color": "#2563eb",
        "fontcolor": "#1e3a8a",
    },
    "function": {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": "#fffbeb",
        "color": "#d97706",
        "fontcolor": "#78350f",
    },
    "async_function": {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": "#fffbeb",
        "color": "#d97706",
        "fontcolor": "#78350f",
    },
    "method": {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": "#f5f3ff",
        "color": "#7c3aed",
        "fontcolor": "#4c1d95",
    },
    "async_method": {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": "#f5f3ff",
        "color": "#7c3aed",
        "fontcolor": "#4c1d95",
    },
    "module": {
        "shape": "component",
        "style": "filled",
        "fillcolor": "#f0fdf4",
        "color": "#16a34a",
        "fontcolor": "#14532d",
    },
    "file": {
        "shape": "note",
        "style": "filled",
        "fillcolor": "#f8fafc",
        "color": "#64748b",
        "fontcolor": "#334155",
    },
    "directory": {
        "shape": "folder",
        "style": "filled",
        "fillcolor": "#f1f5f9",
        "color": "#475569",
        "fontcolor": "#1e293b",
    },
    "package": {
        "shape": "tab",
        "style": "filled",
        "fillcolor": "#f0fdf4",
        "color": "#15803d",
        "fontcolor": "#14532d",
    },
    "unresolved_symbol": {
        "shape": "box",
        "style": "dashed,filled",
        "fillcolor": "#f8fafc",
        "color": "#94a3b8",
        "fontcolor": "#64748b",
    },
    "external_module": {
        "shape": "box",
        "style": "dashed,filled",
        "fillcolor": "#f1f5f9",
        "color": "#94a3b8",
        "fontcolor": "#475569",
    },
}

DEFAULT_NODE_STYLE = {
    "shape": "box",
    "style": "rounded,filled",
    "fillcolor": "#f8fafc",
    "color": "#64748b",
    "fontcolor": "#334155",
}

EDGE_KIND_STYLES = {
    "calls": {"color": "#3b82f6", "style": "solid", "arrowhead": "vee", "weight": "2"},
    "inherits": {
        "color": "#8b5cf6",
        "style": "solid",
        "arrowhead": "empty",
        "weight": "3",
    },
    "imports": {
        "color": "#64748b",
        "style": "dashed",
        "arrowhead": "vee",
        "weight": "1",
    },
    "contains": {
        "color": "#10b981",
        "style": "dashed",
        "arrowhead": "open",
        "weight": "1",
    },
    "defines": {
        "color": "#10b981",
        "style": "dashed",
        "arrowhead": "open",
        "weight": "1",
    },
    "constructs": {
        "color": "#f59e0b",
        "style": "dotted",
        "arrowhead": "normal",
        "weight": "2",
    },
    "references": {
        "color": "#94a3b8",
        "style": "dotted",
        "arrowhead": "vee",
        "weight": "1",
    },
}

DEFAULT_EDGE_STYLE = {
    "color": "#94a3b8",
    "style": "solid",
    "arrowhead": "vee",
    "weight": "1",
}


def _escape(text: str) -> str:
    """Escape text for Graphviz double-quoted strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _sanitize_id(identifier: str) -> str:
    """Create a valid Graphviz node identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", identifier)


def graph_to_dot(graph: dict[str, Any]) -> str:
    """Convert a CodeStruct graph dictionary into a clean Graphviz DOT string."""
    metadata = graph.get("metadata", {})
    analysis_id = metadata.get("analysis_id", "codestruct")
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    lines: list[str] = [
        f'digraph "CodeStruct_{_sanitize_id(analysis_id)}" {{',
        '  graph [rankdir=TB, splines=spline, overlap=false, fontname="Inter,Helvetica,Arial,sans-serif", fontsize=11, bgcolor="#ffffff"];',
        '  node [fontname="Inter,Helvetica,Arial,sans-serif", fontsize=10, margin="0.15,0.08"];',
        '  edge [fontname="Inter,Helvetica,Arial,sans-serif", fontsize=8];',
        "",
    ]

    # Map node id to sanitized DOT id
    dot_id_map: dict[str, str] = {}
    for node in nodes:
        raw_id = node.get("id", "")
        dot_id_map[raw_id] = f"node_{_sanitize_id(raw_id)}"

    # Add nodes
    lines.append("  // Nodes")
    for node in nodes:
        raw_id = node.get("id", "")
        dot_id = dot_id_map[raw_id]
        name = node.get("name") or raw_id
        kind = node.get("kind", "entity")
        qname = node.get("qualified_name") or name

        style = NODE_KIND_STYLES.get(kind, DEFAULT_NODE_STYLE)
        attrs = node.get("attributes", {})

        # Build label: name \n (kind) \n optional metrics
        label_parts = [name, f"({kind})"]
        if "fan_in" in attrs and "fan_out" in attrs:
            label_parts.append(f"in: {attrs['fan_in']} | out: {attrs['fan_out']}")
        if "instability" in attrs:
            label_parts.append(f"I: {attrs['instability']}")

        label_str = "\\n".join(_escape(part) for part in label_parts)
        tooltip_str = _escape(f"{qname} [{kind}]")

        attr_parts = [
            f'label="{label_str}"',
            f'tooltip="{tooltip_str}"',
            f'shape="{style["shape"]}"',
            f'style="{style["style"]}"',
            f'fillcolor="{style["fillcolor"]}"',
            f'color="{style["color"]}"',
            f'fontcolor="{style["fontcolor"]}"',
        ]

        lines.append(f"  {dot_id} [{', '.join(attr_parts)}];")

    lines.append("")
    lines.append("  // Relationships")
    for edge in edges:
        source_id = edge.get("source_id", "")
        target_id = edge.get("target_id")
        kind = edge.get("kind", "references")
        status = edge.get("resolution_status", "resolved")

        if source_id not in dot_id_map or not target_id or target_id not in dot_id_map:
            continue

        src_dot = dot_id_map[source_id]
        tgt_dot = dot_id_map[target_id]
        style = EDGE_KIND_STYLES.get(kind, DEFAULT_EDGE_STYLE)

        edge_attrs = [
            f'label="{_escape(kind)}"',
            f'color="{style["color"]}"',
            f'style="{style["style"]}"',
            f'arrowhead="{style["arrowhead"]}"',
            f'weight="{style["weight"]}"',
        ]
        if status != "resolved":
            edge_attrs.append(f'tooltip="{_escape(status)}"')

        lines.append(f"  {src_dot} -> {tgt_dot} [{', '.join(edge_attrs)}];")

    lines.append("}")
    return "\n".join(lines) + "\n"
