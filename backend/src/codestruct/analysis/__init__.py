"""Safe Python source discovery, syntax extraction, dynamic tracing, and semantic explanations."""

from .dynamic_tracer import (
    DynamicTracer,
    RuntimeCallEvent,
    RuntimeTraceResult,
    merge_runtime_trace_into_graph,
    trace_call,
)
from .llm_summary import (
    ExplanationClaim,
    ExplanationProvider,
    FakeExplanationProvider,
    LLMExplanationPayload,
    NodeContext,
    NodeExplanation,
    OpenAICompatibleExplainer,
    RuleBasedExplainer,
    explain_node,
    extract_node_context,
    format_explanation_prompt,
    validate_evidence_references,
)
from .policy import AnalysisPolicy
from .python_parser import FileParseCache, PythonAstParser, parse_project
from .retrieval import (
    CanonicalEvidenceItem,
    RetrievedEvidenceContext,
    SourceSnippet,
    is_safe_path_contained,
    is_secret_or_sensitive,
    retrieve_evidence_context,
    retrieve_source_snippet,
)
from .scanner import scan_project

__all__ = [
    "AnalysisPolicy",
    "CanonicalEvidenceItem",
    "DynamicTracer",
    "ExplanationClaim",
    "ExplanationProvider",
    "FakeExplanationProvider",
    "FileParseCache",
    "LLMExplanationPayload",
    "NodeContext",
    "NodeExplanation",
    "OpenAICompatibleExplainer",
    "PythonAstParser",
    "RetrievedEvidenceContext",
    "RuleBasedExplainer",
    "RuntimeCallEvent",
    "RuntimeTraceResult",
    "SourceSnippet",
    "explain_node",
    "extract_node_context",
    "format_explanation_prompt",
    "is_safe_path_contained",
    "is_secret_or_sensitive",
    "merge_runtime_trace_into_graph",
    "parse_project",
    "retrieve_evidence_context",
    "retrieve_source_snippet",
    "scan_project",
    "trace_call",
    "validate_evidence_references",
]
