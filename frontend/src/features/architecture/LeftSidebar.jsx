import { OverviewIcon, ClassesIcon, CallFlowIcon } from './Icons.jsx'

const VIEWS = [
  { id: 'overview', label: 'Overview', icon: OverviewIcon },
  { id: 'classes', label: 'Classes', icon: ClassesIcon },
  { id: 'callflow', label: 'Call flow', icon: CallFlowIcon },
]

const VISIBILITY = [
  { id: 'classes', label: 'Classes', color: '#2563eb' },
  { id: 'functions', label: 'Functions', color: '#f59e0b' },
  { id: 'methods', label: 'Methods', color: '#8b5cf6' },
]

const LEGEND = [
  { label: 'Inheritance', color: '#8b5cf6', dash: '' },
  { label: 'Calls', color: '#3b82f6', dash: '' },
  { label: 'Contains', color: '#10b981', dash: '4 3' },
  { label: 'Constructs', color: '#f59e0b', dash: '2 3' },
]

/**
 * Left sidebar for the Architecture Explorer.
 * Sections: Navigation views, visibility toggles, relationship legend.
 */
export default function LeftSidebar({
  activeView,
  onViewChange,
  visibility,
  onVisibilityChange,
  collapsed = false,
  onToggleCollapse = null,
}) {
  return (
    <aside className={`cs-sidebar${collapsed ? ' cs-sidebar--collapsed' : ''}`} aria-label="Architecture navigation">
      {onToggleCollapse && (
        <div className="cs-sidebar__collapse-bar">
          <button
            type="button"
            className="cs-sidebar__collapse-btn"
            onClick={onToggleCollapse}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar to rail'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar to rail'}
          >
            <span aria-hidden="true">{collapsed ? '→' : '←'}</span>
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav className="cs-sidebar__section" aria-label="View modes">
        {!collapsed && <h3 className="cs-sidebar__heading">Views</h3>}
        <ul className="cs-sidebar__nav">
          {VIEWS.map(({ id, label, icon: Icon }) => (
            <li key={id}>
              <button
                type="button"
                className={`cs-sidebar__nav-btn${activeView === id ? ' cs-sidebar__nav-btn--active' : ''}`}
                onClick={() => onViewChange(id)}
                aria-current={activeView === id ? 'true' : undefined}
                title={collapsed ? label : undefined}
                aria-label={collapsed ? label : undefined}
              >
                <Icon width={16} height={16} />
                {!collapsed && <span>{label}</span>}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Visibility - hidden in collapsed rail mode */}
      {!collapsed && (
        <div className="cs-sidebar__section">
          <h3 className="cs-sidebar__heading">Show</h3>
          <div className="cs-sidebar__checks">
            {VISIBILITY.map(({ id, label, color }) => (
              <label key={id} className="cs-sidebar__check">
                <input
                  type="checkbox"
                  checked={visibility[id] !== false}
                  onChange={() => onVisibilityChange({ ...visibility, [id]: !visibility[id] !== false ? false : true })}
                  style={{ accentColor: color }}
                />
                <span style={{ color }}>{label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Relationship Legend - hidden in collapsed rail mode */}
      {!collapsed && (
        <div className="cs-sidebar__section cs-sidebar__section--legend">
          <h3 className="cs-sidebar__heading">Relationships</h3>
          <ul className="cs-sidebar__legend">
            {LEGEND.map(({ label, color, dash }) => (
              <li key={label} className="cs-legend-item">
                <svg width="28" height="12" aria-hidden="true">
                  <line x1="2" y1="6" x2="20" y2="6" stroke={color} strokeWidth="2" strokeDasharray={dash || undefined} />
                  <polygon points="20,2 26,6 20,10" fill={color} />
                </svg>
                <span>{label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  )
}
