export const SUPPORTED_SCHEMA_MAJOR = 1

export const NODE_KINDS = [
  'project', 'directory', 'file', 'package', 'module', 'class', 'function',
  'async_function', 'method', 'async_method', 'external_module', 'unresolved_symbol',
]

export const RELATIONSHIP_KINDS = [
  'contains', 'defines', 'imports', 'inherits', 'calls', 'constructs', 'references',
]

export const RESOLUTION_STATUSES = [
  'not_applicable', 'resolved', 'ambiguous', 'unresolved', 'syntactic_only',
]

const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
const text = (value) => typeof value === 'string' ? value : null
const list = (value) => Array.isArray(value) ? value : []

export function safeRelativePath(value) {
  if (typeof value !== 'string' || !value || value.includes('\\')) return null
  if (value.startsWith('/') || /^[a-zA-Z]:/.test(value)) return null
  const parts = value.split('/')
  return parts.includes('..') ? null : value
}

function location(value) {
  if (!isObject(value)) return null
  const path = safeRelativePath(value.path)
  if (!path) return null
  return {
    sourceUnitId: text(value.source_unit_id),
    path,
    startLine: Number.isInteger(value.start_line) ? value.start_line : null,
    startColumn: Number.isInteger(value.start_column) ? value.start_column : null,
    endLine: Number.isInteger(value.end_line) ? value.end_line : null,
    endColumn: Number.isInteger(value.end_column) ? value.end_column : null,
  }
}

export class GraphContractError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'GraphContractError'
    this.code = code
  }
}

export function validateGraphContract(payload) {
  if (!isObject(payload)) throw new GraphContractError('INVALID_GRAPH', 'The analysis response is not a graph object.')
  const schemaVersion = text(payload.schema_version)
  if (!schemaVersion) throw new GraphContractError('MISSING_SCHEMA', 'The graph schema version is missing.')
  const major = Number.parseInt(schemaVersion.split('.')[0], 10)
  if (!Number.isInteger(major) || major !== SUPPORTED_SCHEMA_MAJOR) {
    throw new GraphContractError('UNSUPPORTED_SCHEMA', `Graph schema ${schemaVersion} is not supported by this explorer.`)
  }
  if (!Array.isArray(payload.nodes) || !Array.isArray(payload.edges)) {
    throw new GraphContractError('INVALID_GRAPH', 'The graph must contain node and edge arrays.')
  }
  return schemaVersion
}

export function normalizeGraphContract(payload) {
  const schemaVersion = validateGraphContract(payload)
  const nodes = payload.nodes.map((node, index) => {
    if (!isObject(node) || !text(node.id) || !text(node.kind) || !text(node.name)) {
      throw new GraphContractError('INVALID_NODE', `Graph node ${index + 1} is missing a required identity field.`)
    }
    return {
      id: node.id,
      kind: node.kind,
      displayName: node.name,
      qualifiedName: text(node.qualified_name),
      parentId: text(node.parent_id),
      moduleId: text(node.module_id),
      fileId: text(node.file_id),
      location: location(node.location),
      modifiers: list(node.modifiers).filter((item) => typeof item === 'string'),
      attributes: isObject(node.attributes) ? { ...node.attributes } : {},
      classification: node.kind === 'external_module' ? 'external' : node.kind === 'unresolved_symbol' ? 'unresolved' : 'internal',
    }
  })
  const nodeIds = new Set(nodes.map((node) => node.id))
  if (nodeIds.size !== nodes.length) throw new GraphContractError('DUPLICATE_NODE', 'The graph contains duplicate node identifiers.')
  const nodeClassifications = new Map(nodes.map((node) => [node.id, node.classification]))

  const edges = payload.edges.map((edge, index) => {
    if (!isObject(edge) || !text(edge.id) || !text(edge.kind) || !text(edge.source_id)) {
      throw new GraphContractError('INVALID_EDGE', `Graph relationship ${index + 1} is missing a required identity field.`)
    }
    const status = text(edge.resolution_status) || 'syntactic_only'
    const targetId = text(edge.target_id)
    return {
      id: edge.id,
      kind: edge.kind,
      sourceId: edge.source_id,
      targetId,
      targetReference: text(edge.target_reference),
      resolutionStatus: status,
      confidence: text(edge.confidence),
      confidenceReason: text(edge.confidence_reason),
      candidateIds: list(edge.candidate_ids).filter((item) => typeof item === 'string'),
      evidenceIds: list(edge.evidence_ids).filter((item) => typeof item === 'string'),
      diagnosticIds: list(edge.diagnostic_ids).filter((item) => typeof item === 'string'),
      occurrenceCount: Number.isInteger(edge.occurrence_count) ? edge.occurrence_count : 1,
      attributes: isObject(edge.attributes) ? { ...edge.attributes } : {},
      targetClassification: targetId && nodeIds.has(targetId)
        ? nodeClassifications.get(targetId)
        : status === 'resolved' ? 'missing' : 'unresolved',
    }
  })
  if (new Set(edges.map((edge) => edge.id)).size !== edges.length) {
    throw new GraphContractError('DUPLICATE_EDGE', 'The graph contains duplicate relationship identifiers.')
  }
  edges.forEach((edge) => {
    if (!nodeIds.has(edge.sourceId)) throw new GraphContractError('MISSING_SOURCE', `Relationship ${edge.id} has no included source.`)
    if (edge.resolutionStatus === 'resolved' && (!edge.targetId || !nodeIds.has(edge.targetId))) {
      throw new GraphContractError('MISSING_RESOLVED_TARGET', `Resolved relationship ${edge.id} has no included target.`)
    }
  })

  const evidence = list(payload.evidence).filter(isObject).map((item) => ({
    id: text(item.evidence_id) || '',
    origin: text(item.origin),
    observationKind: text(item.observation_kind),
    location: location(item.location),
    explanation: text(item.explanation),
    expression: text(item.expression),
  }))
  const diagnostics = list(payload.diagnostics).filter(isObject).map((item) => ({
    id: text(item.id) || '',
    code: text(item.code) || 'UNKNOWN_DIAGNOSTIC',
    severity: text(item.severity) || 'warning',
    phase: text(item.phase),
    message: text(item.message) || 'No safe diagnostic message is available.',
    location: location(item.location),
    entityId: text(item.entity_id),
    edgeId: text(item.edge_id),
    consequence: text(item.consequence),
    suggestedAction: text(item.suggested_action),
  }))
  return {
    source: 'v1', schemaVersion, metadata: isObject(payload.metadata) ? { ...payload.metadata } : {},
    summary: isObject(payload.summary) ? { ...payload.summary } : {}, page: isObject(payload.page) ? { ...payload.page } : null, nodes, edges, evidence, diagnostics,
  }
}
