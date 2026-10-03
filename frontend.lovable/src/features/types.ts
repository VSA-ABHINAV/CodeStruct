export type NodeKind = string;
export type EdgeKind = string;
export type ResolutionStatus = string;
export type Confidence = string;

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
  attributes: Record<string, unknown>;
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
  attributes: Record<string, unknown>;
};

export type Evidence = {
  evidence_id: string;
  origin: string;
  observation_kind: string;
  location: SourceLocation | null;
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
  metadata?: { graph_id: string; analysis_id?: string; [key: string]: unknown };
  page?: { next_cursor: string | null; partial_load: boolean; total_nodes: number; total_edges: number; returned_nodes: number; returned_edges: number };
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
  description: string | null;
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
  | "computing_metrics"
  | "cancellation_requested"
  | "completed"
  | "partially_completed"
  | "cache_hit"
  | "cancelled"
  | "failed";

export type AnalysisJob = {
  analysis_id: string;
  state: JobState;
  terminal: boolean;
  progress: { phase: string; percent: number | null; message_code: string };
  partial: boolean;
  cache_hit: boolean;
  diagnostics_summary: { info: number; warning: number; error: number };
  links?: { graph: string | null };
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
  status: (analysisId: string, signal?: AbortSignal) => Promise<AnalysisJob>;
  cancel: (analysisId: string) => Promise<AnalysisJob>;
  mode: "demo" | "live";
  listProjects: () => Promise<Project[]>;
  analyze: (projectId: string, refresh?: boolean, signal?: AbortSignal) => Promise<AnalysisJob>;
  getGraph: (analysisId: string, cursor?: string | null, signal?: AbortSignal) => Promise<GraphResult>;
  getDiagnostics: (analysisId: string, signal?: AbortSignal) => Promise<Diagnostic[]>;
  explain: (analysisId: string, nodeId: string) => Promise<NodeExplanation>;
  exportDot: (analysisId: string) => Promise<Blob>;
  navigate: (path: string, line: number, column?: number, sessionToken?: string) => Promise<{ status: string }>;
};