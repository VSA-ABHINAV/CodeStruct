"""Pydantic schemas for CodeStruct (Phase 2).

Defines the data contracts specified in Section 4 of CodeStruct_Project_Plan.md:
- Section 4.1: Graph JSON (nodes, edges, errors, summary)
- Section 4.2: Symbol Detail (id, name, kind, file_path, lineno, fan_in/out, incoming/outgoing)
- Section 4.3: API Request/Response models
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Section 4.1: Graph JSON Models
# ---------------------------------------------------------------------------

class Node(BaseModel):
    """A node in the code structure graph (module, class, function, or method)."""
    id: str = Field(..., description="Globally unique node id, e.g. 'sample_project.Animal.speak'")
    name: str = Field(..., description="Short symbol name, e.g. 'speak'")
    kind: Literal["module", "class", "function", "method"] = Field(
        ..., description="Node kind"
    )
    module: str = Field(..., description="Dotted module path, e.g. 'sample_project'")
    file_path: str = Field(..., description="Source file path relative to project_root")
    lineno: int = Field(..., description="1-based start line")
    end_lineno: int = Field(..., description="1-based end line")
    parent_id: Optional[str] = Field(
        None, description="Containing class id for a method, containing module id for top-level class/function, null for module"
    )
    docstring: Optional[str] = Field(None, description="Docstring or null")


class Edge(BaseModel):
    """A directed relationship edge between two nodes."""
    source: str = Field(..., description="Source node id")
    target: str = Field(..., description="Target node id")
    type: Literal["inherits", "defines", "constructs", "calls"] = Field(
        ..., description="Relationship type"
    )


class ParseError(BaseModel):
    """Information on a file that failed to parse."""
    file_path: str = Field(..., description="Path of the unparseable file")
    message: str = Field(..., description="Error message or exception details")


class GraphSummary(BaseModel):
    """Aggregate counts for the analyzed project graph."""
    node_count: int
    edge_count: int
    module_count: int
    class_count: int
    function_count: int
    method_count: int
    cache_hits: int = 0
    cache_misses: int = 0


class Graph(BaseModel):
    """Section 4.1: Core analysis output graph structure."""
    project_root: str
    generated_at: str
    nodes: List[Node]
    edges: List[Edge]
    errors: List[ParseError]
    summary: GraphSummary


# ---------------------------------------------------------------------------
# Section 4.2: Symbol Detail Models
# ---------------------------------------------------------------------------

class SymbolEdge(BaseModel):
    """Incoming or outgoing edge representation for a symbol."""
    id: str = Field(..., description="Opposite node id")
    name: str = Field(..., description="Opposite node short name")
    type: str = Field(..., description="Edge type: inherits, defines, constructs, or calls")


class SymbolDetail(BaseModel):
    """Section 4.2: Detailed symbol information for the Inspector panel."""
    id: str
    name: str
    kind: str
    file_path: str
    lineno: int
    end_lineno: int
    docstring: Optional[str] = None
    fan_in: int = Field(..., description="Count of incoming edges")
    fan_out: int = Field(..., description="Count of outgoing edges")
    incoming: List[SymbolEdge] = Field(default_factory=list)
    outgoing: List[SymbolEdge] = Field(default_factory=list)
    instability: float = Field(0.0, description="Martin's Instability metric: fan_out / (fan_in + fan_out)")


# ---------------------------------------------------------------------------
# Section 4.3: API Request & Response Models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Request body for POST /api/analyze."""
    project_path: str = Field(..., description="Path to the directory or file to analyze")
    force_refresh: bool = Field(False, description="If true, bypass cache and re-parse all files")


class OpenInEditorRequest(BaseModel):
    """Request body for POST /api/open_in_editor (Phase 12)."""
    file_path: str = Field(..., description="Path to the file to open in the system editor")


class OpenInEditorResponse(BaseModel):
    """Response body for POST /api/open_in_editor (Phase 12)."""
    launched: bool = Field(True, description="Whether the file was successfully launched")
    file_path: Optional[str] = Field(None, description="Resolved file path launched")


class SourceResponse(BaseModel):
    """Response body for GET /api/source."""
    html: str = Field(..., description="Pygments-highlighted HTML fragment")
    start: int = Field(..., description="Start line number")
    end: int = Field(..., description="End line number")


class ChatRequest(BaseModel):
    """Request body for POST /api/qwen/chat (Phase 8)."""
    message: str
    context_symbol_id: Optional[str] = None


class ImpactedSymbol(BaseModel):
    """An impacted symbol reached during change-impact BFS walk (Phase 15)."""
    id: str = Field(..., description="Impacted symbol node ID")
    name: str = Field(..., description="Short name of impacted symbol")
    depth: int = Field(..., description="Shortest BFS distance from starting symbol")
    via_edge_type: str = Field(..., description="Relationship type traversed to reach this symbol")


class ImpactResponse(BaseModel):
    """Response body for GET /api/impact/{node_id} (Phase 15)."""
    symbol_id: str
    max_depth: int
    impacted: List[ImpactedSymbol]


class ChatResponse(BaseModel):
    """Response body for POST /api/qwen/chat (Phase 8)."""
    reply: str


class PatternMatch(BaseModel):
    """Detected design pattern match (Phase 13)."""
    pattern: Literal["Singleton", "Factory", "Observer"] = Field(..., description="Detected design pattern name")
    symbol_id: str = Field(..., description="ID of the matching symbol (class or function)")
    evidence: str = Field(..., description="Exact AST heuristic evidence for this match")


class PatternsResponse(BaseModel):
    """Response body for GET /api/patterns (Phase 13)."""
    patterns: List[PatternMatch] = Field(default_factory=list, description="List of detected design pattern matches")

