import type {
  Diagnostic,
  GraphEdge,
  GraphNode,
  GraphResult,
  NodeExplanation,
  Project,
} from "./types";

export const demoProjects: Project[] = [
  {
    id: "sample_service",
    display_name: "Sample Service",
    description: "Core backend service workspace",
    available: true,
  },
  {
    id: "sample_client",
    display_name: "Sample Client",
    description: "Frontend and consumer utilities",
    available: true,
  },
];

export const demoNodes: GraphNode[] = [
  {
    id: "node_pkg_module",
    kind: "module",
    name: "module",
    qualified_name: "pkg.module",
    parent_id: null,
    module_id: null,
    file_id: null,
    location: {
      source_unit_id: "src_pkg_module",
      path: "pkg/module.py",
      start_line: 1,
      start_column: 1,
      end_line: 35,
      end_column: 1,
    },
    modifiers: [],
    attributes: { docstring: "Service module implementation." },
  },
  {
    id: "node_pkg_service_class",
    kind: "class",
    name: "ServiceHandler",
    qualified_name: "pkg.module.ServiceHandler",
    parent_id: "node_pkg_module",
    module_id: "node_pkg_module",
    file_id: null,
    location: {
      source_unit_id: "src_pkg_module",
      path: "pkg/module.py",
      start_line: 10,
      start_column: 1,
      end_line: 30,
      end_column: 1,
    },
    modifiers: [],
    attributes: { methods_count: "2" },
  },
  {
    id: "node_pkg_service_process_fn",
    kind: "function",
    name: "process_request",
    qualified_name: "pkg.module.ServiceHandler.process_request",
    parent_id: "node_pkg_service_class",
    module_id: "node_pkg_module",
    file_id: null,
    location: {
      source_unit_id: "src_pkg_module",
      path: "pkg/module.py",
      start_line: 15,
      start_column: 5,
      end_line: 25,
      end_column: 1,
    },
    modifiers: [],
    attributes: { parameters: "self, payload" },
  },
];

export const demoEdges: GraphEdge[] = [
  {
    id: "edge_01",
    kind: "defines",
    source_id: "node_pkg_module",
    target_id: "node_pkg_service_class",
    target_reference: null,
    resolution_status: "resolved",
    confidence: "high",
    confidence_reason: null,
    candidate_ids: [],
    evidence_ids: ["ev_01"],
    occurrence_count: 1,
    diagnostic_ids: [],
    attributes: {},
  },
  {
    id: "edge_02",
    kind: "defines",
    source_id: "node_pkg_service_class",
    target_id: "node_pkg_service_process_fn",
    target_reference: null,
    resolution_status: "resolved",
    confidence: "high",
    confidence_reason: null,
    candidate_ids: [],
    evidence_ids: ["ev_02"],
    occurrence_count: 1,
    diagnostic_ids: [],
    attributes: {},
  },
];

export const demoDiagnostics: Diagnostic[] = [
  {
    id: "d_demo_locationless",
    code: "IMPORT_NOT_RESOLVED",
    severity: "warning",
    phase: "resolving",
    message: "A referenced import could not be resolved in the authorized project.",
    location: null,
    entity_id: null,
    edge_id: null,
    recoverable: true,
    consequence: "relationship_omitted",
    suggested_action: "Make the dependency available to the analyzer and refresh.",
  },
];

export const demoGraph: GraphResult = {
  graph_id: "graph_canonical_01",
  schema_version: "1.0.0",
  summary: {
    source_units_total: 1,
    nodes_total: 3,
    edges_total: 2,
    evidence_total: 2,
    diagnostics_total: 1,
    nodes_by_kind: { module: 1, class: 1, function: 1 },
    edges_by_kind: { defines: 2 },
    edges_by_resolution: { resolved: 2 },
    edges_by_confidence: { high: 2 },
  },
  nodes: demoNodes,
  edges: demoEdges,
  evidence: [
    {
      evidence_id: "ev_01",
      origin: "source_ast",
      observation_kind: "class_definition",
      location: { ...demoNodes[1].location! },
      excerpt: "class ServiceHandler:",
      explanation: "AST class definition node at line 10",
      expression: null,
    },
    {
      evidence_id: "ev_02",
      origin: "source_ast",
      observation_kind: "function_definition",
      location: { ...demoNodes[2].location! },
      excerpt: "def process_request(self, payload):",
      explanation: "AST function definition node at line 15",
      expression: null,
    },
  ],
  diagnostics: demoDiagnostics,
  partial_load: false,
};

export const demoExplanation: NodeExplanation = {
  node_id: "node_pkg_service_process_fn",
  name: "process_request",
  kind: "function",
  role: "Entrypoint Handler",
  summary: "Handles incoming request processing and coordinates business logic execution.",
  dependencies_summary: "Depends on ServiceHandler instance and incoming request payload.",
  metrics_summary: "Coupling: In-degree 1, Out-degree 0.",
  recommendations: ["Ensure input validation on payload before business processing."],
  provider: "rule-based",
};

export function graphToDot(graph: GraphResult) {
  const nodes = graph.nodes.map((node) => `  "${node.id}" [label="${node.name}\\n${node.kind}"];`);
  const edges = graph.edges
    .filter((edge) => edge.target_id)
    .map((edge) => `  "${edge.source_id}" -> "${edge.target_id}" [label="${edge.kind}"];`);
  return `digraph CodeStruct {\n${nodes.join("\n")}\n${edges.join("\n")}\n}`;
}