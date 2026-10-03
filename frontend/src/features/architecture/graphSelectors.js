export const DEFAULT_FILTERS = Object.freeze({ nodeKinds: [], relationshipKinds: [], resolutionStatuses: [], targetClasses: [], diagnosticSeverities: [] })

export const DEFAULT_VISIBILITY = Object.freeze({ classes: true, functions: true, methods: true })

const includes = (choices, value) => !choices?.length || choices.includes(value)

export function searchNodes(graph, query) {
  const term = query.trim().toLocaleLowerCase()
  if (!term) return []
  return graph.nodes.filter((node) => [node.displayName, node.qualifiedName, node.location?.path, node.kind]
    .some((value) => typeof value === 'string' && value.toLocaleLowerCase().includes(term)))
    .sort((left, right) => left.qualifiedName?.localeCompare(right.qualifiedName || '') || left.id.localeCompare(right.id))
}

export function nextSearchIndex(current, step, resultCount) {
  if (!resultCount) return 0
  return (current + step + resultCount) % resultCount
}

/**
 * Apply visibility toggles from the left sidebar to hide/show entity kinds.
 */
const CLASS_KINDS = new Set(['class'])
const FUNCTION_KINDS = new Set(['function', 'async_function'])
const METHOD_KINDS = new Set(['method', 'async_method'])

export function applyVisibility(graph, visibility) {
  if (!visibility || (visibility.classes !== false && visibility.functions !== false && visibility.methods !== false)) {
    return graph
  }
  const hiddenKinds = new Set()
  if (visibility.classes === false) CLASS_KINDS.forEach((k) => hiddenKinds.add(k))
  if (visibility.functions === false) FUNCTION_KINDS.forEach((k) => hiddenKinds.add(k))
  if (visibility.methods === false) METHOD_KINDS.forEach((k) => hiddenKinds.add(k))

  const nodes = graph.nodes.filter((node) => !hiddenKinds.has(node.kind))
  const visibleIds = new Set(nodes.map((n) => n.id))
  const edges = graph.edges.filter((e) => visibleIds.has(e.sourceId) && (!e.targetId || visibleIds.has(e.targetId)))
  return { ...graph, nodes, edges }
}

/**
 * Apply view-mode filtering: Overview shows everything, Classes hides functions,
 * Call flow hides inheritance.
 */
export function applyViewMode(graph, viewMode) {
  if (!viewMode || viewMode === 'overview') return graph
  if (viewMode === 'classes') {
    const nodes = graph.nodes.filter((n) => !FUNCTION_KINDS.has(n.kind))
    const ids = new Set(nodes.map((n) => n.id))
    const edges = graph.edges.filter((e) => ids.has(e.sourceId) && (!e.targetId || ids.has(e.targetId)))
    return { ...graph, nodes, edges }
  }
  if (viewMode === 'callflow') {
    const edges = graph.edges.filter((e) => e.kind === 'calls' || e.kind === 'constructs')
    const referencedIds = new Set()
    edges.forEach((e) => { referencedIds.add(e.sourceId); if (e.targetId) referencedIds.add(e.targetId) })
    const nodes = graph.nodes.filter((n) => referencedIds.has(n.id))
    return { ...graph, nodes, edges }
  }
  return graph
}

export function filterGraph(graph, filters = DEFAULT_FILTERS) {
  const severityEntities = new Set()
  if (filters.diagnosticSeverities?.length) {
    graph.diagnostics.forEach((item) => {
      if (filters.diagnosticSeverities.includes(item.severity)) {
        if (item.entityId) severityEntities.add(item.entityId)
        if (item.edgeId) severityEntities.add(item.edgeId)
      }
    })
  }
  const nodes = graph.nodes.filter((node) => includes(filters.nodeKinds, node.kind)
    && (!filters.diagnosticSeverities?.length || severityEntities.has(node.id)))
  const visibleNodeIds = new Set(nodes.map((node) => node.id))
  const edges = graph.edges.filter((edge) => includes(filters.relationshipKinds, edge.kind)
    && includes(filters.resolutionStatuses, edge.resolutionStatus)
    && includes(filters.targetClasses, edge.targetClassification)
    && (!filters.diagnosticSeverities?.length || severityEntities.has(edge.id))
    && visibleNodeIds.has(edge.sourceId)
    && (!edge.targetId || visibleNodeIds.has(edge.targetId)))
  return {
    ...graph, nodes, edges,
    counts: { visibleNodes: nodes.length, totalNodes: graph.nodes.length, visibleEdges: edges.length, totalEdges: graph.edges.length },
  }
}

export function selectElementDetails(graph, selection) {
  if (!selection) return null
  const nodes = new Map(graph.nodes.map((node) => [node.id, node]))
  const evidence = new Map(graph.evidence.map((item) => [item.id, item]))
  if (selection.type === 'node') {
    const item = nodes.get(selection.id)
    if (!item) return null
    const incoming = graph.edges.filter((edge) => edge.targetId === item.id)
    const outgoing = graph.edges.filter((edge) => edge.sourceId === item.id)
    return { type: 'node', item, parent: nodes.get(item.parentId) || null, incoming, outgoing, diagnostics: graph.diagnostics.filter((value) => value.entityId === item.id) }
  }
  const item = graph.edges.find((edge) => edge.id === selection.id)
  if (!item) return null
  return {
    type: 'edge', item, source: nodes.get(item.sourceId) || null, target: nodes.get(item.targetId) || null,
    evidence: item.evidenceIds.map((id) => evidence.get(id)).filter(Boolean),
    diagnostics: graph.diagnostics.filter((value) => value.edgeId === item.id || item.diagnosticIds.includes(value.id)),
  }
}

export function overviewGraph(graph) {
  const overviewKinds = new Set(['project', 'directory', 'package', 'module', 'external_module', 'unresolved_symbol'])
  const nodes = graph.nodes.filter((node) => overviewKinds.has(node.kind))
  const ids = new Set(nodes.map((node) => node.id))
  const edges = graph.edges.filter((edge) => ids.has(edge.sourceId) && (!edge.targetId || ids.has(edge.targetId)))
  return { ...graph, nodes, edges }
}

export function exceedsGraphThreshold(graph, threshold) {
  return graph.nodes.length > threshold.nodes || graph.edges.length > threshold.edges
}

/**
 * Determine a clean, human-readable display identity for the current analysis.
 * Handles editor files, folder analyses, and configured project aliases without leaking internal tokens.
 */
export function getAnalysisIdentity(graph, provenance, projects = []) {
  if (!graph || !graph.nodes) return ''

  // 1. Editor file or single file analysis
  const isEditorCapability = provenance?.root_id?.startsWith('cap_')
  const fileNodes = graph.nodes.filter((n) => n.kind === 'file')
  const projectNode = graph.nodes.find((n) => n.kind === 'project')

  if (isEditorCapability) {
    const rawPath = provenance.relative_path || provenance.target_file || provenance.path || provenance.file_path
    if (rawPath) {
      return rawPath.split('/').pop().split('\\').pop()
    }
  }

  if (isEditorCapability || (fileNodes.length === 1 && (!projectNode || projectNode.name?.endsWith?.('.py')))) {
    if (fileNodes.length > 0) {
      const p = fileNodes[0].name || fileNodes[0].displayName || fileNodes[0].location?.path
      if (p) {
        return p.split('/').pop().split('\\').pop()
      }
    }
    if (projectNode && projectNode.name && projectNode.name !== 'project' && !isEditorCapability) {
      return projectNode.name.split('/').pop().split('\\').pop()
    }
  }

  // 2. Matching configured project
  if (provenance?.root_id && Array.isArray(projects)) {
    const matched = projects.find((p) => p.id === provenance.root_id)
    if (matched?.display_name) return matched.display_name
  }

  // 3. Project node name or display name
  if (projectNode) {
    const display = projectNode.displayName || projectNode.attributes?.display_name
    if (display && display !== 'project') return display
    if (projectNode.name && projectNode.name !== 'project') return projectNode.name
  }

  // 4. Single file fallback
  if (fileNodes.length === 1) {
    const p = fileNodes[0].displayName || fileNodes[0].name
    if (p) return p.split('/').pop().split('\\').pop()
  }

  return 'Python Architecture'
}
