import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { ModuleIcon } from '../Icons.jsx'

/**
 * Default card node for React Flow.
 * Used for modules, files, packages, projects, and unresolved symbols.
 */
function DefaultCardNode({ data, selected }) {
  const accent = data.kind === 'unresolved_symbol' ? '#94a3b8' : '#6366f1'
  const badgeLabel = data.kindLabel || 'Module'
  const badgeBg = data.kind === 'unresolved_symbol' ? '#f1f5f9' : '#eef2ff'
  const badgeColor = data.kind === 'unresolved_symbol' ? '#64748b' : '#4338ca'

  return (
    <div className={`cs-card cs-card--default${selected ? ' cs-card--selected' : ''}${data.kind === 'unresolved_symbol' ? ' cs-card--unresolved' : ''}`} style={{ '--card-accent': accent }}>
      <Handle type="target" position={Position.Top} className="cs-handle" />
      <Handle type="target" position={Position.Left} className="cs-handle" />

      <div className="cs-card__accent" />

      <div className="cs-card__header">
        <span className="cs-card__icon" style={{ color: accent }}><ModuleIcon width={16} height={16} /></span>
        <span className="cs-card__name">{data.label}</span>
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

export default memo(DefaultCardNode)
