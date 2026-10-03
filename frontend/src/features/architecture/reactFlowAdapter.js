/**
 * Transforms normalized graph data into React Flow elements with the approved
 * visual design: custom node types, clean label-free edges with color encoding,
 * and selected-neighborhood focus.
 */

const CLASS_KINDS = new Set(['class'])
const FUNCTION_KINDS = new Set(['function', 'async_function'])
const METHOD_KINDS = new Set(['method', 'async_method'])

const NODE_KIND_LABELS = {
  project: 'Project', directory: 'Directory', file: 'File', package: 'Package',
  module: 'Module', class: 'Class', function: 'Function', async_function: 'Async fn',
  method: 'Method', async_method: 'Async method', external_module: 'External',
  unresolved_symbol: 'Unresolved',
}

/** Edge color and dash encoding by relationship kind. */
const EDGE_STYLES = {
  inherits:   { stroke: '#8b5cf6', strokeWidth: 2, type: 'smoothstep' },
  calls:      { stroke: '#3b82f6', strokeWidth: 2, type: 'smoothstep' },
  contains:   { stroke: '#10b981', strokeWidth: 1.5, strokeDasharray: '6 4', type: 'smoothstep' },
  defines:    { stroke: '#10b981', strokeWidth: 1.5, strokeDasharray: '6 4', type: 'smoothstep' },
  constructs: { stroke: '#f59e0b', strokeWidth: 2, strokeDasharray: '3 4', type: 'smoothstep' },
  imports:    { stroke: '#64748b', strokeWidth: 1.5, type: 'smoothstep' },
}
const DEFAULT_EDGE_STYLE = { stroke: '#94a3b8', strokeWidth: 1.5, strokeDasharray: '4 4', type: 'smoothstep' }
const UNCERTAINTY_DASH = { unresolved: '8 5', ambiguous: '3 4', syntactic_only: '2 5' }

/**
 * Determine custom node type name from entity kind.
 */
function nodeType(kind) {
  if (CLASS_KINDS.has(kind)) return 'classCard'
  if (FUNCTION_KINDS.has(kind) || METHOD_KINDS.has(kind)) return 'functionCard'
  return 'defaultCard'
}

/**
 * Build the methods list for a class node by finding child method nodes.
 */
function collectMethods(classId, allNodes) {
  return allNodes
    .filter((n) => n.parentId === classId && METHOD_KINDS.has(n.kind))
    .map((n) => ({ id: n.id, name: n.displayName }))
}

/**
 * Check if a class node is a base class (has no incoming inherits edges).
 */
function isBaseClass(nodeId, edges) {
  return !edges.some((e) => e.kind === 'inherits' && e.sourceId === nodeId)
}

export function toReactFlowElements(graph, positionedNodes, options = {}) {
  const selectedId = options.selectedId || null
  const matches = new Set(options.matchIds || [])
  const nestMethods = Boolean(options.nestMethods)

  const classIds = new Set(graph.nodes.filter((n) => CLASS_KINDS.has(n.kind)).map((n) => n.id))
  const methodToClass = new Map()
  graph.nodes.forEach((n) => {
    if (METHOD_KINDS.has(n.kind) && n.parentId && classIds.has(n.parentId)) {
      methodToClass.set(n.id, n.parentId)
    }
  })

  const visiblePositioned = nestMethods
    ? positionedNodes.filter((node) => !methodToClass.has(node.id))
    : positionedNodes

  const nodeMap = new Map(visiblePositioned.map((node) => [node.id, node]))

  // Determine connected-neighborhood for focus dimming
  const connectedIds = new Set()
  if (selectedId) {
    connectedIds.add(selectedId)
    if (methodToClass.has(selectedId)) {
      connectedIds.add(methodToClass.get(selectedId))
    }
    graph.edges.forEach((edge) => {
      if (edge.sourceId === selectedId) {
        connectedIds.add(edge.targetId || edge.id)
        if (methodToClass.has(edge.targetId)) connectedIds.add(methodToClass.get(edge.targetId))
      }
      if (edge.targetId === selectedId) {
        connectedIds.add(edge.sourceId)
        if (methodToClass.has(edge.sourceId)) connectedIds.add(methodToClass.get(edge.sourceId))
      }
    })
  }

  const nodes = visiblePositioned.map((node) => {
    const type = nodeType(node.kind)
    const methods = CLASS_KINDS.has(node.kind) ? collectMethods(node.id, graph.nodes) : []
    const isSelected = selectedId === node.id || methods.some((m) => m.id === selectedId)
    const dimmed = selectedId && !connectedIds.has(node.id) && !isSelected
    return {
      id: node.id,
      type,
      position: node.position,
      data: {
        label: node.displayName,
        description: node.qualifiedName || node.displayName,
        kind: node.kind,
        kindLabel: NODE_KIND_LABELS[node.kind] || node.kind,
        methods,
        selectedMethodId: selectedId,
        onSelectMethod: options.onSelectMethod,
        isBase: CLASS_KINDS.has(node.kind) ? isBaseClass(node.id, graph.edges) : false,
        location: node.location || null,
        qualifiedName: node.qualifiedName || node.displayName,
      },
      className: `${matches.has(node.id) ? 'is-match' : ''}${dimmed ? ' is-dimmed' : ''}`,
      selected: isSelected,
      ariaLabel: `${node.kind} ${node.qualifiedName || node.displayName}`,
    }
  })

  const edges = []
  graph.edges.forEach((edge) => {
    let sourceId = edge.sourceId
    let targetId = edge.targetId

    if (nestMethods) {
      // Containment/defines edge from class to its own nested method: omit line
      if ((edge.kind === 'defines' || edge.kind === 'contains') && methodToClass.get(targetId) === sourceId) {
        return
      }

      const projSource = methodToClass.get(sourceId) || sourceId
      const projTarget = targetId ? (methodToClass.get(targetId) || targetId) : null

      // Do not create misleading class self-loops when projecting internal method calls
      if (projSource === projTarget) {
        return
      }

      sourceId = projSource
      if (projTarget) targetId = projTarget
    }

    if (!nodeMap.has(sourceId)) return

    if (!targetId || !nodeMap.has(targetId)) {
      targetId = `view-unresolved-${edge.id}`
      if (!nodeMap.has(targetId)) {
        const source = nodeMap.get(sourceId)
        const virtual = {
          id: targetId,
          type: 'defaultCard',
          position: { x: (source?.position.x || 0) + 280, y: (source?.position.y || 0) + 70 },
          data: { label: edge.targetReference || 'unknown', description: 'Unresolved target', kind: 'unresolved_symbol', kindLabel: 'Unresolved', methods: [], isBase: false },
          className: 'is-dimmed',
          selectable: false,
          ariaLabel: `Unresolved target ${edge.targetReference || 'unknown'}`,
        }
        nodeMap.set(targetId, virtual)
        nodes.push(virtual)
      }
    }

    const edgeStyle = EDGE_STYLES[edge.kind] || DEFAULT_EDGE_STYLE
    const dimmedEdge = selectedId && !connectedIds.has(sourceId) && !connectedIds.has(targetId)

    edges.push({
      id: edge.id,
      source: sourceId,
      target: targetId,
      type: edgeStyle.type,
      /* No label — clean connectors per the approved design */
      className: `cs-edge cs-edge--${edge.kind}${dimmedEdge ? ' is-dimmed' : ''}`,
      animated: false,
      selected: selectedId === edge.id,
      markerEnd: { type: 'arrowclosed', color: edgeStyle.stroke },
      style: {
        stroke: edgeStyle.stroke,
        strokeWidth: edgeStyle.strokeWidth,
        strokeDasharray: UNCERTAINTY_DASH[edge.resolutionStatus] || edgeStyle.strokeDasharray || undefined,
        opacity: dimmedEdge ? 0.2 : 1,
      },
      ariaLabel: `${edge.kind} relationship, ${edge.resolutionStatus}`,
    })
  })

  return { nodes, edges }
}
