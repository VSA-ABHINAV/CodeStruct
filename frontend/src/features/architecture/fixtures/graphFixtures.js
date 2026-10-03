const location = (path, line = 1) => ({ source_unit_id: `file-${path}`, path, start_line: line, start_column: 1, end_line: line, end_column: 8 })
const node = (id, kind, name, qualifiedName, path = null, parentId = null) => ({ id, kind, name, qualified_name: qualifiedName, parent_id: parentId, module_id: null, file_id: path ? `file-${path}` : null, location: path ? location(path) : null, modifiers: [], attributes: {} })
const edge = (id, kind, source, target, status = 'resolved', reference = null, attributes = {}) => ({ id, kind, source_id: source, target_id: target, target_reference: reference, resolution_status: status, confidence: status === 'resolved' ? 'exact' : 'unknown', confidence_reason: status === 'resolved' ? 'EXACT_STATIC_TARGET' : 'NO_SUPPORTED_STATIC_TARGET', candidate_ids: [], evidence_ids: [`v-${id}`], occurrence_count: 1, diagnostic_ids: status === 'resolved' ? [] : [`d-${id}`], attributes })
const evidence = (id, path = 'app/main.py') => ({ evidence_id: `v-${id}`, origin: 'source_ast', observation_kind: 'fixture', location: location(path), observed_text_hash: null, excerpt: null, explanation: 'Fixture syntax evidence.', expression: null })

export const smallGraph = {
  schema_version: '1.0.0', metadata: { partial: false }, summary: {},
  nodes: [
    node('n-project', 'project', 'Demo', 'project'),
    node('n-package', 'package', 'app', 'app', 'app/__init__.py', 'n-project'),
    node('n-module', 'module', 'main', 'app.main', 'app/main.py', 'n-package'),
    node('n-class', 'class', 'Service', 'app.main.Service', 'app/main.py', 'n-module'),
    node('n-method', 'method', 'run', 'app.main.Service.run', 'app/main.py', 'n-class'),
  ],
  edges: [edge('e-contains', 'contains', 'n-project', 'n-package', 'not_applicable'), edge('e-defines', 'defines', 'n-module', 'n-class', 'not_applicable'), edge('e-call', 'calls', 'n-method', 'n-class')],
  evidence: [evidence('e-contains', 'app/__init__.py'), evidence('e-defines'), evidence('e-call')], diagnostics: [],
}

export const partialGraph = {
  ...smallGraph,
  metadata: { partial: true, partial_reasons: ['file_parse_failure'] },
  diagnostics: [{ id: 'd-syntax', code: 'FILE_SYNTAX_ERROR', severity: 'error', phase: 'parsing', message: 'A Python file contains invalid syntax.', location: location('app/broken.py', 4), entity_id: 'n-module', edge_id: null, recoverable: true, consequence: 'partial', suggested_action: null, details: {} }],
}

export const circularGraph = {
  ...smallGraph,
  nodes: [...smallGraph.nodes, node('n-other', 'module', 'other', 'app.other', 'app/other.py', 'n-package')],
  edges: [...smallGraph.edges, edge('e-forward', 'imports', 'n-module', 'n-other', 'resolved', null, { import_kind: 'module' }), edge('e-back', 'imports', 'n-other', 'n-module', 'resolved', null, { import_kind: 'module' })],
  evidence: [...smallGraph.evidence, evidence('e-forward'), evidence('e-back', 'app/other.py')],
}

export const resolutionGraph = {
  ...smallGraph,
  nodes: [...smallGraph.nodes, node('n-external', 'external_module', 'pathlib', 'pathlib'), node('n-unresolved', 'unresolved_symbol', 'factory', 'dynamic.factory')],
  edges: [...smallGraph.edges, edge('e-external', 'imports', 'n-module', 'n-external'), edge('e-missing', 'calls', 'n-method', 'n-unresolved', 'unresolved', 'dynamic.factory'), edge('e-ambiguous', 'inherits', 'n-class', null, 'ambiguous', 'Base'), edge('e-syntax', 'calls', 'n-method', null, 'syntactic_only', 'factory().run')],
  evidence: [...smallGraph.evidence, evidence('e-external'), evidence('e-missing'), evidence('e-ambiguous'), evidence('e-syntax')],
  diagnostics: ['e-missing', 'e-ambiguous', 'e-syntax'].map((id) => ({ id: `d-${id}`, code: 'UNRESOLVED_STATIC_REFERENCE', severity: 'warning', phase: 'resolving', message: 'No exact static target.', location: location('app/main.py'), entity_id: null, edge_id: id, recoverable: true, consequence: 'retained', suggested_action: null, details: {} })),
}

export const emptyGraph = { schema_version: '1.0.0', metadata: { partial: false }, summary: {}, nodes: [], edges: [], evidence: [], diagnostics: [] }
export const unsupportedGraph = { ...emptyGraph, schema_version: '2.0.0' }
export const legacyFixture = { files: [{ file: 'main.py', imports: ['service'], classes: ['App'], functions: ['main'], inheritance: [], calls: [] }, { file: 'service.py', imports: [], classes: ['Service'], functions: [], inheritance: [], calls: [] }], dependencies: [{ source: 'main.py', target: 'service.py', type: 'import' }] }

export function createLargeGraph(count = 400) {
  const nodes = Array.from({ length: count }, (_, index) => node(`n-${String(index).padStart(4, '0')}`, 'module', `module_${index}`, `pkg.module_${index}`, `pkg/module_${index}.py`))
  const edges = nodes.slice(1).map((item, index) => edge(`e-${index}`, 'imports', nodes[index].id, item.id))
  return { schema_version: '1.0.0', metadata: { partial: false }, summary: {}, nodes, edges, evidence: edges.map((item, index) => evidence(item.id, `pkg/module_${index}.py`)), diagnostics: [] }
}
