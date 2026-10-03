/**
 * Client-side Graphviz DOT generator for CodeStruct architecture graphs.
 */

function sanitizeId(id) {
  return String(id).replace(/[^a-zA-Z0-9_]/g, '_')
}

function escapeDot(text) {
  return String(text).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n')
}

const KIND_COLORS = {
  class: { fill: '#eff6ff', stroke: '#2563eb', font: '#1e3a8a' },
  function: { fill: '#fffbeb', stroke: '#d97706', font: '#78350f' },
  async_function: { fill: '#fffbeb', stroke: '#d97706', font: '#78350f' },
  method: { fill: '#f5f3ff', stroke: '#7c3aed', font: '#4c1d95' },
  async_method: { fill: '#f5f3ff', stroke: '#7c3aed', font: '#4c1d95' },
  module: { fill: '#f0fdf4', stroke: '#16a34a', font: '#14532d' },
  file: { fill: '#f8fafc', stroke: '#64748b', font: '#334155' },
  package: { fill: '#f0fdf4', stroke: '#15803d', font: '#14532d' },
  unresolved_symbol: { fill: '#f8fafc', stroke: '#94a3b8', font: '#64748b' },
}

const DEFAULT_COLOR = { fill: '#f8fafc', stroke: '#64748b', font: '#334155' }

export function generateDot(graph) {
  if (!graph) return ''
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const title = graph.metadata?.analysis_id || 'CodeStructArchitecture'

  const lines = [
    `digraph "${sanitizeId(title)}" {`,
    '  graph [rankdir=TB, splines=spline, overlap=false, fontname="Inter,sans-serif", fontsize=11, bgcolor="#ffffff"];',
    '  node [shape=box, style="rounded,filled", fontname="Inter,sans-serif", fontsize=10, margin="0.15,0.08"];',
    '  edge [fontname="Inter,sans-serif", fontsize=8, color="#64748b"];',
    '',
    '  // Nodes',
  ]

  const idMap = new Map()
  nodes.forEach((n) => {
    idMap.set(n.id, `node_${sanitizeId(n.id)}`)
  })

  nodes.forEach((node) => {
    const dotId = idMap.get(node.id)
    const name = node.displayName || node.name || node.id
    const kind = node.kind || 'entity'
    const color = KIND_COLORS[kind] || DEFAULT_COLOR

    const labelParts = [name, `(${kind})`]
    if (node.attributes?.fan_in != null && node.attributes?.fan_out != null) {
      labelParts.push(`in: ${node.attributes.fan_in} | out: ${node.attributes.fan_out}`)
    }
    const label = labelParts.map(escapeDot).join('\\n')

    lines.push(
      `  ${dotId} [label="${label}", fillcolor="${color.fill}", color="${color.stroke}", fontcolor="${color.font}"];`
    )
  })

  lines.push('')
  lines.push('  // Edges')
  edges.forEach((edge) => {
    const src = idMap.get(edge.sourceId)
    const tgt = idMap.get(edge.targetId)
    if (!src || !tgt) return

    const kind = edge.kind || 'calls'
    const isCall = kind === 'calls'
    const isInherit = kind === 'inherits'
    const color = isCall ? '#3b82f6' : isInherit ? '#8b5cf6' : '#64748b'
    const style = isInherit ? 'solid' : isCall ? 'solid' : 'dashed'

    lines.push(`  ${src} -> ${tgt} [label="${escapeDot(kind)}", color="${color}", style="${style}"];`)
  })

  lines.push('}')
  return lines.join('\n') + '\n'
}
