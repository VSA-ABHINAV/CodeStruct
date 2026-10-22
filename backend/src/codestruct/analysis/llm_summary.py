"""Semantic explanation and LLM/RAG context summarizer for architecture nodes.

Provides deterministic, offline-first architectural explanations analyzing coupling,
centrality, caller/callee networks, runtime traces, and structural risks. Supports
optional pluggable LLM providers with strict Pydantic response validation, canonical
evidence verification, claim provenance labeling (LLM_INFERRED), and automatic
deterministic fallback to rule-based synthesis.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .retrieval import (
    RetrievedEvidenceContext,
    SourceSnippet,
    retrieve_evidence_context,
)


class ExplanationClaim(BaseModel):
    """A single architectural claim or interpretation with truthful provenance and evidence citations."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=4000)
    claim_type: str = Field(default="architectural_interpretation", max_length=128)
    evidence_ids: list[str] = Field(default_factory=list)
    provenance: Literal[
        "LLM_INFERRED", "RULE_SYNTHESIZED", "STATIC_AST", "RUNTIME_OBSERVED"
    ] = "LLM_INFERRED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "claim_type": self.claim_type,
            "evidence_ids": list(self.evidence_ids),
            "provenance": self.provenance,
        }


class LLMExplanationPayload(BaseModel):
    """Strict Pydantic schema for external LLM provider responses.

    Enforces exact types and forbids extra fields to prevent unvalidated output.
    """

    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=4000)
    dependencies_summary: str = Field(min_length=1, max_length=4000)
    metrics_summary: str = Field(min_length=1, max_length=4000)
    recommendations: list[str] = Field(default_factory=list, max_length=50)
    evidence_references: list[str] = Field(default_factory=list, max_length=100)
    claims: list[ExplanationClaim] = Field(default_factory=list, max_length=50)


def validate_evidence_references(
    cited_ids: list[str],
    canonical_evidence_ids: set[str],
) -> tuple[bool, list[str], list[str]]:
    """Validate all cited evidence references against canonical evidence set.

    Returns (is_valid, valid_ids, invalid_ids).
    """
    valid: list[str] = []
    invalid: list[str] = []
    for cid in cited_ids:
        if cid in canonical_evidence_ids:
            if cid not in valid:
                valid.append(cid)
        else:
            if cid not in invalid:
                invalid.append(cid)
    return (len(invalid) == 0, valid, invalid)


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
    source_snippet: SourceSnippet | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    importers: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    inherits: list[str] = field(default_factory=list)
    inherited_by: list[str] = field(default_factory=list)
    runtime_stats: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    canonical_evidence_ids: set[str] = field(default_factory=set)


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
    fallback_used: bool = False
    fallback_reason: str | None = None
    retrieved_evidence_ids: list[str] = field(default_factory=list)
    cited_evidence_ids: list[str] = field(default_factory=list)
    claims: list[ExplanationClaim] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "kind": self.kind,
            "role": self.role,
            "summary": self.summary,
            "dependencies_summary": self.dependencies_summary,
            "metrics_summary": self.metrics_summary,
            "recommendations": list(self.recommendations),
            "prompt": self.prompt,
            "provider": self.provider,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "retrieved_evidence_ids": list(self.retrieved_evidence_ids),
            "cited_evidence_ids": list(self.cited_evidence_ids),
            "claims": [c.to_dict() for c in self.claims],
        }


def extract_node_context(
    graph: dict[str, Any],
    node_id: str,
    project_root: str | Path | None = None,
) -> NodeContext:
    """Extract full structural context, metrics, evidence, and relationships for a node."""
    retrieved = retrieve_evidence_context(
        graph,
        node_id,
        project_root=project_root,
    )

    # Convert CanonicalEvidenceItems to dicts for backward compatibility
    evidence_dicts: list[dict[str, Any]] = [
        {
            "id": ev.id,
            "origin": ev.origin,
            "observation_kind": ev.observation_kind,
            "location": ev.location,
            "excerpt": ev.excerpt,
            "explanation": ev.explanation,
            "observed_text_hash": ev.observed_text_hash,
            "expression": ev.expression,
        }
        for ev in retrieved.evidence_items
    ]

    return NodeContext(
        node_id=retrieved.node_id,
        name=retrieved.name,
        qualified_name=retrieved.qualified_name,
        kind=retrieved.kind,
        file_path=retrieved.file_path,
        line=retrieved.line,
        end_line=retrieved.end_line,
        docstring=retrieved.docstring,
        source_snippet=retrieved.source_snippet,
        metrics=retrieved.metrics,
        callers=retrieved.callers,
        callees=retrieved.callees,
        importers=retrieved.importers,
        imports=retrieved.imports,
        inherits=retrieved.inherits,
        inherited_by=retrieved.inherited_by,
        runtime_stats=retrieved.runtime_stats,
        evidence=evidence_dicts,
        canonical_evidence_ids=retrieved.canonical_evidence_ids,
    )


def format_explanation_prompt(context: NodeContext | RetrievedEvidenceContext) -> str:
    """Format an LLM prompt describing the architecture context of a node with evidence citations."""
    file_loc = context.file_path or "unknown"
    if context.line is not None:
        file_loc += f":{context.line}"
        if context.end_line is not None and context.end_line != context.line:
            file_loc += f"-{context.end_line}"
    else:
        file_loc += ":?"

    lines = [
        "You are an expert Python software architect analyzing a codebase architecture graph.",
        "Analyze the following code entity and provide a clear, concise architectural summary.",
        "Base all interpretations strictly on the provided evidence.",
        "",
        f"Entity: {context.name} ({context.kind})",
        f"Qualified Name: {context.qualified_name}",
        f"File: {file_loc}",
    ]
    if context.docstring:
        lines.append(f"Docstring: {context.docstring.strip()}")

    if context.source_snippet and context.source_snippet.content:
        lines.append(
            f"\nBounded Source Code Snippet ({context.source_snippet.file_path}:{context.source_snippet.start_line}-{context.source_snippet.end_line}):"
        )
        lines.append("```python")
        lines.append(context.source_snippet.content.rstrip())
        lines.append("```")
        if context.source_snippet.is_truncated:
            lines.append("Note: Source snippet was bounded by size limit.")

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

    # Evidence items
    evidence_list: list[dict[str, Any]] = []
    if isinstance(context, NodeContext):
        evidence_list = context.evidence
    elif hasattr(context, "evidence_items"):
        evidence_list = [
            {
                "id": item.id,
                "origin": item.origin,
                "observation_kind": item.observation_kind,
            }
            for item in context.evidence_items
        ]

    if evidence_list:
        lines.append(f"\nCanonical Evidence Observations ({len(evidence_list)}):")
        for ev in evidence_list[:10]:
            eid = ev.get("id", "")
            origin = ev.get("origin", "STATIC_AST")
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
        if len(evidence_list) > 10:
            lines.append(f"- ... and {len(evidence_list) - 10} more evidence records.")

    lines.append("\nStrict Output Requirements:")
    lines.append("Respond ONLY with valid JSON conforming to this schema:")
    lines.append(
        "{\n"
        '  "role": "<architectural role>",\n'
        '  "summary": "<architectural summary>",\n'
        '  "dependencies_summary": "<dependencies narrative>",\n'
        '  "metrics_summary": "<metrics and stability narrative>",\n'
        '  "recommendations": ["<recommendation 1>", ...],\n'
        '  "evidence_references": ["<evidence_id_1>", ...],\n'
        '  "claims": [\n'
        "    {\n"
        '      "statement": "<specific claim>",\n'
        '      "claim_type": "architectural_interpretation",\n'
        '      "evidence_ids": ["<evidence_id_1>"],\n'
        '      "provenance": "LLM_INFERRED"\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    lines.append(
        "IMPORTANT: Do NOT hallucinate evidence IDs. Only cite IDs present in the Canonical Evidence Observations list."
    )
    lines.append("All claims must be labeled with provenance 'LLM_INFERRED'.")

    return "\n".join(lines)


class RuleBasedExplainer:
    """Deterministic, offline-first architectural explainer."""

    @staticmethod
    def explain(
        context: NodeContext | RetrievedEvidenceContext,
        prompt: str | None = None,
        fallback_used: bool = False,
        fallback_reason: str | None = None,
        provider_name: str = "rule-based",
    ) -> NodeExplanation:
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

        # Friendly kind formatting
        if kind == "unresolved_symbol":
            friendly_kind = "unresolved reference"
        elif kind == "external_module":
            friendly_kind = "external module"
        else:
            friendly_kind = kind.replace("_", " ")

        kind_article = "an" if friendly_kind[0] in "aeiou" else "a"
        role_article = "an" if role[0].lower() in "aeiou" else "a"

        if kind == "unresolved_symbol":
            summary = (
                f"`{context.name}` is an unresolved reference{loc_str} with no local AST definition."
            )
        elif context.docstring:
            summary = (
                f"`{context.name}` is {kind_article} {friendly_kind}{loc_str}. "
                f'Documented purpose: "{context.docstring.strip()}"'
            )
        else:
            summary = (
                f"`{context.name}` is {kind_article} {friendly_kind}{loc_str} serving as {role_article} {role.lower()} "
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
                f"{len(context.callees) + len(context.imports)} outgoing."
            ]

        if context.runtime_stats:
            calls = (
                context.runtime_stats.get("runtime_calls")
                or context.runtime_stats.get("runtime_invocations")
                or 0
            )
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

        # Build claims with deterministic provenance
        canon_ids = sorted(context.canonical_evidence_ids)
        claims: list[ExplanationClaim] = [
            ExplanationClaim(
                statement=summary,
                claim_type="architectural_summary",
                evidence_ids=canon_ids,
                provenance="RULE_SYNTHESIZED",
            ),
            ExplanationClaim(
                statement=dependencies_summary,
                claim_type="dependencies_narrative",
                evidence_ids=canon_ids,
                provenance="RULE_SYNTHESIZED",
            ),
            ExplanationClaim(
                statement=metrics_summary,
                claim_type="metrics_narrative",
                evidence_ids=canon_ids,
                provenance="RULE_SYNTHESIZED",
            ),
        ]
        for rec in recommendations:
            claims.append(
                ExplanationClaim(
                    statement=rec,
                    claim_type="recommendation",
                    evidence_ids=canon_ids,
                    provenance="RULE_SYNTHESIZED",
                )
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
            provider=provider_name if fallback_used else "rule-based",
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            retrieved_evidence_ids=canon_ids,
            cited_evidence_ids=canon_ids,
            claims=claims,
        )


class ExplanationProvider(Protocol):
    """Protocol for semantic explanation providers."""

    def generate_explanation(
        self,
        prompt: str,
        retrieval_context: NodeContext | RetrievedEvidenceContext,
    ) -> LLMExplanationPayload:
        """Generate structured explanation payload from prompt and retrieved context."""
        ...


class FakeExplanationProvider:
    """Injected deterministic test fake provider ensuring zero remote/paid API calls."""

    def __init__(
        self,
        payload: dict[str, Any] | LLMExplanationPayload | None = None,
        error: Exception | None = None,
        name: str = "fake-llm",
    ) -> None:
        self.payload = payload
        self.error = error
        self.name = name
        self.calls: list[dict[str, Any]] = []

    def generate_explanation(
        self,
        prompt: str,
        retrieval_context: NodeContext | RetrievedEvidenceContext,
    ) -> LLMExplanationPayload:
        self.calls.append(
            {
                "prompt": prompt,
                "node_id": retrieval_context.node_id,
            }
        )
        if self.error:
            raise self.error
        if isinstance(self.payload, LLMExplanationPayload):
            return self.payload
        if isinstance(self.payload, dict):
            return LLMExplanationPayload.model_validate(self.payload)
        raise ValueError(
            "FakeExplanationProvider has neither valid payload nor error configured."
        )


class OpenAICompatibleExplainer:
    """Explainer using an OpenAI-compatible HTTP endpoint with strict validation and rule fallback."""

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

    def generate_explanation(
        self,
        prompt: str,
        retrieval_context: NodeContext | RetrievedEvidenceContext,
    ) -> LLMExplanationPayload:
        endpoint = f"{self.api_base}/chat/completions"
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError(f"Invalid API base URL: {self.api_base}")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert Python software architect. Respond strictly with valid JSON "
                        "matching the requested schema. Base claims on provided evidence and cite canonical IDs."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        req_data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(  # noqa: S310
            endpoint, data=req_data, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}: {resp.reason}")
            raw_body = json.loads(resp.read().decode("utf-8"))

        content = raw_body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        # Strict Pydantic model validation
        return LLMExplanationPayload.model_validate(parsed)

    def explain(
        self,
        context: NodeContext | RetrievedEvidenceContext,
        prompt: str,
    ) -> NodeExplanation:
        """Call external LLM API; strictly validate and fall back to RuleBasedExplainer on any error."""
        try:
            payload = self.generate_explanation(prompt, context)
            return _build_validated_explanation(
                payload=payload,
                context=context,
                prompt=prompt,
                provider_name=f"llm:{self.model}",
            )
        except Exception as err:
            return RuleBasedExplainer.explain(
                context,
                prompt=prompt,
                fallback_used=True,
                fallback_reason=f"LLM provider failed: {err}",
                provider_name="rule-based (llm-fallback)",
            )


def _build_validated_explanation(
    payload: LLMExplanationPayload,
    context: NodeContext | RetrievedEvidenceContext,
    prompt: str,
    provider_name: str,
) -> NodeExplanation:
    """Validate evidence citations, enforce LLM_INFERRED labeling, and construct NodeExplanation."""
    # Collect all cited evidence IDs from references and claims
    all_cited: list[str] = list(payload.evidence_references)
    for c in payload.claims:
        all_cited.extend(c.evidence_ids)

    # Validate against canonical evidence set
    is_valid, valid_ids, invalid_ids = validate_evidence_references(
        all_cited,
        context.canonical_evidence_ids,
    )

    if not is_valid:
        # Invalid / hallucinated evidence IDs trigger deterministic fallback
        return RuleBasedExplainer.explain(
            context,
            prompt=prompt,
            fallback_used=True,
            fallback_reason=f"Provider cited invalid or unknown evidence IDs: {sorted(invalid_ids)}",
            provider_name="rule-based (llm-fallback)",
        )

    # Construct claims ensuring strictly LLM_INFERRED provenance
    claims: list[ExplanationClaim] = []
    if payload.claims:
        for c in payload.claims:
            claims.append(
                ExplanationClaim(
                    statement=c.statement,
                    claim_type=c.claim_type,
                    evidence_ids=c.evidence_ids,
                    provenance="LLM_INFERRED",
                )
            )
    else:
        # Synthesize claims from summaries with explicit LLM_INFERRED provenance
        claims.append(
            ExplanationClaim(
                statement=payload.summary,
                claim_type="architectural_summary",
                evidence_ids=valid_ids,
                provenance="LLM_INFERRED",
            )
        )
        claims.append(
            ExplanationClaim(
                statement=payload.dependencies_summary,
                claim_type="dependencies_interpretation",
                evidence_ids=valid_ids,
                provenance="LLM_INFERRED",
            )
        )
        claims.append(
            ExplanationClaim(
                statement=payload.metrics_summary,
                claim_type="metrics_interpretation",
                evidence_ids=valid_ids,
                provenance="LLM_INFERRED",
            )
        )
        for rec in payload.recommendations:
            claims.append(
                ExplanationClaim(
                    statement=rec,
                    claim_type="recommendation",
                    evidence_ids=valid_ids,
                    provenance="LLM_INFERRED",
                )
            )

    return NodeExplanation(
        node_id=context.node_id,
        name=context.name,
        kind=context.kind,
        role=payload.role,
        summary=payload.summary,
        dependencies_summary=payload.dependencies_summary,
        metrics_summary=payload.metrics_summary,
        recommendations=payload.recommendations,
        prompt=prompt,
        provider=provider_name,
        fallback_used=False,
        fallback_reason=None,
        retrieved_evidence_ids=sorted(context.canonical_evidence_ids),
        cited_evidence_ids=valid_ids,
        claims=claims,
    )


def explain_node(
    graph: dict[str, Any],
    node_id: str,
    provider: str = "rule-based",
    project_root: str | Path | None = None,
    custom_provider: ExplanationProvider | None = None,
) -> NodeExplanation:
    """Generate an architectural explanation for any node in an analysis graph.

    Adheres strictly to explicit provider opt-in:
    - 'rule-based' (default): Runs deterministic offline rule-based explainer without provider calls.
    - 'llm' or 'auto': Attempts external or custom LLM provider; on failure, timeout, invalid schema,
      or hallucinated evidence references, cleanly falls back to rule-based explanation with fallback metadata.
    """
    context = extract_node_context(graph, node_id, project_root=project_root)
    prompt = format_explanation_prompt(context)

    # 1. Explicit Rule-Based Opt-In: always offline deterministic
    if provider == "rule-based":
        return RuleBasedExplainer.explain(context, prompt=prompt, fallback_used=False)

    # 2. Custom injected provider (used in tests and decoupled deployments)
    if custom_provider is not None:
        try:
            payload = custom_provider.generate_explanation(prompt, context)
            provider_name = getattr(custom_provider, "name", "custom-llm")
            return _build_validated_explanation(
                payload=payload,
                context=context,
                prompt=prompt,
                provider_name=provider_name,
            )
        except Exception as err:
            return RuleBasedExplainer.explain(
                context,
                prompt=prompt,
                fallback_used=True,
                fallback_reason=f"Custom provider failed: {type(err).__name__}: {err}",
                provider_name="rule-based (llm-fallback)",
            )

    # 3. Environment-configured LLM provider
    api_base = os.getenv("CODESTRUCT_LLM_API_BASE")
    api_key = os.getenv("CODESTRUCT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("CODESTRUCT_LLM_MODEL", "llama3")

    if api_base:
        explainer = OpenAICompatibleExplainer(
            api_base=api_base,
            api_key=api_key,
            model=model,
        )
        return explainer.explain(context, prompt)

    # 4. No LLM configured: fallback behavior
    if provider == "llm":
        return RuleBasedExplainer.explain(
            context,
            prompt=prompt,
            fallback_used=True,
            fallback_reason="LLM provider requested but not configured (CODESTRUCT_LLM_API_BASE unset)",
            provider_name="rule-based (llm-fallback)",
        )

    # 'auto' without LLM configured cleanly defaults to rule-based
    return RuleBasedExplainer.explain(
        context, prompt=prompt, fallback_used=False, provider_name="rule-based"
    )
