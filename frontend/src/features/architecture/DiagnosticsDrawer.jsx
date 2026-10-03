import { CloseIcon } from './Icons.jsx'

/**
 * Compact diagnostics drawer — replaces the old full-width DiagnosticsPanel.
 * Renders as a collapsible overlay when opened from the toolbar overflow menu.
 */
export default function DiagnosticsDrawer({ diagnostics, open, onClose, severity, onSeverity, onSelect }) {
  if (!open) return null
  const visible = severity === 'all' ? diagnostics : diagnostics.filter((item) => item.severity === severity)

  return (
    <div className="cs-drawer" role="dialog" aria-label="Analysis diagnostics" aria-modal="false">
      <div className="cs-drawer__header">
        <h3 className="cs-drawer__title">Diagnostics ({diagnostics.length})</h3>
        <div className="cs-drawer__controls">
          <label className="cs-drawer__filter">
            Severity
            <select value={severity} onChange={(e) => onSeverity(e.target.value)}>
              <option value="all">All</option>
              <option value="error">Error</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </label>
          <button type="button" className="cs-drawer__close" onClick={onClose} aria-label="Close diagnostics">
            <CloseIcon width={16} height={16} />
          </button>
        </div>
      </div>

      <div className="cs-drawer__body">
        {!visible.length ? (
          <p className="cs-drawer__empty">No analysis diagnostics match this filter. Application failures appear in the status region.</p>
        ) : (
          <ul className="cs-drawer__list">
            {visible.map((item) => (
              <li key={item.id} className={`cs-drawer__item cs-drawer__item--${item.severity}`}>
                <div className="cs-drawer__item-header">
                  <span className={`cs-drawer__severity cs-drawer__severity--${item.severity}`}>
                    {item.severity?.toUpperCase() || 'INFO'}
                  </span>
                  <code className="cs-drawer__code">{item.code}</code>
                </div>
                <p className="cs-drawer__msg">{item.message}</p>
                {item.location && (
                  <p className="cs-drawer__loc">
                    {item.location.path}{item.location.startLine ? `:${item.location.startLine}:${item.location.startColumn || 1}` : ''}
                  </p>
                )}
                {(item.entityId || item.edgeId) && (
                  <button
                    type="button"
                    className="cs-drawer__inspect"
                    onClick={() => onSelect({ type: item.entityId ? 'node' : 'edge', id: item.entityId || item.edgeId })}
                  >
                    Inspect related element
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
