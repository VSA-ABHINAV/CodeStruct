"""Semantic explanation and LLM/RAG context summarizer for architecture nodes.

Provides deterministic, offline-first architectural explanations analyzing coupling,
centrality, caller/callee networks, runtime traces, and structural risks. Supports
optional pluggable OpenAI-compatible LLM endpoints (e.g. local Ollama or cloud models)
with automatic fallback to rule-based synthesis.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class NodeContext:
    """Extracted architectural context for a single graph node."""

    node_id: str
    name: str
    qualified_name: str
    kind: str
    file_path: str | None = None
    line: int | None = None
    end_line: int | None = None
    docstring: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    importers: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    inherits: list[str] = field(default_factory=list)
    inherited_by: list[str] = field(default_factory=list)
    runtime_stats: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class NodeExplanation:
    """Architectural explanation for display and developer guidance."""

    node_id: str
    name: str
    kind: str
    role: str
    summary: str
    dependencies_summary: str
    metrics_summary: str
    recommendations: list[str]
    prompt: str | None = None
    provider: str = "rule-based"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "kind": self.kind,
            "role": self.role,
            "summary": self.summary,
            "dependencies_summary": self.dependencies_summary,
            "metrics_summary": self.metrics_summary,
            "recommendations": self.recommendations,
            "prompt": self.prompt,
            "provider": self.provider,
        }


def extract_node_context(graph: dict[str, Any], node_id: str) -> NodeContext:
    """Extract full structural context, metrics, evidence, and relationships for a node."""
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

    # Extract canonical location: {path, start_line, end_line} (flat) or nested variants
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

    # Extract attributes & metrics from dict, list of pairs, or list of dicts
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
        "runtime_exceptions",
        "runtime_duration_ms",
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

    evidence_index: dict[str, dict[str, Any]] = {}
    for ev in graph.get("evidence", []):
        if isinstance(ev, dict):
            eid = str(ev.get("evidence_id") or ev.get("id") or "")
            if eid:
                evidence_index[eid] = ev

    collected_evidence: list[dict[str, Any]] = []
    for eid in sorted(incident_evidence_ids):
        ev = evidence_index.get(eid)
        if ev:
            collected_evidence.append(
                {
                    "id": eid,
                    "origin": ev.get("origin"),
                    "observation_kind": ev.get("observation_kind"),
                    "location": ev.get("location"),
                    "observed_text_hash": ev.get("observed_text_hash"),
                    "excerpt": ev.get("excerpt"),
                    "explanation": ev.get("explanation"),
                    "expression": ev.get("expression"),
                }
            )

    return NodeContext(
        node_id=node_id,
        name=name,
        qualified_name=qualified_name,
        kind=kind,
        file_path=file_path,
        line=line,
        end_line=end_line,
        docstring=docstring,
        metrics=metrics,
        callers=sorted(set(callers)),
        callees=sorted(set(callees)),
        importers=sorted(set(importers)),
        imports=sorted(set(imports)),
        inherits=sorted(set(inherits)),
        inherited_by=sorted(set(inherited_by)),
        runtime_stats=runtime_stats,
        evidence=collected_evidence,
    )


def format_explanation_prompt(context: NodeContext) -> str:
    """Format an LLM prompt describing the architecture context of a node."""
    file_loc = context.file_path or "unknown"
    if context.line is not None:
        file_loc += f":{context.line}"
        if context.end_line is not None and context.end_line != context.line:
            file_loc += f"-{context.end_line}"
    else:
        file_loc += ":?"

    lines = [
        "You are an expert Python software architect analyzing a codebase architecture graph.",
        "Analyze the following code entity and provide a clear, concise architectural summary:",
        "",
        f"Entity: {context.name} ({context.kind})",
        f"Qualified Name: {context.qualified_name}",
        f"File: {file_loc}",
    ]
    if context.docstring:
        lines.append(f"Docstring: {context.docstring.strip()}")

    lines.append("\nArchitecture Metrics:")
    for k, v in sorted(context.metrics.items()):
        lines.append(f"- {k}: {v}")

    if context.runtime_stats:
        lines.append("\nRuntime Profiling Evidence:")
        for k, v in sorted(context.runtime_stats.items()):
            lines.append(f"- {k}: {v}")

    lines.append("\nDependency Network:")
    lines.append(
        f"- Incoming Callers ({len(context.callers)}): {', '.join(context.callers[:10]) or 'None'}"
    )
    lines.append(
        f"- Outgoing Callees ({len(context.callees)}): {', '.join(context.callees[:10]) or 'None'}"
    )
    lines.append(
        f"- Importers ({len(context.importers)}): {', '.join(context.importers[:10]) or 'None'}"
    )
    lines.append(
        f"- Imported Modules ({len(context.imports)}): {', '.join(context.imports[:10]) or 'None'}"
    )
    if context.inherits:
        lines.append(f"- Inherits From: {', '.join(context.inherits)}")
    if context.inherited_by:
        lines.append(f"- Inherited By: {', '.join(context.inherited_by)}")

    if context.evidence:
        lines.append(f"\nStatic Evidence Observations ({len(context.evidence)}):")
        for ev in context.evidence[:5]:
            eid = ev.get("id", "")
            origin = ev.get("origin", "SYNTAX")
            loc = ev.get("location")
            loc_str = ""
            if isinstance(loc, dict):
                p = loc.get("path")
                sl = loc.get("start_line")
                el = loc.get("end_line")
                if p and sl:
                    loc_str = f" at {p}:{sl}" + (f"-{el}" if el and el != sl else "")
            obs_kind = ev.get("observation_kind") or ""
            obs_desc = f" ({obs_kind})" if obs_kind else ""
            lines.append(f"- [{eid}] {origin}{obs_desc}{loc_str}")
        if len(context.evidence) > 5:
            lines.append(
                f"- ... and {len(context.evidence) - 5} more evidence records."
            )

    lines.append(
        "\nProvide an explanation covering: 1) Architectural Role, 2) Summary of Responsibilities, "
        "3) Coupling & Stability Analysis, and 4) Architectural Recommendations or Risks."
    )
    return "\n".join(lines)


class RuleBasedExplainer:
    """Deterministic, offline-first architectural explainer."""

    @staticmethod
    def explain(context: NodeContext, prompt: str | None = None) -> NodeExplanation:
        kind = context.kind.lower()
        has_computed_metrics = bool(context.metrics)
        fan_in = context.metrics.get("fan_in")
        if fan_in is None:
            fan_in = len(context.callers) + len(context.importers)
        fan_out = context.metrics.get("fan_out")
        if fan_out is None:
            fan_out = len(context.callees) + len(context.imports)
        instability = context.metrics.get("instability")
        in_cycle = bool(context.metrics.get("in_cycle", False))
        community_id = context.metrics.get("community_id")

        # 1. Determine Architectural Role
        if in_cycle:
            role = "Cyclic Dependency Hotspot"
        elif fan_in > 5 and fan_out <= 2:
            role = "Core Foundation / Shared Utility"
        elif fan_in == 0 and fan_out > 3:
            role = "Entrypoint / Orchestrator"
        elif fan_in > 3 and fan_out > 3:
            role = "Central Mediator / Hub"
        elif context.inherited_by and not context.inherits:
            role = "Abstract Base / Extension Point"
        elif kind in ("module", "package"):
            role = "Architectural Subsystem / Namespace"
        elif fan_in == 0 and fan_out == 0:
            role = "Isolated Leaf Component"
        else:
            role = f"{context.kind.capitalize()} Component"

        # 2. Synthesize Architectural Summary with canonical location
        if context.file_path:
            if context.line is not None:
                line_spec = f":{context.line}"
                if context.end_line is not None and context.end_line != context.line:
                    line_spec += f"-{context.end_line}"
                loc_str = f" in `{context.file_path}{line_spec}`"
            else:
                loc_str = f" in `{context.file_path}`"
        else:
            loc_str = ""

        if context.docstring:
            summary = (
                f"`{context.name}` is a {kind}{loc_str}. "
                f'Documented purpose: "{context.docstring.strip()}"'
            )
        else:
            summary = (
                f"`{context.name}` is a {kind}{loc_str} serving as a {role.lower()} "
                f"within the codebase."
            )

        # 3. Dependencies narrative
        dep_parts = []
        if context.callers:
            callers_preview = ", ".join(f"`{c}`" for c in context.callers[:5])
            if len(context.callers) > 5:
                callers_preview += f" (+{len(context.callers) - 5} more)"
            dep_parts.append(
                f"Invoked by {len(context.callers)} caller(s): {callers_preview}."
            )
        else:
            dep_parts.append("Has no recorded internal callers.")

        if context.callees:
            callees_preview = ", ".join(f"`{c}`" for c in context.callees[:5])
            if len(context.callees) > 5:
                callees_preview += f" (+{len(context.callees) - 5} more)"
            dep_parts.append(
                f"Delegates to {len(context.callees)} callee(s): {callees_preview}."
            )

        if context.importers:
            dep_parts.append(f"Imported by {len(context.importers)} module(s).")
        if context.imports:
            dep_parts.append(
                f"Depends on {len(context.imports)} external/internal module(s)."
            )

        dependencies_summary = " ".join(dep_parts)

        # 4. Metrics & Stability narrative
        if has_computed_metrics:
            metric_parts = [f"Fan-in: {fan_in}, Fan-out: {fan_out}."]
            if instability is not None:
                if instability < 0.3:
                    stability_desc = (
                        "highly stable (resilient to changes, heavily relied upon)"
                    )
                elif instability > 0.7:
                    stability_desc = "highly flexible / unstable (orchestrates dependencies, easily altered)"
                else:
                    stability_desc = "balanced coupling"
                metric_parts.append(
                    f"Instability index is {instability:.2f}, indicating {stability_desc}."
                )

            component_id = context.metrics.get("component_id")
            if component_id is not None:
                metric_parts.append(f"Component: #{component_id}.")

            if community_id is not None:
                metric_parts.append(
                    f"Assigned to architectural community cluster #{community_id}."
                )

            if "ca" in context.metrics or "ce" in context.metrics:
                ca = context.metrics.get("ca", 0)
                ce = context.metrics.get("ce", 0)
                cohesion = context.metrics.get("cohesion")
                coh_str = f", Cohesion: {cohesion:.2f}" if cohesion is not None else ""
                metric_parts.append(f"Module Architecture: Ca={ca}, Ce={ce}{coh_str}.")

            if in_cycle:
                metric_parts.append("Participates in a cyclic dependency.")
        else:
            metric_parts = [
                f"Observed connections: {len(context.callers) + len(context.importers)} incoming, "
                f"{len(context.callees) + len(context.imports)} outgoing (graph metrics not computed)."
            ]

        if context.runtime_stats:
            calls = context.runtime_stats.get("runtime_calls", 0)
            duration = context.runtime_stats.get("runtime_duration_ms", 0.0)
            metric_parts.append(
                f"Runtime profiling observed {calls} execution(s) spanning {duration:.2f} ms."
            )

        metrics_summary = " ".join(metric_parts)

        # 5. Actionable Recommendations & Risk Alerts
        recommendations: list[str] = []
        if in_cycle:
            recommendations.append(
                "Cycle Participation: This entity participates in a dependency cycle. "
                "Consider refactoring through dependency inversion or extracting common interfaces."
            )
        if fan_in > 8:
            recommendations.append(
                "High Fan-In: Many components depend on this entity. Breaking changes here will have a high blast radius."
            )
        if fan_out > 10:
            recommendations.append(
                "High Fan-Out: This entity depends on many external symbols. Consider breaking it down to adhere to Single Responsibility."
            )
        if instability is not None and instability < 0.2 and fan_out > 0:
            recommendations.append(
                "Stable Abstraction Principle: Ensure public interfaces remain backwards-compatible as modifications impact downstream consumers."
            )
        if not recommendations:
            recommendations.append(
                "Healthy architectural posture: No immediate coupling or cycle risks detected."
            )

        return NodeExplanation(
            node_id=context.node_id,
            name=context.name,
            kind=context.kind,
            role=role,
            summary=summary,
            dependencies_summary=dependencies_summary,
            metrics_summary=metrics_summary,
            recommendations=recommendations,
            prompt=prompt,
            provider="rule-based",
        )


class OpenAICompatibleExplainer:
    """Explainer using an OpenAI-compatible HTTP endpoint with rule-based fallback."""

    def __init__(
        self,
        api_base: str,
        api_key: str | None = None,
        model: str = "gpt-3.5-turbo",
        timeout: float = 6.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.timeout = timeout

    def explain(self, context: NodeContext, prompt: str) -> NodeExplanation:
        """Call external LLM API; fall back to RuleBasedExplainer on any error."""
        endpoint = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert code architect. Respond in valid JSON with keys: "
                        '"role" (string), "summary" (string), "dependencies_summary" (string), '
                        '"metrics_summary" (string), "recommendations" (list of strings).'
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        if not endpoint.startswith(("http://", "https://")):
            rule_fallback = RuleBasedExplainer.explain(context, prompt=prompt)
            return NodeExplanation(
                node_id=rule_fallback.node_id,
                name=rule_fallback.name,
                kind=rule_fallback.kind,
                role=rule_fallback.role,
                summary=rule_fallback.summary,
                dependencies_summary=rule_fallback.dependencies_summary,
                metrics_summary=rule_fallback.metrics_summary,
                recommendations=rule_fallback.recommendations,
                prompt=prompt,
                provider="rule-based (llm-fallback)",
            )

        try:
            req_data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            req = urllib.request.Request(  # noqa: S310
                endpoint, data=req_data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                if resp.status == 200:
                    raw_body = json.loads(resp.read().decode("utf-8"))
                    content = raw_body["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return NodeExplanation(
                        node_id=context.node_id,
                        name=context.name,
                        kind=context.kind,
                        role=parsed.get("role", "Component"),
                        summary=parsed.get("summary", ""),
                        dependencies_summary=parsed.get("dependencies_summary", ""),
                        metrics_summary=parsed.get("metrics_summary", ""),
                        recommendations=parsed.get("recommendations", []),
                        prompt=prompt,
                        provider=f"llm:{self.model}",
                    )
        except Exception:  # noqa: S110
            pass  # Fall back cleanly

        # Fallback to rule-based explanation
        rule_exp = RuleBasedExplainer.explain(context, prompt=prompt)
        return NodeExplanation(
            node_id=rule_exp.node_id,
            name=rule_exp.name,
            kind=rule_exp.kind,
            role=rule_exp.role,
            summary=rule_exp.summary,
            dependencies_summary=rule_exp.dependencies_summary,
            metrics_summary=rule_exp.metrics_summary,
            recommendations=rule_exp.recommendations,
            prompt=prompt,
            provider="rule-based (llm-fallback)",
        )


def explain_node(
    graph: dict[str, Any],
    node_id: str,
    provider: str = "auto",
) -> NodeExplanation:
    """Generate an architectural explanation for any node in an analysis graph."""
    context = extract_node_context(graph, node_id)
    prompt = format_explanation_prompt(context)

    api_base = os.getenv("CODESTRUCT_LLM_API_BASE")
    api_key = os.getenv("CODESTRUCT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("CODESTRUCT_LLM_MODEL", "llama3")

    if provider in ("llm", "auto") and api_base:
        explainer = OpenAICompatibleExplainer(
            api_base=api_base, api_key=api_key, model=model
        )
        return explainer.explain(context, prompt)

    return RuleBasedExplainer.explain(context, prompt=prompt)
