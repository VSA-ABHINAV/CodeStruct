export type NodeKind = "module" | "class" | "function";
export type EdgeKind = "defines" | "imports" | "inherits" | "calls";
export type ResolutionStatus = "resolved" | "unresolved" | "ambiguous";
export type Confidence = "high" | "medium" | "low";

export type SourceLocation = {
  source_unit_id: string;
  path: string;
  start_line: number | null;
  start_column: number | null;
  end_line: number | null;
  end_column: number | null;
};

export type GraphNode = {
  id: string;
  kind: NodeKind;
  name: string;
  qualified_name: string;
  parent_id: string | null;
  module_id: string | null;
  file_id: string | null;
  location: SourceLocation | null;
  modifiers: string[];
  attributes: Record<string, string>;
};

export type GraphEdge = {
  id: string;
  kind: EdgeKind;
  source_id: string;
  target_id: string | null;
  target_reference: string | null;
  resolution_status: ResolutionStatus;
  confidence: Confidence;
  confidence_reason: string | null;
  candidate_ids: string[];
  evidence_ids: string[];
  occurrence_count: number;
  diagnostic_ids: string[];
  attributes: Record<string, string>;
};

export type Evidence = {
  evidence_id: string;
  origin: string;
  observation_kind: string;
  location: SourceLocation;
  excerpt: string | null;
  explanation: string | null;
  expression: string | null;
};

export type Diagnostic = {
  id: string;
  code: string;
  severity: "info" | "warning" | "error";
  phase: string;
  message: string;
  location: SourceLocation | null;
  entity_id: string | null;
  edge_id: string | null;
  recoverable: boolean;
  consequence: string;
  suggested_action: string | null;
};

export type GraphSummary = {
  source_units_total: number;
  nodes_total: number;
  edges_total: number;
  evidence_total: number;
  diagnostics_total: number;
  nodes_by_kind: Record<string, number>;
  edges_by_kind: Record<string, number>;
  edges_by_resolution: Record<string, number>;
  edges_by_confidence: Record<string, number>;
};

export type GraphResult = {
  graph_id: string;
  schema_version: string;
  summary: GraphSummary;
  nodes: GraphNode[];
  edges: GraphEdge[];
  evidence: Evidence[];
  diagnostics: Diagnostic[];
  partial_load: boolean;
};

export type Project = {
  id: string;
  display_name: string;
  description: string;
  available: boolean;
};

export type JobState =
  | "submitted"
  | "validating"
  | "queued"
  | "scanning"
  | "parsing"
  | "resolving"
  | "building_graph"
  | "completed"
  | "partially_completed"
  | "cache_hit"
  | "cancelled"
  | "failed";

export type AnalysisJob = {
  analysis_id: string;
  state: JobState;
  terminal: boolean;
  progress: { phase: string; percent: number; message_code: string };
  partial: boolean;
  cache_hit: boolean;
  diagnostics_summary: { info: number; warning: number; error: number };
};

export type NodeExplanation = {
  node_id: string;
  name: string;
  kind: string;
  role: string;
  summary: string;
  dependencies_summary: string;
  metrics_summary: string;
  recommendations: string[];
  provider: string;
};

export type Transport = {
  mode: "demo" | "live";
  listProjects: () => Promise<Project[]>;
  analyze: (projectId: string, refresh?: boolean) => Promise<AnalysisJob>;
  getGraph: (analysisId: string) => Promise<GraphResult>;
  getDiagnostics: (analysisId: string) => Promise<Diagnostic[]>;
  explain: (analysisId: string, nodeId: string) => Promise<NodeExplanation>;
  exportDot: (analysisId: string) => Promise<Blob>;
  navigate: (path: string, line: number, column?: number) => Promise<{ status: string }>;
};