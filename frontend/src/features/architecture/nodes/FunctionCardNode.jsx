import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { FunctionIcon, MethodIcon } from '../Icons.jsx'

/**
 * Function or Method card node for React Flow.
 * Renders an amber card for free functions, and a purple card for standalone methods.
 */
function FunctionCardNode({ data, selected }) {
  const isMethod = data.kind === 'method' || data.kind === 'async_method'
  const accent = isMethod ? '#8b5cf6' : '#f59e0b'
  const badgeBg = isMethod ? '#f5f3ff' : '#fef3c7'
  const badgeColor = isMethod ? '#7c3aed' : '#92400e'
  const badgeLabel = isMethod ? 'Method' : 'Function'

  return (
    <div className={`cs-card cs-card--${isMethod ? 'method' : 'function'}${selected ? ' cs-card--selected' : ''}`} style={{ '--card-accent': accent }}>
      <Handle type="target" position={Position.Top} className="cs-handle" />
      <Handle type="target" position={Position.Left} className="cs-handle" />

      <div className="cs-card__accent" />

      <div className="cs-card__header">
        <span className="cs-card__icon" style={{ color: accent }}>
          {isMethod ? <MethodIcon width={16} height={16} /> : <FunctionIcon width={16} height={16} />}
        </span>
        <span className="cs-card__name">{data.label}()</span>
        <span className="cs-card__badge" style={{ background: badgeBg, color: badgeColor }}>{badgeLabel}</span>
      </div>

      {data.description && (
        <p className="cs-card__desc">{data.description}</p>
      )}

      <Handle type="source" position={Position.Bottom} className="cs-handle" />
      <Handle type="source" position={Position.Right} className="cs-handle" />
    </div>
  )
}

export default memo(FunctionCardNode)
