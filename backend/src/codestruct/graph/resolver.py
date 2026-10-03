"""Conservative, non-executing relationship resolution over parser observations."""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace

from codestruct.analysis.models import (
    CallKind,
    ImportKind,
    ProjectParseResult,
    SourceSpan,
)

from .enums import Confidence, NodeKind, RelationshipKind, ResolutionStatus
from .identifiers import node_id
from .model import GraphNode


@dataclass(frozen=True, slots=True)
class RelationshipObservation:
    kind: RelationshipKind
    source_id: str
    target_id: str | None
    target_reference: str | None
    status: ResolutionStatus
    confidence: Confidence
    reason_code: str
    candidate_ids: tuple[str, ...]
    discriminator: str
    attributes: tuple[tuple[str, str], ...]
    source_unit_id: str
    relative_path: str
    span: SourceSpan
    observation_kind: str
    expression: str


@dataclass(frozen=True, slots=True)
class _Binding:
    scope_id: str
    name: str
    target_ids: tuple[str, ...]
    kind: str
    status: ResolutionStatus
    reference: str


class SymbolIndex:
    """Deterministic lookup index; duplicate candidates remain visible."""

    def __init__(self, nodes: tuple[GraphNode, ...]) -> None:
        modules: dict[str, list[GraphNode]] = {}
        qualified: dict[str, list[GraphNode]] = {}
        children: dict[str, list[GraphNode]] = {}
        for item in nodes:
            if item.kind in {NodeKind.MODULE, NodeKind.PACKAGE}:
                modules.setdefault(item.qualified_name, []).append(item)
            if item.kind in {
                NodeKind.CLASS,
                NodeKind.FUNCTION,
                NodeKind.ASYNC_FUNCTION,
                NodeKind.METHOD,
                NodeKind.ASYNC_METHOD,
            }:
                qualified.setdefault(item.qualified_name, []).append(item)
            if item.parent_id:
                children.setdefault(item.parent_id, []).append(item)

        def order(node: GraphNode) -> tuple[int, str, str, str]:
            is_stub = (
                1 if (node.location and node.location.path.endswith(".pyi")) else 0
            )
            return (is_stub, node.kind.value, node.qualified_name, node.id)

        self._modules = {
            key: tuple(sorted(value, key=order)) for key, value in modules.items()
        }
        self._qualified = {
            key: tuple(sorted(value, key=order)) for key, value in qualified.items()
        }
        self._children = {
            key: tuple(sorted(value, key=order)) for key, value in children.items()
        }
        self.nodes_by_id = {node.id: node for node in nodes}

    def modules(self, qualified_name: str) -> tuple[GraphNode, ...]:
        candidates = self._modules.get(qualified_name, ())
        # A package and its __init__ module share an import name. The module is
        # the executable namespace; the package remains a containment entity.
        module_nodes = tuple(n for n in candidates if n.kind is NodeKind.MODULE)
        return module_nodes or candidates

    def qualified(self, qualified_name: str) -> tuple[GraphNode, ...]:
        return self._qualified.get(qualified_name, ())

    def children(
        self,
        parent_id: str,
        name: str | None = None,
        kinds: frozenset[NodeKind] | None = None,
    ) -> tuple[GraphNode, ...]:
        result = self._children.get(parent_id, ())
        if name is not None:
            result = tuple(item for item in result if item.name == name)
        if kinds is not None:
            result = tuple(item for item in result if item.kind in kinds)
        return result


class RelationshipResolver:
    """Resolve only names supported by explicit lexical/import evidence."""

    _CALLABLES = frozenset(
        {
            NodeKind.CLASS,
            NodeKind.FUNCTION,
            NodeKind.ASYNC_FUNCTION,
            NodeKind.METHOD,
            NodeKind.ASYNC_METHOD,
        }
    )

    def __init__(
        self,
        parsed: ProjectParseResult,
        nodes: tuple[GraphNode, ...],
        parser_to_node: dict[str, str],
        parser_parent: dict[str, str | None],
        parser_module: dict[str, str],
        project_node_id: str,
    ) -> None:
        self.parsed = parsed
        self.index = SymbolIndex(nodes)
        self.parser_to_node = parser_to_node
        self.parser_parent = parser_parent
        self.parser_module = parser_module
        self.project_node_id = project_node_id
        self.bindings: dict[tuple[str, str], list[_Binding]] = {}
        self.synthetic_nodes: dict[str, GraphNode] = {}

    @staticmethod
    def _relative_module(
        module_name: str, is_package: bool, level: int, name: str | None
    ) -> str | None:
        if level == 0:
            return name
        package = module_name if is_package else module_name.rpartition(".")[0]
        parts = package.split(".") if package else []
        remove = level - 1
        if remove > len(parts):
            return None
        anchor = parts[: len(parts) - remove] if remove else parts
        if name:
            anchor.extend(name.split("."))
        return ".".join(anchor) or None

    def _source_node(self, parser_scope_id: str) -> str:
        return self.parser_to_node[parser_scope_id]

    def _result(
        self,
        *,
        kind: RelationshipKind,
        scope_id: str,
        target_ids: tuple[str, ...],
        reference: str,
        reason: str,
        status: ResolutionStatus,
        confidence: Confidence,
        discriminator: str,
        attributes: tuple[tuple[str, str], ...],
        source_unit_id: str,
        relative_path: str,
        span: SourceSpan,
        observation_kind: str,
        expression: str,
    ) -> RelationshipObservation:
        ordered = tuple(sorted(target_ids))
        return RelationshipObservation(
            kind=kind,
            source_id=self._source_node(scope_id),
            target_id=ordered[0] if len(ordered) == 1 else None,
            target_reference=reference
            if status is not ResolutionStatus.RESOLVED
            else None,
            status=status,
            confidence=confidence,
            reason_code=reason,
            candidate_ids=ordered,
            discriminator=discriminator,
            attributes=tuple(sorted(attributes)),
            source_unit_id=source_unit_id,
            relative_path=relative_path,
            span=span,
            observation_kind=observation_kind,
            expression=expression,
        )

    def _classified_target(
        self, reference: str, classification: str
    ) -> tuple[tuple[str, ...], ResolutionStatus, Confidence, str]:
        top_level = reference.split(".", 1)[0]
        is_symbol = classification.endswith("symbol")
        if (
            top_level in getattr(sys, "stdlib_module_names", frozenset())
            and not is_symbol
        ):
            identifier = node_id(NodeKind.EXTERNAL_MODULE, reference)
            self.synthetic_nodes.setdefault(
                identifier,
                GraphNode(
                    id=identifier,
                    kind=NodeKind.EXTERNAL_MODULE,
                    name=reference.rsplit(".", 1)[-1],
                    qualified_name=reference,
                    attributes=(("classification", "stdlib"),),
                ),
            )
            return (
                (identifier,),
                ResolutionStatus.RESOLVED,
                Confidence.HIGH,
                "EXTERNAL_STDLIB_NAME",
            )
        if top_level in getattr(sys, "stdlib_module_names", frozenset()) and is_symbol:
            classification = "external_symbol"
            identifier = node_id(NodeKind.UNRESOLVED_SYMBOL, classification, reference)
            self.synthetic_nodes.setdefault(
                identifier,
                GraphNode(
                    id=identifier,
                    kind=NodeKind.UNRESOLVED_SYMBOL,
                    name=reference.rsplit(".", 1)[-1],
                    qualified_name=reference,
                    attributes=(("classification", classification),),
                ),
            )
            return (
                (identifier,),
                ResolutionStatus.SYNTACTIC_ONLY,
                Confidence.UNKNOWN,
                "EXTERNAL_SYMBOL_NOT_INSPECTED",
            )
        identifier = node_id(NodeKind.UNRESOLVED_SYMBOL, classification, reference)
        self.synthetic_nodes.setdefault(
            identifier,
            GraphNode(
                id=identifier,
                kind=NodeKind.UNRESOLVED_SYMBOL,
                name=reference.rsplit(".", 1)[-1],
                qualified_name=reference,
                attributes=(("classification", classification),),
            ),
        )
        return (
            (identifier,),
            ResolutionStatus.UNRESOLVED,
            Confidence.UNKNOWN,
            "NO_INTERNAL_TARGET",
        )

    @classmethod
    def _filter_stub_shadows(
        cls, candidates: tuple[GraphNode, ...]
    ) -> tuple[GraphNode, ...]:
        """Prioritize .py implementation candidates over .pyi type stubs when both exist."""
        if len(candidates) <= 1:
            return candidates
        py_candidates = tuple(
            c
            for c in candidates
            if not (c.location and c.location.path.endswith(".pyi"))
        )
        if py_candidates:
            return py_candidates
        return candidates

    @classmethod
    def _status(
        cls, candidates: tuple[GraphNode, ...], missing_reason: str
    ) -> tuple[ResolutionStatus, Confidence, str]:
        filtered = cls._filter_stub_shadows(candidates)
        if len(filtered) == 1:
            return ResolutionStatus.RESOLVED, Confidence.EXACT, "EXACT_STATIC_TARGET"
        if len(filtered) > 1:
            return (
                ResolutionStatus.AMBIGUOUS,
                Confidence.UNKNOWN,
                "MULTIPLE_STATIC_CANDIDATES",
            )
        return ResolutionStatus.UNRESOLVED, Confidence.UNKNOWN, missing_reason

    def _add_binding(self, binding: _Binding) -> None:
        self.bindings.setdefault((binding.scope_id, binding.name), []).append(binding)

    def _visible_bindings(self, scope_id: str, name: str) -> tuple[_Binding, ...]:
        current: str | None = scope_id
        while current is not None:
            found = self.bindings.get((current, name), ())
            if found:
                return tuple(
                    sorted(found, key=lambda item: (item.reference, item.target_ids))
                )
            current = self.parser_parent.get(current)
        return ()

    def resolve_imports(self) -> list[RelationshipObservation]:
        relationships: list[RelationshipObservation] = []
        for file_result in self.parsed.files:
            if file_result.module is None:
                continue
            module = file_result.module
            source_file = file_result.source_file
            for statement in file_result.imports:
                if statement.kind is ImportKind.IMPORT:
                    for position, alias in enumerate(statement.names):
                        reference = alias.name
                        candidates = self._filter_stub_shadows(
                            self.index.modules(reference)
                        )
                        if candidates:
                            status, confidence, reason = self._status(
                                candidates, "MISSING_INTERNAL_MODULE"
                            )
                            target_ids = tuple(item.id for item in candidates)
                        else:
                            target_ids, status, confidence, reason = (
                                self._classified_target(
                                    reference, "external_or_missing_module"
                                )
                            )
                        bound = alias.alias or alias.name.split(".", 1)[0]
                        self._add_binding(
                            _Binding(
                                statement.enclosing_scope_id,
                                bound,
                                target_ids,
                                "module",
                                status,
                                reference,
                            )
                        )
                        relationships.append(
                            self._result(
                                kind=RelationshipKind.IMPORTS,
                                scope_id=statement.enclosing_scope_id,
                                target_ids=target_ids,
                                reference=reference,
                                reason=reason,
                                status=status,
                                confidence=confidence,
                                discriminator=f"{statement.id}:{position}:module",
                                attributes=(
                                    ("alias", alias.alias or ""),
                                    ("import_kind", "module"),
                                ),
                                source_unit_id=source_file.id,
                                relative_path=source_file.relative_path,
                                span=statement.span,
                                observation_kind="import_statement",
                                expression=f"import {reference}",
                            )
                        )
                    continue

                base = self._relative_module(
                    module.qualified_name,
                    module.is_package,
                    statement.relative_level,
                    statement.module,
                )
                for position, alias in enumerate(statement.names):
                    symbol_reference = f"{base}.{alias.name}" if base else alias.name
                    base_candidates = (
                        self._filter_stub_shadows(self.index.modules(base))
                        if base
                        else ()
                    )
                    symbol_candidates: tuple[GraphNode, ...] = ()
                    submodule_candidates = self._filter_stub_shadows(
                        self.index.modules(symbol_reference)
                    )
                    if len(base_candidates) == 1:
                        symbol_candidates = self._filter_stub_shadows(
                            self.index.children(
                                base_candidates[0].id,
                                alias.name,
                                self._CALLABLES,
                            )
                        )
                    candidates = self._filter_stub_shadows(
                        symbol_candidates or submodule_candidates
                    )
                    import_kind = (
                        "symbol"
                        if symbol_candidates
                        else "module"
                        if submodule_candidates
                        else "symbol"
                    )
                    if candidates:
                        status, confidence, reason = self._status(
                            candidates, "MISSING_IMPORTED_SYMBOL"
                        )
                        target_ids = tuple(item.id for item in candidates)
                    elif statement.relative_level:
                        target_ids, status, confidence, reason = (
                            self._classified_target(
                                symbol_reference, "missing_relative_import"
                            )
                        )
                    else:
                        target_ids, status, confidence, reason = (
                            self._classified_target(
                                symbol_reference, "external_or_missing_symbol"
                            )
                        )
                    bound = alias.alias or alias.name
                    self._add_binding(
                        _Binding(
                            statement.enclosing_scope_id,
                            bound,
                            target_ids,
                            import_kind,
                            status,
                            symbol_reference,
                        )
                    )
                    relationships.append(
                        self._result(
                            kind=RelationshipKind.IMPORTS,
                            scope_id=statement.enclosing_scope_id,
                            target_ids=target_ids,
                            reference=symbol_reference,
                            reason=reason,
                            status=status,
                            confidence=confidence,
                            discriminator=f"{statement.id}:{position}:{import_kind}",
                            attributes=(
                                ("alias", alias.alias or ""),
                                ("import_kind", import_kind),
                                ("relative_level", str(statement.relative_level)),
                            ),
                            source_unit_id=source_file.id,
                            relative_path=source_file.relative_path,
                            span=statement.span,
                            observation_kind="from_import_statement",
                            expression=f"from {'.' * statement.relative_level}{statement.module or ''} import {alias.name}",
                        )
                    )
        return relationships

    def _classify_candidates(
        self,
        *,
        kind: RelationshipKind,
        scope_id: str,
        candidates: tuple[GraphNode, ...],
        reference: str,
        discriminator: str,
        attributes: tuple[tuple[str, str], ...],
        source_unit_id: str,
        relative_path: str,
        span: SourceSpan,
        observation_kind: str,
        expression: str,
        inferred: bool = False,
    ) -> RelationshipObservation:
        filtered = self._filter_stub_shadows(candidates)
        status, confidence, reason = self._status(
            filtered, "NO_SUPPORTED_STATIC_TARGET"
        )
        if status is ResolutionStatus.RESOLVED and inferred:
            confidence = Confidence.HIGH
            reason = "CONSERVATIVE_LEXICAL_TARGET"
        if not filtered:
            target_ids, status, confidence, reason = self._classified_target(
                reference, "unresolved_reference"
            )
        else:
            target_ids = tuple(item.id for item in filtered)

        return self._result(
            kind=kind,
            scope_id=scope_id,
            target_ids=target_ids,
            reference=reference,
            reason=reason,
            status=status,
            confidence=confidence,
            discriminator=discriminator,
            attributes=attributes,
            source_unit_id=source_unit_id,
            relative_path=relative_path,
            span=span,
            observation_kind=observation_kind,
            expression=expression,
        )

    def _enclosing_scope_ids(self, scope_id: str) -> list[str]:
        scopes: list[str] = []
        current: str | None = scope_id
        while current is not None:
            scopes.append(current)
            current = self.parser_parent.get(current)
        return scopes

    def resolve_inheritance(self) -> list[RelationshipObservation]:
        result: list[RelationshipObservation] = []
        classes = frozenset({NodeKind.CLASS})
        for file_result in self.parsed.files:
            if file_result.module is None:
                continue
            module_node_id = self.parser_to_node[file_result.module.id]
            source_file = file_result.source_file
            for base in file_result.inheritance:
                candidates: tuple[GraphNode, ...] = ()
                inferred = False
                if base.expression.isidentifier():
                    bindings = self._visible_bindings(base.class_id, base.expression)
                    ids = tuple(
                        sorted(
                            {
                                item
                                for binding in bindings
                                for item in binding.target_ids
                            }
                        )
                    )
                    candidates = tuple(
                        self.index.nodes_by_id[item]
                        for item in ids
                        if item in self.index.nodes_by_id
                        and self.index.nodes_by_id[item].kind is NodeKind.CLASS
                    )
                    if not candidates:
                        candidates = self.index.children(
                            module_node_id, base.expression, classes
                        )
                elif "." in base.expression:
                    owner_part, _, name = base.expression.rpartition(".")
                    bindings = self._visible_bindings(base.class_id, owner_part)
                    modules = tuple(
                        self.index.nodes_by_id[item]
                        for binding in bindings
                        for item in binding.target_ids
                        if item in self.index.nodes_by_id
                        and self.index.nodes_by_id[item].kind is NodeKind.MODULE
                    )
                    if not modules:
                        # Try direct module lookup
                        modules = self.index.modules(owner_part)
                    candidates = tuple(
                        candidate
                        for module in modules
                        for candidate in self.index.children(module.id, name, classes)
                    )
                    inferred = True
                status = (
                    ResolutionStatus.SYNTACTIC_ONLY
                    if base.expression_kind not in {"Name", "Attribute"}
                    else None
                )
                observation = self._classify_candidates(
                    kind=RelationshipKind.INHERITS,
                    scope_id=base.class_id,
                    candidates=tuple(sorted(candidates, key=lambda item: item.id)),
                    reference=base.expression,
                    discriminator=base.id,
                    attributes=(("expression_kind", base.expression_kind),),
                    source_unit_id=source_file.id,
                    relative_path=source_file.relative_path,
                    span=base.span,
                    observation_kind="base_class_expression",
                    expression=base.expression,
                    inferred=inferred,
                )
                if status is ResolutionStatus.SYNTACTIC_ONLY:
                    observation = replace(
                        observation,
                        target_id=None,
                        status=status,
                        confidence=Confidence.UNKNOWN,
                        reason_code="UNSUPPORTED_DYNAMIC_EXPRESSION",
                    )
                result.append(observation)
        return result

    def _nearest_class(self, scope_id: str) -> GraphNode | None:
        current: str | None = scope_id
        while current is not None:
            graph_id = self.parser_to_node.get(current)
            if graph_id and self.index.nodes_by_id[graph_id].kind is NodeKind.CLASS:
                return self.index.nodes_by_id[graph_id]
            current = self.parser_parent.get(current)
        return None

    def _find_class_methods(
        self, class_node: GraphNode, method_name: str, visited: set[str] | None = None
    ) -> tuple[GraphNode, ...]:
        if visited is None:
            visited = set()
        if class_node.id in visited:
            return ()
        visited.add(class_node.id)

        direct = self.index.children(class_node.id, method_name, self._CALLABLES)
        if direct:
            return direct

        # Search base classes in inheritance observations
        inherited: list[GraphNode] = []
        for file_result in self.parsed.files:
            for base in file_result.inheritance:
                if self.parser_to_node.get(base.class_id) == class_node.id:
                    # Look up base class node
                    base_candidates = self._find_base_class_nodes(
                        base.class_id, base.expression
                    )
                    for base_node in base_candidates:
                        inherited.extend(
                            self._find_class_methods(base_node, method_name, visited)
                        )
        return tuple(inherited)

    def _find_base_class_nodes(
        self, class_id: str, expression: str
    ) -> tuple[GraphNode, ...]:
        classes = frozenset({NodeKind.CLASS})
        if expression.isidentifier():
            bindings = self._visible_bindings(class_id, expression)
            ids = tuple(
                sorted({item for binding in bindings for item in binding.target_ids})
            )
            nodes = tuple(
                self.index.nodes_by_id[item]
                for item in ids
                if item in self.index.nodes_by_id
                and self.index.nodes_by_id[item].kind is NodeKind.CLASS
            )
            if nodes:
                return nodes
            module_id = self.parser_module.get(class_id)
            if module_id:
                module_node_id = self.parser_to_node.get(module_id)
                if module_node_id:
                    return self.index.children(module_node_id, expression, classes)
        elif "." in expression:
            owner_part, _, name = expression.rpartition(".")
            bindings = self._visible_bindings(class_id, owner_part)
            modules = tuple(
                self.index.nodes_by_id[item]
                for binding in bindings
                for item in binding.target_ids
                if item in self.index.nodes_by_id
                and self.index.nodes_by_id[item].kind is NodeKind.MODULE
            )
            if not modules:
                modules = self.index.modules(owner_part)
            return tuple(
                candidate
                for module in modules
                for candidate in self.index.children(module.id, name, classes)
            )
        return ()

    def resolve_calls(self) -> list[RelationshipObservation]:
        result: list[RelationshipObservation] = []
        for file_result in self.parsed.files:
            if file_result.module is None:
                continue
            module_node_id = self.parser_to_node[file_result.module.id]
            source_file = file_result.source_file
            for call in file_result.calls:
                candidates: tuple[GraphNode, ...] = ()
                inferred = False
                if call.kind is CallKind.DIRECT and call.expression.isidentifier():
                    # Check enclosing lexical scopes upward from caller to module
                    for parent_scope in self._enclosing_scope_ids(
                        call.enclosing_scope_id
                    ):
                        parent_graph_id = self.parser_to_node.get(parent_scope)
                        if parent_graph_id:
                            candidates = self.index.children(
                                parent_graph_id, call.expression, self._CALLABLES
                            )
                            if candidates:
                                break
                    if not candidates:
                        candidates = self.index.children(
                            module_node_id, call.expression, self._CALLABLES
                        )
                    if not candidates:
                        bindings = self._visible_bindings(
                            call.enclosing_scope_id, call.expression
                        )
                        ids = tuple(
                            sorted(
                                {
                                    item
                                    for binding in bindings
                                    for item in binding.target_ids
                                }
                            )
                        )
                        candidates = tuple(
                            self.index.nodes_by_id[item]
                            for item in ids
                            if item in self.index.nodes_by_id
                            and self.index.nodes_by_id[item].kind in self._CALLABLES
                        )
                elif call.kind is CallKind.ATTRIBUTE and "." in call.expression:
                    owner, _, name = call.expression.rpartition(".")
                    if owner in {"self", "cls"}:
                        enclosing_class = self._nearest_class(call.enclosing_scope_id)
                        if enclosing_class:
                            candidates = self._filter_stub_shadows(
                                self._find_class_methods(enclosing_class, name)
                            )
                            inferred = True
                    else:
                        bindings = self._visible_bindings(
                            call.enclosing_scope_id, owner
                        )
                        modules = tuple(
                            self.index.nodes_by_id[item]
                            for binding in bindings
                            for item in binding.target_ids
                            if item in self.index.nodes_by_id
                            and self.index.nodes_by_id[item].kind is NodeKind.MODULE
                        )
                        if not modules:
                            modules = self._filter_stub_shadows(
                                self.index.modules(owner)
                            )
                        candidates = tuple(
                            candidate
                            for module in modules
                            for candidate in self.index.children(
                                module.id, name, self._CALLABLES
                            )
                        )
                        candidates = self._filter_stub_shadows(candidates)
                        inferred = True

                relationship_kind = (
                    RelationshipKind.CONSTRUCTS
                    if len(candidates) == 1 and candidates[0].kind is NodeKind.CLASS
                    else RelationshipKind.CALLS
                )
                observation = self._classify_candidates(
                    kind=relationship_kind,
                    scope_id=call.enclosing_scope_id,
                    candidates=tuple(sorted(candidates, key=lambda item: item.id)),
                    reference=call.expression,
                    discriminator=call.id,
                    attributes=(("call_kind", call.kind.value),),
                    source_unit_id=source_file.id,
                    relative_path=source_file.relative_path,
                    span=call.span,
                    observation_kind="call_expression",
                    expression=call.expression,
                    inferred=inferred,
                )
                if call.kind in {CallKind.CHAINED_ATTRIBUTE, CallKind.EXPRESSION}:
                    observation = RelationshipObservation(
                        kind=observation.kind,
                        source_id=observation.source_id,
                        target_id=None,
                        target_reference=call.expression,
                        status=ResolutionStatus.SYNTACTIC_ONLY,
                        confidence=Confidence.UNKNOWN,
                        reason_code="UNSUPPORTED_DYNAMIC_EXPRESSION",
                        candidate_ids=(),
                        discriminator=observation.discriminator,
                        attributes=observation.attributes,
                        source_unit_id=observation.source_unit_id,
                        relative_path=observation.relative_path,
                        span=observation.span,
                        observation_kind=observation.observation_kind,
                        expression=observation.expression,
                    )
                result.append(observation)
        return result

    def resolve(
        self,
    ) -> tuple[tuple[RelationshipObservation, ...], tuple[GraphNode, ...]]:
        relationships = self.resolve_imports()
        relationships.extend(self.resolve_inheritance())
        relationships.extend(self.resolve_calls())

        def order(item):
            return (
                item.kind.value,
                item.source_id,
                item.target_id or item.target_reference or "",
                item.discriminator,
            )

        return (
            tuple(sorted(relationships, key=order)),
            tuple(
                sorted(
                    self.synthetic_nodes.values(),
                    key=lambda item: (item.kind.value, item.qualified_name, item.id),
                )
            ),
        )
