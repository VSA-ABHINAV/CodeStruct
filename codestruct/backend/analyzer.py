"""CodeStruct AST Static Analysis Engine (Phase 1, 14, 15).

Extracts modules, classes, functions, and methods from Python source code,
computes defines, inherits, constructs, and calls relationships, and produces
deterministic Graph JSON conforming to Section 4.1.

Implements two-stage incremental analysis (Phase 14):
- Stage A (per-file, cacheable): extracts local nodes, defines edges, and candidate targets.
- Stage B (global, always fresh): merges per-file data and resolves cross-file relationships.
"""

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.patterns import detect_patterns
from backend.cache import load_cache, save_cache, get_file_cache_key


def _get_call_name(node: ast.AST) -> Optional[str]:
    """Extract dotted or simple name from a function call target."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value_name = _get_call_name(node.value)
        if value_name:
            return f"{value_name}.{node.attr}"
        return node.attr
    return None


def _walk_local_scope(node: ast.AST):
    """Walk AST nodes within the local scope, not descending into nested functions or classes."""
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield child
            yield from _walk_local_scope(child)


def stage_a_parse_file(file_path: Path, base_dir: Path, is_single_file: bool) -> Dict[str, Any]:
    """Stage A (per-file, cacheable):
    Parse a single .py file into its nodes, defines edges, and unresolved candidate targets.
    """
    if is_single_file:
        rel_file_path = file_path.name
        module_path = file_path.stem
    else:
        rel_file_path = file_path.relative_to(base_dir).as_posix()
        parts = list(file_path.relative_to(base_dir).with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1] or [base_dir.name]
        module_path = ".".join(parts) if parts else base_dir.name

    nodes: List[Dict[str, Any]] = []
    defines_edges: List[Dict[str, str]] = []
    candidate_classes: List[Dict[str, Any]] = []
    candidate_callables: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding="latin-1")
        except Exception as e:
            return {
                "rel_file_path": rel_file_path,
                "module_path": module_path,
                "nodes": [],
                "defines_edges": [],
                "candidate_classes": [],
                "candidate_callables": [],
                "errors": [{"file_path": rel_file_path, "message": str(e)}],
            }
    except Exception as e:
        return {
            "rel_file_path": rel_file_path,
            "module_path": module_path,
            "nodes": [],
            "defines_edges": [],
            "candidate_classes": [],
            "candidate_callables": [],
            "errors": [{"file_path": rel_file_path, "message": str(e)}],
        }

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return {
            "rel_file_path": rel_file_path,
            "module_path": module_path,
            "nodes": [],
            "defines_edges": [],
            "candidate_classes": [],
            "candidate_callables": [],
            "errors": [{"file_path": rel_file_path, "message": f"SyntaxError: {e.msg} at line {e.lineno}"}],
        }
    except Exception as e:
        return {
            "rel_file_path": rel_file_path,
            "module_path": module_path,
            "nodes": [],
            "defines_edges": [],
            "candidate_classes": [],
            "candidate_callables": [],
            "errors": [{"file_path": rel_file_path, "message": str(e)}],
        }

    # Module node
    module_node_id = module_path
    total_lines = max(1, len(content.splitlines()))
    module_node = {
        "id": module_node_id,
        "name": module_path,
        "kind": "module",
        "module": module_path,
        "file_path": rel_file_path,
        "lineno": 1,
        "end_lineno": total_lines,
        "parent_id": None,
        "docstring": ast.get_docstring(tree),
    }
    nodes.append(module_node)

    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            class_name = stmt.name
            class_id = f"{module_path}.{class_name}"
            class_node = {
                "id": class_id,
                "name": class_name,
                "kind": "class",
                "module": module_path,
                "file_path": rel_file_path,
                "lineno": stmt.lineno,
                "end_lineno": getattr(stmt, "end_lineno", stmt.lineno),
                "parent_id": module_node_id,
                "docstring": ast.get_docstring(stmt),
            }
            nodes.append(class_node)
            defines_edges.append({"source": module_node_id, "target": class_id, "type": "defines"})

            base_names = []
            for base in stmt.bases:
                b_name = _get_call_name(base)
                if b_name:
                    base_names.append(b_name)
            candidate_classes.append({
                "class_id": class_id,
                "class_name": class_name,
                "module_path": module_path,
                "base_names": base_names,
            })

            # Methods inside class
            for item in stmt.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_name = item.name
                    method_id = f"{class_id}.{method_name}"
                    method_node = {
                        "id": method_id,
                        "name": method_name,
                        "kind": "method",
                        "module": module_path,
                        "file_path": rel_file_path,
                        "lineno": item.lineno,
                        "end_lineno": getattr(item, "end_lineno", item.lineno),
                        "parent_id": class_id,
                        "docstring": ast.get_docstring(item),
                    }
                    nodes.append(method_node)
                    defines_edges.append({"source": class_id, "target": method_id, "type": "defines"})

                    local_assigns = []
                    calls = []
                    for sub_node in _walk_local_scope(item):
                        if isinstance(sub_node, ast.Assign):
                            if isinstance(sub_node.value, ast.Call):
                                called_name = _get_call_name(sub_node.value.func)
                                if called_name:
                                    for target in sub_node.targets:
                                        if isinstance(target, ast.Name):
                                            local_assigns.append({"target": target.id, "called_name": called_name})
                        elif isinstance(sub_node, ast.AnnAssign):
                            if sub_node.value and isinstance(sub_node.value, ast.Call):
                                called_name = _get_call_name(sub_node.value.func)
                                if called_name and isinstance(sub_node.target, ast.Name):
                                    local_assigns.append({"target": sub_node.target.id, "called_name": called_name})
                        elif isinstance(sub_node, ast.NamedExpr):
                            if isinstance(sub_node.value, ast.Call):
                                called_name = _get_call_name(sub_node.value.func)
                                if called_name and isinstance(sub_node.target, ast.Name):
                                    local_assigns.append({"target": sub_node.target.id, "called_name": called_name})

                    for sub_node in _walk_local_scope(item):
                        if isinstance(sub_node, ast.Call):
                            called_name = _get_call_name(sub_node.func)
                            if called_name:
                                calls.append({"type": "call", "called_name": called_name})
                            if isinstance(sub_node.func, ast.Attribute) and isinstance(sub_node.func.value, ast.Name):
                                calls.append({
                                    "type": "attr_call",
                                    "var_name": sub_node.func.value.id,
                                    "attr_name": sub_node.func.attr,
                                })

                    candidate_callables.append({
                        "callable_id": method_id,
                        "module_path": module_path,
                        "enclosing_class_id": class_id,
                        "local_assigns": local_assigns,
                        "calls": calls,
                    })

        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = stmt.name
            func_id = f"{module_path}.{func_name}"
            func_node = {
                "id": func_id,
                "name": func_name,
                "kind": "function",
                "module": module_path,
                "file_path": rel_file_path,
                "lineno": stmt.lineno,
                "end_lineno": getattr(stmt, "end_lineno", stmt.lineno),
                "parent_id": module_node_id,
                "docstring": ast.get_docstring(stmt),
            }
            nodes.append(func_node)
            defines_edges.append({"source": module_node_id, "target": func_id, "type": "defines"})

            local_assigns = []
            calls = []
            for sub_node in _walk_local_scope(stmt):
                if isinstance(sub_node, ast.Assign):
                    if isinstance(sub_node.value, ast.Call):
                        called_name = _get_call_name(sub_node.value.func)
                        if called_name:
                            for target in sub_node.targets:
                                if isinstance(target, ast.Name):
                                    local_assigns.append({"target": target.id, "called_name": called_name})
                elif isinstance(sub_node, ast.AnnAssign):
                    if sub_node.value and isinstance(sub_node.value, ast.Call):
                        called_name = _get_call_name(sub_node.value.func)
                        if called_name and isinstance(sub_node.target, ast.Name):
                            local_assigns.append({"target": sub_node.target.id, "called_name": called_name})
                elif isinstance(sub_node, ast.NamedExpr):
                    if isinstance(sub_node.value, ast.Call):
                        called_name = _get_call_name(sub_node.value.func)
                        if called_name and isinstance(sub_node.target, ast.Name):
                            local_assigns.append({"target": sub_node.target.id, "called_name": called_name})

            for sub_node in _walk_local_scope(stmt):
                if isinstance(sub_node, ast.Call):
                    called_name = _get_call_name(sub_node.func)
                    if called_name:
                        calls.append({"type": "call", "called_name": called_name})
                    if isinstance(sub_node.func, ast.Attribute) and isinstance(sub_node.func.value, ast.Name):
                        calls.append({
                            "type": "attr_call",
                            "var_name": sub_node.func.value.id,
                            "attr_name": sub_node.func.attr,
                        })

            candidate_callables.append({
                "callable_id": func_id,
                "module_path": module_path,
                "enclosing_class_id": None,
                "local_assigns": local_assigns,
                "calls": calls,
            })

    return {
        "rel_file_path": rel_file_path,
        "module_path": module_path,
        "nodes": nodes,
        "defines_edges": defines_edges,
        "candidate_classes": candidate_classes,
        "candidate_callables": candidate_callables,
        "errors": errors,
    }


def stage_b_resolve_graph(
    project_root: str,
    stage_a_outputs: List[Dict[str, Any]],
    cache_hits: int = 0,
    cache_misses: int = 0,
) -> Dict[str, Any]:
    """Stage B (global, always fresh, never cached):
    Merge all Stage A outputs into a project symbol table and resolve inherits, constructs, and calls edges.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []
    seen_edges: Set[Tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, edge_type: str) -> None:
        key = (source, target, edge_type)
        if key not in seen_edges and source and target:
            seen_edges.add(key)
            edges.append({"source": source, "target": target, "type": edge_type})

    all_candidate_classes: List[Dict[str, Any]] = []
    all_candidate_callables: List[Dict[str, Any]] = []

    for out in stage_a_outputs:
        nodes.extend(out.get("nodes", []))
        errors.extend(out.get("errors", []))
        for edge in out.get("defines_edges", []):
            add_edge(edge["source"], edge["target"], edge["type"])
        all_candidate_classes.extend(out.get("candidate_classes", []))
        all_candidate_callables.extend(out.get("candidate_callables", []))

    # Symbol registries for cross-referencing
    known_classes: Dict[str, Dict[str, Any]] = {}
    known_functions: Dict[str, Dict[str, Any]] = {}
    known_methods: Dict[str, Dict[str, Any]] = {}
    classes_by_short_name: Dict[str, List[str]] = {}
    funcs_by_short_name: Dict[str, List[str]] = {}
    class_hierarchy: Dict[str, List[str]] = {}

    for n in nodes:
        k = n.get("kind")
        nid = n.get("id")
        nname = n.get("name")
        if k == "class":
            known_classes[nid] = n
            classes_by_short_name.setdefault(nname, []).append(nid)
        elif k == "function":
            known_functions[nid] = n
            funcs_by_short_name.setdefault(nname, []).append(nid)
        elif k == "method":
            known_methods[nid] = n

    # Pass 2A: Resolve inherits edges
    for cls in all_candidate_classes:
        class_id = cls["class_id"]
        module_path = cls["module_path"]
        for base_name in cls["base_names"]:
            target_class_id = None
            candidate_same_mod = f"{module_path}.{base_name}"
            if candidate_same_mod in known_classes:
                target_class_id = candidate_same_mod
            elif base_name in known_classes:
                target_class_id = base_name
            elif base_name in classes_by_short_name and len(classes_by_short_name[base_name]) == 1:
                target_class_id = classes_by_short_name[base_name][0]

            if target_class_id:
                class_hierarchy.setdefault(class_id, []).append(target_class_id)
                add_edge(class_id, target_class_id, "inherits")

    def find_method_in_class(cls_id: str, method_name: str) -> Optional[str]:
        direct = f"{cls_id}.{method_name}"
        if direct in known_methods:
            return direct
        for base_id in class_hierarchy.get(cls_id, []):
            inherited = find_method_in_class(base_id, method_name)
            if inherited:
                return inherited
        return None

    # Pass 2B: Resolve constructs and calls edges
    for cal in all_candidate_callables:
        callable_id = cal["callable_id"]
        module_path = cal["module_path"]
        enclosing_class_id = cal["enclosing_class_id"]

        # Build local resolution maps
        class_map: Dict[str, str] = {}
        for s_name, c_ids in classes_by_short_name.items():
            same_mod = [cid for cid in c_ids if cid.startswith(f"{module_path}.")]
            if same_mod:
                class_map[s_name] = same_mod[0]
            elif len(c_ids) == 1:
                class_map[s_name] = c_ids[0]
        for c_id in known_classes:
            class_map[c_id] = c_id

        func_map: Dict[str, str] = {}
        for s_name, f_ids in funcs_by_short_name.items():
            same_mod = [fid for fid in f_ids if fid.startswith(f"{module_path}.")]
            if same_mod:
                func_map[s_name] = same_mod[0]
            elif len(f_ids) == 1:
                func_map[s_name] = f_ids[0]
        for f_id in known_functions:
            func_map[f_id] = f_id

        # Local variable types
        local_types: Dict[str, str] = {}
        for assign in cal.get("local_assigns", []):
            tgt = assign["target"]
            cname = assign["called_name"]
            if cname in class_map:
                local_types[tgt] = class_map[cname]

        for call in cal.get("calls", []):
            if call["type"] == "call":
                called_name = call["called_name"]
                if called_name in class_map:
                    add_edge(callable_id, class_map[called_name], "constructs")
                elif called_name in func_map:
                    add_edge(callable_id, func_map[called_name], "calls")
            elif call["type"] == "attr_call":
                var_name = call["var_name"]
                attr_name = call["attr_name"]
                if var_name == "self" and enclosing_class_id:
                    target_method = find_method_in_class(enclosing_class_id, attr_name)
                    if target_method:
                        add_edge(callable_id, target_method, "calls")
                elif var_name in local_types:
                    var_class = local_types[var_name]
                    target_method = find_method_in_class(var_class, attr_name)
                    if target_method:
                        add_edge(callable_id, target_method, "calls")

    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "module_count": sum(1 for n in nodes if n["kind"] == "module"),
        "class_count": sum(1 for n in nodes if n["kind"] == "class"),
        "function_count": sum(1 for n in nodes if n["kind"] == "function"),
        "method_count": sum(1 for n in nodes if n["kind"] == "method"),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    }

    graph_dict = {
        "project_root": str(project_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
        "errors": errors,
        "summary": summary,
    }

    patterns = detect_patterns(graph_dict)
    graph_dict["patterns"] = patterns

    return graph_dict


def analyze_project(project_root: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Analyze a Python project directory or single Python file with two-stage caching (Phase 14).

    Returns Graph JSON matching the specification in Section 4.1.
    """
    root_path = Path(project_root).resolve()

    if not root_path.exists():
        errors = [{"file_path": str(project_root), "message": f"Path does not exist: {project_root}"}]
        return {
            "project_root": str(project_root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nodes": [],
            "edges": [],
            "errors": errors,
            "patterns": [],
            "summary": {
                "node_count": 0,
                "edge_count": 0,
                "module_count": 0,
                "class_count": 0,
                "function_count": 0,
                "method_count": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            },
        }

    # Determine files to analyze and root directory
    is_single_file = root_path.is_file()
    if is_single_file:
        base_dir = root_path.parent
        target_files = [root_path]
    else:
        base_dir = root_path
        skip_dirs = {".git", ".venv", "venv", "__pycache__", "build", "dist", ".tox", ".pytest_cache"}
        target_files = []
        for p in sorted(base_dir.rglob("*.py")):
            if not any(part in skip_dirs or part.startswith(".") for part in p.parts):
                target_files.append(p)

    if not target_files:
        errors = [{
            "file_path": str(project_root),
            "message": f"No .py files found in project directory: {project_root}",
        }]
        return {
            "project_root": str(project_root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nodes": [],
            "edges": [],
            "errors": errors,
            "patterns": [],
            "summary": {
                "node_count": 0,
                "edge_count": 0,
                "module_count": 0,
                "class_count": 0,
                "function_count": 0,
                "method_count": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            },
        }

    # Cache handling (Phase 14)
    cache_data = load_cache(str(root_path)) if not force_refresh else {}
    cache_hits = 0
    cache_misses = 0

    stage_a_outputs: List[Dict[str, Any]] = []
    current_rel_paths: Set[str] = set()

    for file_path in target_files:
        rel_path = file_path.name if is_single_file else file_path.relative_to(base_dir).as_posix()
        current_rel_paths.add(rel_path)
        current_key = get_file_cache_key(file_path)

        cached_entry = cache_data.get(rel_path)
        if not force_refresh and cached_entry and cached_entry.get("mtime_size") == current_key and "stage_a" in cached_entry:
            # Cache hit: reuse cached Stage A output
            stage_a_outputs.append(cached_entry["stage_a"])
            cache_hits += 1
        else:
            # Cache miss: parse Stage A fresh
            stage_a_out = stage_a_parse_file(file_path, base_dir, is_single_file)
            stage_a_outputs.append(stage_a_out)
            cache_data[rel_path] = {
                "mtime_size": current_key,
                "stage_a": stage_a_out,
            }
            cache_misses += 1

    # Drop cache entries for files no longer present in the project
    for cached_rel in list(cache_data.keys()):
        if cached_rel not in current_rel_paths:
            del cache_data[cached_rel]

    # Persist cache to disk
    save_cache(str(root_path), cache_data)

    # Stage B: global resolution always runs fresh
    return stage_b_resolve_graph(
        project_root=str(project_root),
        stage_a_outputs=stage_a_outputs,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )


def compute_impact(graph: Dict[str, Any], node_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
    """Transitive backward impact BFS over calls/constructs/inherits edges, excluding defines."""
    nodes_map = {n["id"]: n for n in graph.get("nodes", [])}
    if node_id not in nodes_map:
        for nid, node in nodes_map.items():
            if node.get("name") == node_id or nid.endswith("." + node_id):
                node_id = nid
                break
    backward = {}
    for e in graph.get("edges", []):
        if e.get("type") in ("calls", "constructs", "inherits"):
            target = e.get("target")
            if target:
                backward.setdefault(target, []).append((e.get("source"), e.get("type")))
    result = []
    visited = {node_id}
    queue = [(node_id, 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        for src, etype in backward.get(current, []):
            if src and src not in visited:
                visited.add(src)
                result.append({"id": src, "name": nodes_map.get(src, {}).get("name", src), "depth": depth + 1, "via_edge_type": etype})
                queue.append((src, depth + 1))
    result.sort(key=lambda x: x["depth"])
    return result
