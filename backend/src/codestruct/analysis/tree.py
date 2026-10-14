"""Directory tree and nested Python symbol hierarchy for project explorer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDED_DIRS: dict[str, str] = {
    ".git": "Default policy excludes version control directory '.git'",
    "__pycache__": "Default policy excludes Python bytecode cache directory '__pycache__'",
    ".venv": "Default policy excludes virtual environment directory '.venv'",
    "venv": "Default policy excludes virtual environment directory 'venv'",
    ".idea": "Default policy excludes IDE configuration directory '.idea'",
    ".vscode": "Default policy excludes IDE configuration directory '.vscode'",
    "node_modules": "Default policy excludes dependency directory 'node_modules'",
    ".pytest_cache": "Default policy excludes test cache directory '.pytest_cache'",
    ".mypy_cache": "Default policy excludes type checker cache directory '.mypy_cache'",
    ".ruff_cache": "Default policy excludes linter cache directory '.ruff_cache'",
    "dist": "Default policy excludes build distribution directory 'dist'",
    "build": "Default policy excludes build output directory 'build'",
    ".tox": "Default policy excludes test environment directory '.tox'",
}


def _sort_key_span(node: dict[str, Any]) -> tuple[int, int]:
    loc = node.get("location")
    if isinstance(loc, dict):
        line = loc.get("start_line") or 0
        col = loc.get("start_column") or 0
        return (line, col)
    return (0, 0)


def _build_file_symbols(
    file_rel_path: str, nodes_for_file: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build nested symbols (module -> classes -> methods; functions) in source order."""
    if not nodes_for_file:
        return []

    # Partition symbols by kind
    modules = [n for n in nodes_for_file if n.get("kind") == "module"]
    classes = [n for n in nodes_for_file if n.get("kind") == "class"]
    functions = [
        n for n in nodes_for_file if n.get("kind") in {"function", "async_function"}
    ]
    methods = [n for n in nodes_for_file if n.get("kind") in {"method", "async_method"}]

    # Map methods to their owning class
    methods_by_class_id: dict[str, list[dict[str, Any]]] = {
        c.get("id", ""): [] for c in classes
    }
    unparented_methods: list[dict[str, Any]] = []

    for m in methods:
        parent_id = m.get("parent_id")
        qname = str(m.get("qualified_name", ""))
        matched_class = None

        if parent_id and parent_id in methods_by_class_id:
            matched_class = parent_id
        else:
            # Fallback to qualified name prefix
            for c in classes:
                cqname = str(c.get("qualified_name", ""))
                if cqname and qname.startswith(f"{cqname}."):
                    matched_class = c.get("id", "")
                    break

        if matched_class and matched_class in methods_by_class_id:
            methods_by_class_id[matched_class].append(m)
        else:
            unparented_methods.append(m)

    # Format class nodes with nested methods
    formatted_classes: list[dict[str, Any]] = []
    for c in classes:
        c_id = c.get("id", "")
        c_methods = sorted(methods_by_class_id.get(c_id, []), key=_sort_key_span)
        loc = c.get("location") or {}
        formatted_classes.append(
            {
                "id": c_id,
                "name": c.get("name", ""),
                "qualified_name": c.get("qualified_name", ""),
                "kind": "class",
                "line": loc.get("start_line"),
                "column": loc.get("start_column"),
                "children": [
                    {
                        "id": m.get("id", ""),
                        "name": m.get("name", ""),
                        "qualified_name": m.get("qualified_name", ""),
                        "kind": m.get("kind", "method"),
                        "line": (m.get("location") or {}).get("start_line"),
                        "column": (m.get("location") or {}).get("start_column"),
                        "children": [],
                    }
                    for m in c_methods
                ],
            }
        )

    # Format functions
    formatted_functions: list[dict[str, Any]] = []
    for f in functions:
        loc = f.get("location") or {}
        formatted_functions.append(
            {
                "id": f.get("id", ""),
                "name": f.get("name", ""),
                "qualified_name": f.get("qualified_name", ""),
                "kind": f.get("kind", "function"),
                "line": loc.get("start_line"),
                "column": loc.get("start_column"),
                "children": [],
            }
        )

    # Add any unparented methods as functions/methods
    for m in unparented_methods:
        loc = m.get("location") or {}
        formatted_functions.append(
            {
                "id": m.get("id", ""),
                "name": m.get("name", ""),
                "qualified_name": m.get("qualified_name", ""),
                "kind": m.get("kind", "method"),
                "line": loc.get("start_line"),
                "column": loc.get("start_column"),
                "children": [],
            }
        )

    # Combine top-level symbols and sort in source order
    top_level_symbols = formatted_classes + formatted_functions
    top_level_symbols.sort(key=lambda s: (s.get("line") or 0, s.get("column") or 0))

    if modules:
        mod = modules[0]
        mod_loc = mod.get("location") or {}
        return [
            {
                "id": mod.get("id", ""),
                "name": mod.get("name", ""),
                "qualified_name": mod.get("qualified_name", ""),
                "kind": "module",
                "line": mod_loc.get("start_line"),
                "column": mod_loc.get("start_column"),
                "children": top_level_symbols,
            }
        ]

    return top_level_symbols


def build_project_tree(
    project_root: Path,
    graph_nodes: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Recursively build a complete directory and symbol tree for the project.

    Returns:
    - Root directory tree dict with nested directories, files, and Python symbols.
    - Excluded directories list with paths and human-readable explanation.
    """
    canonical_root = project_root.resolve()
    excluded: list[dict[str, str]] = []

    # Index graph nodes by relative file path (using forward slashes)
    nodes_by_file: dict[str, list[dict[str, Any]]] = {}
    if graph_nodes:
        for node in graph_nodes:
            loc = node.get("location")
            if isinstance(loc, dict) and loc.get("path"):
                norm_p = str(loc["path"]).replace("\\", "/")
                nodes_by_file.setdefault(norm_p, []).append(node)

    def _walk_dir(current_dir: Path) -> dict[str, Any]:
        rel_to_root = current_dir.relative_to(canonical_root).as_posix()
        dir_id = (
            f"dir_{rel_to_root}" if rel_to_root and rel_to_root != "." else "dir_root"
        )
        dir_name = canonical_root.name if rel_to_root in {"", "."} else current_dir.name

        dir_children: list[dict[str, Any]] = []

        try:
            entries = sorted(
                current_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except (PermissionError, OSError) as exc:
            logger.warning("Cannot read directory '%s': %s", current_dir, exc)
            return {
                "id": dir_id,
                "name": dir_name,
                "path": rel_to_root if rel_to_root != "." else "",
                "kind": "directory",
                "children": [],
            }

        for entry in entries:
            entry_name = entry.name
            entry_rel = entry.relative_to(canonical_root).as_posix()

            # Containment check: prevent symlink escape
            try:
                resolved_entry = entry.resolve()
                if not resolved_entry.is_relative_to(canonical_root):
                    excluded.append(
                        {
                            "path": entry_rel,
                            "reason": f"Path '{entry_name}' resolves outside the project root and was skipped.",
                        }
                    )
                    continue
            except Exception:
                excluded.append(
                    {
                        "path": entry_rel,
                        "reason": f"Cannot safely resolve path '{entry_name}'.",
                    }
                )
                continue

            if entry.is_dir():
                # Check for policy exclusions
                if entry_name in DEFAULT_EXCLUDED_DIRS:
                    excluded.append(
                        {
                            "path": entry_rel,
                            "reason": DEFAULT_EXCLUDED_DIRS[entry_name],
                        }
                    )
                    continue

                if entry_name.endswith(".egg-info"):
                    excluded.append(
                        {
                            "path": entry_rel,
                            "reason": "Default policy excludes packaging metadata directory '*.egg-info'",
                        }
                    )
                    continue

                sub_dir_node = _walk_dir(entry)
                dir_children.append(sub_dir_node)

            elif entry.is_file():
                ext = entry.suffix.lower()
                is_python = ext in {".py", ".pyi"}
                file_id = f"file_{entry_rel}"

                file_node: dict[str, Any] = {
                    "id": file_id,
                    "name": entry_name,
                    "path": entry_rel,
                    "kind": "file",
                    "extension": ext,
                }

                if is_python:
                    file_nodes = nodes_by_file.get(entry_rel, [])
                    symbols = _build_file_symbols(entry_rel, file_nodes)
                    file_node["symbols"] = symbols

                dir_children.append(file_node)

        return {
            "id": dir_id,
            "name": dir_name,
            "path": rel_to_root if rel_to_root != "." else "",
            "kind": "directory",
            "children": dir_children,
        }

    tree = _walk_dir(canonical_root)
    return tree, excluded
