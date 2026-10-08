export const DEFAULT_LAYOUT_OPTIONS = Object.freeze({ columnGap: 340, rowGap: 160, originX: 60, originY: 60 })

// Replaceable zero-dependency fallback until the approved Dagre adapter can be
// installed and benchmarked; presentation coordinates never enter graph data.
export function layoutGraph(nodes, edges, options = {}) {
  const t0 = typeof performance !== 'undefined' ? performance.now() : 0
  const config = { ...DEFAULT_LAYOUT_OPTIONS, ...options }
  const ids = new Set(nodes.map((node) => node.id))
  const incoming = new Map(nodes.map((node) => [node.id, 0]))
  const outgoing = new Map(nodes.map((node) => [node.id, []]))
  edges.forEach((edge) => {
    if (!edge.targetId || !ids.has(edge.sourceId) || !ids.has(edge.targetId) || edge.sourceId === edge.targetId) return
    outgoing.get(edge.sourceId).push(edge.targetId)
    incoming.set(edge.targetId, incoming.get(edge.targetId) + 1)
  })
  outgoing.forEach((targets) => targets.sort())
  const level = new Map(nodes.map((node) => [node.id, 0]))
  const queue = [...nodes.filter((node) => incoming.get(node.id) === 0).map((node) => node.id)].sort()
  const visited = new Set()
  while (queue.length) {
    const id = queue.shift()
    if (visited.has(id)) continue
    visited.add(id)
    outgoing.get(id).forEach((target) => {
      level.set(target, Math.max(level.get(target), level.get(id) + 1))
      incoming.set(target, incoming.get(target) - 1)
      if (incoming.get(target) === 0) queue.push(target)
    })
    queue.sort()
  }
  // Cyclic components are placed deterministically after acyclic layers.
  const maxLevel = Math.max(0, ...level.values())
  nodes.filter((node) => !visited.has(node.id)).sort((a, b) => a.id.localeCompare(b.id))
    .forEach((node, index) => level.set(node.id, maxLevel + 1 + (index % 2)))
  const rows = new Map()
  const result = [...nodes].sort((a, b) => level.get(a.id) - level.get(b.id) || a.qualifiedName?.localeCompare(b.qualifiedName || '') || a.id.localeCompare(b.id))
    .map((node) => {
      const column = level.get(node.id)
      const row = rows.get(column) || 0
      rows.set(column, row + 1)
      return { ...node, position: { x: config.originX + column * config.columnGap, y: config.originY + row * config.rowGap } }
    })
  const t1 = typeof performance !== 'undefined' ? performance.now() : 0
  if (typeof window !== 'undefined') {
    window.__codestruct_last_layout_ms = t1 - t0
    window.__codestruct_layout_node_count = nodes.length
    window.__codestruct_layout_edge_count = edges.length
  }
  return result
}
