"""Design-Pattern Detection Engine for CodeStruct (Phase 13).

Detects three structurally-recognizable design patterns:
1. Singleton: __new__ guards and returns a cached class-level instance
2. Factory: returns different constructed types across conditional branches
3. Observer: iterates a self-owned collection and invokes a method on each element

Note: This is heuristic pattern-matching on code structure, not guaranteed
correct identification of design intent.
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def _walk_local_scope(node: ast.AST):
    """Walk AST nodes within the local scope, not descending into nested functions or classes."""
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield child
            yield from _walk_local_scope(child)


def _get_call_name(node: ast.AST) -> Optional[str]:
    """Extract dotted or simple name from a function/constructor call target."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value_name = _get_call_name(node.value)
        if value_name:
            return f"{value_name}.{node.attr}"
        return node.attr
    return None


def _get_if_chain_branches(root_if: ast.If) -> List[List[ast.stmt]]:
    """Return list of branch statement bodies for an if/elif/else chain."""
    branches: List[List[ast.stmt]] = []
    current = root_if
    while isinstance(current, ast.If):
        branches.append(current.body)
        if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
            current = current.orelse[0]
        else:
            if current.orelse:
                branches.append(current.orelse)
            break
    return branches


def _find_target_attribute_name(node: ast.AST, class_names: Set[str]) -> Optional[str]:
    """Check if node is cls.<name> or ClassName.<name>, returning <name>."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if node.value.id in class_names:
            return node.attr
    return None


def _check_singleton_class(class_def: ast.ClassDef, symbol_id: str) -> Optional[Dict[str, str]]:
    """Check Heuristic 1: Singleton.

    A class is flagged Singleton if ALL of the following hold:
    - It defines a __new__ method.
    - That method's body contains an if statement whose test compares a class-level
      attribute (cls.<name> or ClassName.<name>) to None.
    - Inside that if block, there is an assignment to that same attribute.
    - The method returns that attribute (directly or via class attribute reference) at the end.
    Evidence: "__new__ guards and returns a cached class-level instance"
    """
    # 1. Defines __new__ method
    new_method: Optional[ast.FunctionDef] = None
    for stmt in class_def.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == "__new__":
            new_method = stmt
            break

    if not new_method:
        return None

    cls_param = new_method.args.args[0].arg if new_method.args.args else "cls"
    class_names = {cls_param, class_def.name}

    # 2. Check if statement whose test compares cls.<name> or ClassName.<name> to None
    candidate_attr: Optional[str] = None
    guard_if: Optional[ast.If] = None

    for item in _walk_local_scope(new_method):
        if isinstance(item, ast.If):
            test = item.test
            # Compare cls.<attr> is/== None or None is/== cls.<attr>
            if isinstance(test, ast.Compare):
                left_attr = _find_target_attribute_name(test.left, class_names)
                for op, comp in zip(test.ops, test.comparators):
                    if isinstance(op, (ast.Is, ast.Eq)):
                        if left_attr and isinstance(comp, ast.Constant) and comp.value is None:
                            candidate_attr = left_attr
                            guard_if = item
                            break
                        comp_attr = _find_target_attribute_name(comp, class_names)
                        if comp_attr and isinstance(test.left, ast.Constant) and test.left.value is None:
                            candidate_attr = comp_attr
                            guard_if = item
                            break
            if candidate_attr:
                break

    if not candidate_attr or not guard_if:
        return None

    # 3. Inside that if block, there is an assignment to that same attribute
    assigned = False
    for item in _walk_local_scope(guard_if):
        if isinstance(item, ast.Assign):
            for t in item.targets:
                if _find_target_attribute_name(t, class_names) == candidate_attr:
                    assigned = True
                    break
        elif isinstance(item, ast.AnnAssign):
            if _find_target_attribute_name(item.target, class_names) == candidate_attr:
                assigned = True
                break
        if assigned:
            break

    if not assigned:
        return None

    # 4. Method returns that attribute at the end
    returns_attr = False
    for item in _walk_local_scope(new_method):
        if isinstance(item, ast.Return) and item.value is not None:
            if _find_target_attribute_name(item.value, class_names) == candidate_attr:
                returns_attr = True
                break

    if not returns_attr:
        return None

    return {
        "pattern": "Singleton",
        "symbol_id": symbol_id,
        "evidence": "__new__ guards and returns a cached class-level instance",
    }


def _check_factory_callable(
    fn_def: ast.AST,
    symbol_id: str,
    project_class_names: Set[str],
) -> Optional[Dict[str, str]]:
    """Check Heuristic 2: Factory.

    A function or method is flagged Factory if ALL of the following hold:
    - Its body contains 2 or more return <ClassName>(...) statements.
    - Those ClassNames are at least 2 distinct classes defined within the analyzed project.
    - Those return statements occur in different branches of the same if/elif/else chain
      (not sequential unconditional returns).
    Evidence: "returns different constructed types across conditional branches"
    """
    if not isinstance(fn_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None

    # Find all if chains in the function body
    for item in _walk_local_scope(fn_def):
        if isinstance(item, ast.If):
            branches = _get_if_chain_branches(item)
            if len(branches) < 2:
                continue

            # For each branch, find return statements that construct project classes
            branch_returns: List[List[Tuple[str, ast.Return]]] = []
            for branch_stmts in branches:
                cur_branch: List[Tuple[str, ast.Return]] = []
                for b_item in branch_stmts:
                    # Look for returns in this branch
                    if isinstance(b_item, ast.Return):
                        candidates = [b_item]
                    else:
                        candidates = [n for n in _walk_local_scope(b_item) if isinstance(n, ast.Return)]

                    for ret in candidates:
                        if ret.value and isinstance(ret.value, ast.Call):
                            call_name = _get_call_name(ret.value.func)
                            if call_name:
                                short_name = call_name.split(".")[-1]
                                if call_name in project_class_names:
                                    cur_branch.append((call_name, ret))
                                elif short_name in project_class_names:
                                    cur_branch.append((short_name, ret))
                branch_returns.append(cur_branch)

            # Check if returns occur in at least 2 different branches
            branches_with_returns = [b for b in branch_returns if len(b) > 0]
            if len(branches_with_returns) < 2:
                continue

            all_returned_classes: List[str] = []
            for b in branch_returns:
                for cls_name, _ in b:
                    all_returned_classes.append(cls_name)

            distinct_classes = set(all_returned_classes)
            # Must have 2 or more return <ClassName>(...) statements and at least 2 distinct classes
            if len(all_returned_classes) >= 2 and len(distinct_classes) >= 2:
                return {
                    "pattern": "Factory",
                    "symbol_id": symbol_id,
                    "evidence": "returns different constructed types across conditional branches",
                }

    return None


def _check_observer_class(class_def: ast.ClassDef, symbol_id: str) -> Optional[Dict[str, str]]:
    """Check Heuristic 3: Observer / Subject.

    A class is flagged Observer if ALL of the following hold:
    - It has a method containing a `for <var> in self.<attr>:` loop (iterating a self-owned attribute).
    - Inside that loop's body, there is a method call on the loop variable (<var>.<method>(...)).
    Evidence: "iterates a self-owned collection and invokes a method on each element"
    """
    for stmt in class_def.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Look for a for loop in this method
            for node in _walk_local_scope(stmt):
                if isinstance(node, ast.For):
                    # Check if iter target is self.<attr>
                    if (
                        isinstance(node.iter, ast.Attribute)
                        and isinstance(node.iter.value, ast.Name)
                        and node.iter.value.id == "self"
                    ):
                        # Extract loop variable names
                        loop_vars: Set[str] = set()
                        if isinstance(node.target, ast.Name):
                            loop_vars.add(node.target.id)
                        else:
                            for sub in ast.walk(node.target):
                                if isinstance(sub, ast.Name):
                                    loop_vars.add(sub.id)

                        if not loop_vars:
                            continue

                        # Check for a method call on any loop variable in loop body
                        for body_node in _walk_local_scope(node):
                            if isinstance(body_node, ast.Call) and isinstance(body_node.func, ast.Attribute):
                                if (
                                    isinstance(body_node.func.value, ast.Name)
                                    and body_node.func.value.id in loop_vars
                                ):
                                    return {
                                        "pattern": "Observer",
                                        "symbol_id": symbol_id,
                                        "evidence": "iterates a self-owned collection and invokes a method on each element",
                                    }

    return None


def detect_patterns(graph: Dict[str, Any], ast_trees: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Detect Singleton, Factory, and Observer design patterns from graph data and AST trees.

    Args:
        graph: Deterministic Graph JSON produced by analyze_project.
        ast_trees: Dictionary mapping file paths or module names to parsed ast.AST trees.
                   If not provided, AST trees will be parsed on-the-fly from project files.

    Returns:
        List of pattern matches: [{ "pattern": ..., "symbol_id": ..., "evidence": ... }, ...]
    """
    nodes = graph.get("nodes", [])
    project_root = graph.get("project_root", "")

    # Parse AST trees on demand if not provided
    trees: Dict[str, ast.AST] = {}
    if ast_trees:
        trees.update(ast_trees)

    # Collect project files to parse if missing
    root_path = Path(project_root).resolve() if project_root else None
    for n in nodes:
        file_path_str = n.get("file_path")
        if not file_path_str:
            continue
        if file_path_str not in trees:
            target_file: Optional[Path] = None
            if root_path:
                if root_path.is_file():
                    target_file = root_path
                else:
                    target_file = (root_path / file_path_str).resolve()
            else:
                target_file = Path(file_path_str).resolve()

            if target_file and target_file.exists() and target_file.is_file():
                try:
                    content = target_file.read_text(encoding="utf-8")
                    trees[file_path_str] = ast.parse(content, filename=str(target_file))
                except Exception:
                    pass

    # Collect project class names (for factory resolution)
    project_class_names: Set[str] = set()
    for n in nodes:
        if n.get("kind") == "class":
            project_class_names.add(n["name"])
            project_class_names.add(n["id"])

    # Map nodes to AST statements by file and line/name
    matches: List[Dict[str, str]] = []

    # Map trees by both relative path, normalized path, and module stem
    normalized_trees: Dict[str, ast.AST] = {}
    for k, v in trees.items():
        normalized_trees[k] = v
        normalized_trees[Path(k).name] = v
        normalized_trees[Path(k).stem] = v

    def get_tree_for_node(node: Dict[str, Any]) -> Optional[ast.AST]:
        fpath = node.get("file_path", "")
        if fpath in normalized_trees:
            return normalized_trees[fpath]
        fname = Path(fpath).name
        if fname in normalized_trees:
            return normalized_trees[fname]
        mod = node.get("module", "")
        if mod in normalized_trees:
            return normalized_trees[mod]
        return None

    # Find AST ClassDef for a class node
    def find_class_ast(node: Dict[str, Any]) -> Optional[ast.ClassDef]:
        tree = get_tree_for_node(node)
        if not tree:
            return None
        target_name = node["name"]
        target_line = node.get("lineno")
        for item in ast.walk(tree):
            if isinstance(item, ast.ClassDef) and item.name == target_name:
                if target_line is None or item.lineno == target_line:
                    return item
        # Fallback without line check
        for item in ast.walk(tree):
            if isinstance(item, ast.ClassDef) and item.name == target_name:
                return item
        return None

    # Find AST FunctionDef for a function or method node
    def find_func_ast(node: Dict[str, Any]) -> Optional[ast.AST]:
        tree = get_tree_for_node(node)
        if not tree:
            return None
        target_name = node["name"]
        target_line = node.get("lineno")
        for item in ast.walk(tree):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == target_name:
                if target_line is None or item.lineno == target_line:
                    return item
        for item in ast.walk(tree):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == target_name:
                return item
        return None

    # Process all nodes
    for node in nodes:
        kind = node.get("kind")
        symbol_id = node.get("id", "")

        # 1. Singleton Heuristic (applies to classes)
        if kind == "class":
            class_ast = find_class_ast(node)
            if class_ast:
                singleton_match = _check_singleton_class(class_ast, symbol_id)
                if singleton_match:
                    matches.append(singleton_match)

                # 3. Observer Heuristic (applies to classes as subjects)
                observer_match = _check_observer_class(class_ast, symbol_id)
                if observer_match:
                    matches.append(observer_match)

        # 2. Factory Heuristic (applies to functions and methods)
        elif kind in ("function", "method"):
            func_ast = find_func_ast(node)
            if func_ast:
                factory_match = _check_factory_callable(func_ast, symbol_id, project_class_names)
                if factory_match:
                    matches.append(factory_match)

    return matches

