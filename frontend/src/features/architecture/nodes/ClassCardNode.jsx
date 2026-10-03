import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { ClassIcon, MethodIcon } from '../Icons.jsx'

/**
 * Class card node for React Flow.
 * Renders a white card with blue left accent bar, class icon + badge header,
 * and optional nested method rows (purple pills).
 */
function ClassCardNode({ data, selected }) {
  const methods = data.methods || []
  const isBase = data.isBase
  const accent = isBase ? '#059669' : '#2563eb'
  const badgeBg = isBase ? '#ecfdf5' : '#eff6ff'
  const badgeColor = isBase ? '#059669' : '#2563eb'

  return (
    <div
      className={`cs-card cs-card--class${selected ? ' cs-card--selected' : ''}`}
      style={{ '--card-accent': accent }}
    >
      <Handle type="target" position={Position.Top} className="cs-handle" />
      <Handle type="target" position={Position.Left} className="cs-handle" />

      <div className="cs-card__accent" />

      <div className="cs-card__header">
        <span className="cs-card__icon" style={{ color: accent }}><ClassIcon width={16} height={16} /></span>
        <span className="cs-card__name">{data.label}</span>
        <span className="cs-card__badge" style={{ background: badgeBg, color: badgeColor }}>Class</span>
      </div>

      {methods.length > 0 && (
        <div className="cs-card__methods">
          {methods.map((m) => (
            <span
              key={m.id || m.name}
              className={`cs-method-pill${data.selectedMethodId === m.id ? ' cs-method-pill--selected' : ''}`}
              onClick={(e) => {
                if (data.onSelectMethod && m.id) {
                  e.stopPropagation()
                  data.onSelectMethod({ type: 'node', id: m.id })
                }
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if ((e.key === 'Enter' || e.key === ' ') && data.onSelectMethod && m.id) {
                  e.stopPropagation()
                  e.preventDefault()
                  data.onSelectMethod({ type: 'node', id: m.id })
                }
              }}
              style={{ cursor: 'pointer' }}
              title={`Select method ${m.name}`}
            >
              <MethodIcon width={12} height={12} />
              <span>{m.name}()</span>
            </span>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="cs-handle" />
      <Handle type="source" position={Position.Right} className="cs-handle" />
    </div>
  )
}

export default memo(ClassCardNode)
