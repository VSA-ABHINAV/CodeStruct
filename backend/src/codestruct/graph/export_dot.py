"""Graphviz DOT export generation for CodeStruct architecture graphs."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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


logger = logging.getLogger("codestruct.graph.export_dot")

MAX_EXPORT_NODES = 2000
MAX_EXPORT_EDGES = 5000
MAX_RENDER_BYTES = 10 * 1024 * 1024  # 10 MiB
DEFAULT_MAX_STDERR_BYTES = 64 * 1024  # 64 KiB
DEFAULT_RENDER_TIMEOUT = 15.0  # seconds


class GraphvizExportError(Exception):
    """Base exception for Graphviz export failures."""


class GraphvizNotFoundError(GraphvizExportError):
    """Raised when Graphviz 'dot' executable cannot be found."""


class GraphvizTimeoutError(GraphvizExportError):
    """Raised when Graphviz rendering exceeds the maximum allowed time."""


class GraphvizOutputLimitError(GraphvizExportError):
    """Raised when Graphviz output exceeds the maximum allowed byte size."""


class GraphvizRenderError(GraphvizExportError):
    """Raised when Graphviz fails to render the provided DOT graph."""


class GraphTooLargeForExportError(GraphvizExportError):
    """Raised when the graph node or edge count exceeds export safety bounds."""


def _escape(text: Any) -> str:
    """Safely escape arbitrary text for Graphviz double-quoted strings."""
    if text is None:
        return ""
    safe_chars: list[str] = []
    for ch in str(text):
        if ch == "\\":
            safe_chars.append("\\\\")
        elif ch == '"':
            safe_chars.append('\\"')
        elif ch == "\n":
            safe_chars.append("\\n")
        elif ch == "\r":
            continue
        elif ch == "\t":
            safe_chars.append("\\t")
        elif ord(ch) < 32 or ord(ch) == 127:
            safe_chars.append(f"\\x{ord(ch):02x}")
        else:
            safe_chars.append(ch)
    return "".join(safe_chars)


def _sanitize_id(identifier: str) -> str:
    """Create a valid Graphviz node identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(identifier))


def graph_to_dot(
    graph: dict[str, Any],
    max_bytes: int | None = None,
) -> str:
    """Convert a CodeStruct graph dictionary into a deterministic Graphviz DOT string."""
    effective_max_bytes = max_bytes if max_bytes is not None else MAX_RENDER_BYTES
    metadata = graph.get("metadata", {})
    analysis_id = metadata.get("analysis_id", "codestruct")

    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])

    if len(raw_nodes) > MAX_EXPORT_NODES or len(raw_edges) > MAX_EXPORT_EDGES:
        raise GraphTooLargeForExportError(
            f"Graph exceeds maximum export size bounds ({len(raw_nodes)} nodes > {MAX_EXPORT_NODES} "
            f"or {len(raw_edges)} edges > {MAX_EXPORT_EDGES})."
        )

    # Sort nodes and edges deterministically by ID and relationship tuple
    nodes = sorted(raw_nodes, key=lambda n: str(n.get("id", "")))
    edges = sorted(
        raw_edges,
        key=lambda e: (
            str(e.get("source_id", "")),
            str(e.get("target_id", "")),
            str(e.get("kind", "")),
            str(e.get("id", "")),
        ),
    )

    lines: list[str] = [
        f'digraph "CodeStruct_{_sanitize_id(analysis_id)}" {{',
        '  graph [rankdir=TB, splines=spline, overlap=false, fontname="Inter,Helvetica,Arial,sans-serif", fontsize=11, bgcolor="#ffffff"];',
        '  node [fontname="Inter,Helvetica,Arial,sans-serif", fontsize=10, margin="0.15,0.08"];',
        '  edge [fontname="Inter,Helvetica,Arial,sans-serif", fontsize=8];',
        "",
    ]

    current_bytes = sum(len(line.encode("utf-8")) + 1 for line in lines)
    if current_bytes > effective_max_bytes:
        raise GraphvizOutputLimitError(
            f"Serialized DOT output exceeded maximum byte limit ({effective_max_bytes} bytes)"
        )

    def _append_line(line: str) -> None:
        nonlocal current_bytes
        line_bytes = len(line.encode("utf-8")) + 1
        current_bytes += line_bytes
        if current_bytes > effective_max_bytes:
            raise GraphvizOutputLimitError(
                f"Serialized DOT output exceeded maximum byte limit ({effective_max_bytes} bytes)"
            )
        lines.append(line)

    # Map node id to sanitized DOT id
    dot_id_map: dict[str, str] = {}
    for node in nodes:
        raw_id = str(node.get("id", ""))
        dot_id_map[raw_id] = f"node_{_sanitize_id(raw_id)}"

    # Add nodes
    _append_line("  // Nodes")
    for node in nodes:
        raw_id = str(node.get("id", ""))
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

        _append_line(f"  {dot_id} [{', '.join(attr_parts)}];")

    _append_line("")
    _append_line("  // Relationships")
    for edge in edges:
        source_id = str(edge.get("source_id", ""))
        target_id = str(edge.get("target_id") or "")
        kind = str(edge.get("kind", "references"))
        status = str(edge.get("resolution_status", "resolved"))

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

        _append_line(f"  {src_dot} -> {tgt_dot} [{', '.join(edge_attrs)}];")

    _append_line("}")
    dot_str = "\n".join(lines) + "\n"
    if len(dot_str.encode("utf-8")) > effective_max_bytes:
        raise GraphvizOutputLimitError(
            f"Serialized DOT output exceeded maximum byte limit ({len(dot_str.encode('utf-8'))} > {effective_max_bytes} bytes)"
        )
    return dot_str


def find_graphviz_dot() -> str | None:
    """Locate the Graphviz 'dot' binary via environment override or system PATH."""
    override = os.environ.get("CODESTRUCT_GRAPHVIZ_DOT_PATH")
    if override and os.path.isfile(override) and os.access(override, os.X_OK):
        return override
    found = shutil.which("dot")
    if found:
        return found
    # On Windows, also check common installation directories if not on PATH
    if os.name == "nt":
        for program_files in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(program_files)
            if base:
                candidate = Path(base) / "Graphviz" / "bin" / "dot.exe"
                if candidate.is_file():
                    return str(candidate)
    return None


def _kill_process_tree(pid: int) -> None:
    """Terminate a process and its child processes defensively."""
    if pid <= 0:
        return
    if os.name == "nt":
        with contextlib.suppress(Exception):
            subprocess.run(  # noqa: S603
                ["taskkill", "/F", "/T", "/PID", str(pid)],  # noqa: S607
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
    else:
        with contextlib.suppress(Exception):
            os.kill(pid, 9)


def render_graphviz(
    graph: dict[str, Any],
    format: str = "svg",
    dot_path: str | None = None,
    timeout: float = DEFAULT_RENDER_TIMEOUT,
    max_bytes: int | None = None,
    max_stderr_bytes: int | None = None,
) -> bytes:
    """Render a canonical CodeStruct graph dictionary to SVG, PNG, or DOT bytes.

    Enforces byte limits as streams are consumed, terminates descendant processes
    promptly upon limit violations or timeouts, and bounds stderr diagnostics.

    Raises:
        GraphvizNotFoundError: If Graphviz executable is not installed or located.
        GraphTooLargeForExportError: If the graph exceeds export size limits.
        GraphvizTimeoutError: If rendering exceeds the timeout deadline.
        GraphvizOutputLimitError: If rendered output exceeds maximum byte limit.
        GraphvizRenderError: If rendering produces an error or invalid output.
    """
    effective_max_bytes = max_bytes if max_bytes is not None else MAX_RENDER_BYTES
    effective_max_stderr = (
        max_stderr_bytes if max_stderr_bytes is not None else DEFAULT_MAX_STDERR_BYTES
    )

    fmt = format.lower().strip()
    if fmt not in ("svg", "png", "dot"):
        raise ValueError(
            f"Unsupported export format '{format}'; must be 'dot', 'svg', or 'png'"
        )

    dot_content = graph_to_dot(graph, max_bytes=effective_max_bytes)
    if fmt == "dot":
        dot_bytes = dot_content.encode("utf-8")
        if len(dot_bytes) > effective_max_bytes:
            raise GraphvizOutputLimitError(
                f"Graphviz output exceeded maximum byte limit ({len(dot_bytes)} > {effective_max_bytes} bytes)"
            )
        return dot_bytes

    input_bytes = dot_content.encode("utf-8")

    executable = dot_path or find_graphviz_dot()
    if not executable:
        raise GraphvizNotFoundError(
            "Graphviz 'dot' executable was not found. Install Graphviz "
            "(e.g., 'winget install Graphviz.Graphviz' or 'apt install graphviz') "
            "and ensure 'dot' is in PATH or set CODESTRUCT_GRAPHVIZ_DOT_PATH."
        )

    cmd = [executable, f"-T{fmt}", "-Gmargin=0.2", "-Gdpi=96"]

    try:
        proc = subprocess.Popen(  # noqa: S603
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except Exception as exc:
        raise GraphvizRenderError(
            f"Failed to spawn Graphviz process '{executable}': {exc}"
        ) from exc

    stdout_chunks: list[bytes] = []
    stdout_bytes_read = 0
    stdout_exceeded = False

    stderr_chunks: list[bytes] = []
    stderr_bytes_read = 0
    stderr_exceeded = False

    def _write_stdin() -> None:
        try:
            if proc.stdin:
                proc.stdin.write(input_bytes)
                proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    def _read_stdout() -> None:
        nonlocal stdout_bytes_read, stdout_exceeded
        chunk_size = 65536
        try:
            if proc.stdout:
                while True:
                    try:
                        chunk = proc.stdout.read(chunk_size)
                    except (ValueError, OSError):
                        break
                    if not chunk:
                        break
                    stdout_bytes_read += len(chunk)
                    if stdout_bytes_read > effective_max_bytes:
                        stdout_exceeded = True
                        _kill_process_tree(proc.pid)
                        with contextlib.suppress(Exception):
                            proc.kill()
                        break
                    stdout_chunks.append(chunk)
        except Exception as exc:
            logger.debug("Exception while streaming stdout: %s", exc)

    def _read_stderr() -> None:
        nonlocal stderr_bytes_read, stderr_exceeded
        chunk_size = 8192
        try:
            if proc.stderr:
                while True:
                    try:
                        chunk = proc.stderr.read(chunk_size)
                    except (ValueError, OSError):
                        break
                    if not chunk:
                        break
                    stderr_bytes_read += len(chunk)
                    if stderr_bytes_read > effective_max_stderr:
                        stderr_exceeded = True
                        _kill_process_tree(proc.pid)
                        with contextlib.suppress(Exception):
                            proc.kill()
                        break
                    stderr_chunks.append(chunk)
        except Exception as exc:
            logger.debug("Exception while streaming stderr: %s", exc)

    t_in = threading.Thread(target=_write_stdin, name="dot_stdin_writer", daemon=True)
    t_out = threading.Thread(target=_read_stdout, name="dot_stdout_reader", daemon=True)
    t_err = threading.Thread(target=_read_stderr, name="dot_stderr_reader", daemon=True)

    t_in.start()
    t_out.start()
    t_err.start()

    start_time = time.monotonic()
    deadline = start_time + timeout
    timed_out = False

    while time.monotonic() < deadline:
        if proc.poll() is not None:
            t_out.join(timeout=0.2)
            t_err.join(timeout=0.2)
            if not t_out.is_alive() and not t_err.is_alive():
                break
        if stdout_exceeded or stderr_exceeded:
            break
        time.sleep(0.01)
    else:
        if proc.poll() is None:
            timed_out = True
            _kill_process_tree(proc.pid)
            with contextlib.suppress(Exception):
                proc.kill()

    # Ensure pipes are closed defensively
    with contextlib.suppress(Exception):
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
    with contextlib.suppress(Exception):
        if proc.stdout and not proc.stdout.closed:
            proc.stdout.close()
    with contextlib.suppress(Exception):
        if proc.stderr and not proc.stderr.closed:
            proc.stderr.close()

    t_in.join(timeout=0.5)
    t_out.join(timeout=0.5)
    t_err.join(timeout=0.5)

    with contextlib.suppress(Exception):
        proc.wait(timeout=1.0)

    if timed_out:
        raise GraphvizTimeoutError(f"Graphviz render timed out after {timeout:.1f}s")

    if stdout_exceeded:
        raise GraphvizOutputLimitError(
            f"Graphviz output exceeded maximum byte limit ({stdout_bytes_read} > {effective_max_bytes} bytes)"
        )

    if stderr_exceeded:
        raise GraphvizOutputLimitError(
            f"Graphviz stderr exceeded maximum byte limit ({stderr_bytes_read} > {effective_max_stderr} bytes)"
        )

    if proc.returncode != 0:
        err_msg = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
        raise GraphvizRenderError(
            f"Graphviz process exited with code {proc.returncode}: {err_msg}"
        )

    stdout_bytes = b"".join(stdout_chunks)

    # Format-specific signature verification
    if fmt == "svg":
        if b"<svg" not in stdout_bytes:
            raise GraphvizRenderError(
                "Graphviz output does not contain a valid SVG root element."
            )
    elif fmt == "png":
        if not stdout_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise GraphvizRenderError(
                "Graphviz output does not have a valid PNG file header."
            )

    return stdout_bytes
