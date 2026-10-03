import { useEffect, useMemo, useState } from 'react'
import { Background, Controls, MiniMap, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { toReactFlowElements } from './reactFlowAdapter.js'
import ClassCardNode from './nodes/ClassCardNode.jsx'
import FunctionCardNode from './nodes/FunctionCardNode.jsx'
import DefaultCardNode from './nodes/DefaultCardNode.jsx'
import NodeContextMenu from './NodeContextMenu.jsx'

/** Custom node types registered with React Flow. */
const nodeTypes = {
  classCard: ClassCardNode,
  functionCard: FunctionCardNode,
  defaultCard: DefaultCardNode,
}

/** Minimap node color mapping matching entity accent colors. */
function minimapNodeColor(node) {
  const kind = node.data?.kind
  if (kind === 'class') return '#2563eb'
  if (kind === 'function' || kind === 'async_function') return '#f59e0b'
  if (kind === 'method' || kind === 'async_method') return '#8b5cf6'
  if (kind === 'unresolved_symbol') return '#94a3b8'
  return '#6366f1'
}

export default function ArchitectureGraph({
  graph,
  positionedNodes,
  matchIds,
  reducedMotion,
  selectedId,
  onSelect,
  onController,
  viewMode = 'overview',
  onNavigateSource = null,
}) {
  const [instance, setInstance] = useState(null)
  const [contextMenu, setContextMenu] = useState(null)

  const elements = useMemo(
    () =>
      toReactFlowElements(graph, positionedNodes, {
        matchIds,
        reducedMotion,
        allowAnimation: false,
        selectedId,
        viewMode,
        nestMethods: viewMode !== 'callflow',
        onSelectMethod: onSelect,
      }),
    [graph, positionedNodes, matchIds, reducedMotion, selectedId, viewMode, onSelect]
  )

  useEffect(() => {
    if (!instance) return undefined
    const controller = {
      zoomIn: () => instance.zoomIn({ duration: reducedMotion ? 0 : 150 }),
      zoomOut: () => instance.zoomOut({ duration: reducedMotion ? 0 : 150 }),
      fitView: () => instance.fitView({ duration: reducedMotion ? 0 : 200, padding: 0.15 }),
      reset: () => instance.setViewport({ x: 0, y: 0, zoom: 1 }, { duration: reducedMotion ? 0 : 200 }),
      center: (id) => instance.fitView({ nodes: [{ id }], duration: reducedMotion ? 0 : 200, padding: 1.5 }),
    }
    onController(controller)
    return () => {
      onController(null)
    }
  }, [instance, onController, reducedMotion])

  return (
    <div className="cs-canvas" role="region" aria-label="Interactive architecture graph">
      <ReactFlow
        nodes={elements.nodes}
        edges={elements.edges}
        nodeTypes={nodeTypes}
        onInit={setInstance}
        onNodeClick={(_, node) => {
          setContextMenu(null)
          if (!node.id.startsWith('view-unresolved-')) {
            onSelect({ type: 'node', id: node.id })
          }
        }}
        onNodeContextMenu={(event, node) => {
          event.preventDefault()
          if (!node.id.startsWith('view-unresolved-')) {
            setContextMenu({ x: event.clientX, y: event.clientY, node })
          }
        }}
        onEdgeClick={(_, edge) => {
          setContextMenu(null)
          onSelect({ type: 'edge', id: edge.id })
        }}
        onPaneClick={() => {
          setContextMenu(null)
          onSelect(null)
        }}
        onMoveStart={() => setContextMenu(null)}
        fitView
        nodesFocusable
        edgesFocusable
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        <Background variant="dots" gap={20} size={1} color="#cbd5e1" />
        <Controls showInteractive={false} className="cs-controls" />
        <MiniMap
          pannable
          zoomable
          ariaLabel="Architecture overview map"
          className="cs-minimap"
          nodeColor={minimapNodeColor}
          maskColor="rgba(248, 250, 252, 0.75)"
        />
      </ReactFlow>

      {contextMenu && (
        <NodeContextMenu
          node={contextMenu.node}
          position={{ x: contextMenu.x, y: contextMenu.y }}
          onClose={() => setContextMenu(null)}
          onNavigateSource={onNavigateSource}
          onSelect={onSelect}
          onCenter={
            instance
              ? (nodeId) =>
                  instance.fitView({
                    nodes: [{ id: nodeId }],
                    duration: reducedMotion ? 0 : 200,
                    padding: 1.5,
                  })
              : null
          }
        />
      )}
    </div>
  )
}

