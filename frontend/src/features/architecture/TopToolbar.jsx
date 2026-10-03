import { useEffect, useRef, useState } from 'react'
import {
  SearchIcon,
  FitIcon,
  FullscreenIcon,
  ExitFullscreenIcon,
  MoreIcon,
  TableIcon,
  DiagnosticsIcon,
  RefreshIcon,
  LogoIcon,
  ChevronDownIcon,
  CloseIcon,
  ExportIcon,
} from './Icons.jsx'
import { generateDot } from './exportDot.js'

/**
 * Top toolbar matching requirements:
 * [Logo + CodeStruct] [Current file/project picker] [Search] [Fit] [Fullscreen] [More]
 * Height: 56–64 px, clean outline icons, non-overlapping search, working actions.
 */
export default function TopToolbar({
  currentIdentity = 'Architecture',
  analysisId = '',
  projects = [],
  projectId = '',
  onSelectProject = null,
  onSubmitProject = null,
  onRefresh = null,
  provenance = null,
  busy = false,
  query = '',
  onQueryChange = null,
  resultCount = 0,
  activeIndex = 0,
  onStep = null,
  onActivate = null,
  controller = null,
  onToggleTable = null,
  onToggleDiagnostics = null,
  focusMode = false,
  onToggleFocusMode = null,
  graph = null,
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [aboutOpen, setAboutOpen] = useState(false)
  const searchInputRef = useRef(null)
  const menuRef = useRef(null)
  const pickerRef = useRef(null)

  const isEditorAnalysis = provenance?.root_id?.startsWith('cap_') || currentIdentity.endsWith('.py')

  // Keyboard shortcut: Ctrl+K or Cmd+K focuses search
  useEffect(() => {
    function handleKeyDown(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Close menus on outside click or escape
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
      if (pickerRef.current && !pickerRef.current.contains(e.target)) {
        setPickerOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleSearchKeyDown(event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      onStep?.(1)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      onStep?.(-1)
    } else if (event.key === 'Enter' && resultCount) {
      event.preventDefault()
      onActivate?.()
    } else if (event.key === 'Escape') {
      onQueryChange?.('')
      searchInputRef.current?.blur()
    }
  }

  // Working JSON export action
  function handleExportJson() {
    if (!graph) return
    const blob = new Blob([JSON.stringify(graph, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentIdentity || 'architecture'}-graph.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    setMenuOpen(false)
  }

  // Working DOT export action
  async function handleExportDot() {
    if (!graph) return
    let dotContent = ''
    if (analysisId) {
      try {
        const res = await fetch(`/api/v1/analyses/${encodeURIComponent(analysisId)}/export/dot`)
        if (res.ok) {
          dotContent = await res.text()
        }
      } catch {
        // Fallback to client-side generation
      }
    }
    if (!dotContent) {
      dotContent = generateDot(graph)
    }
    const blob = new Blob([dotContent], { type: 'text/vnd.graphviz' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentIdentity || 'architecture'}-graph.dot`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    setMenuOpen(false)
  }

  return (
    <header className="cs-toolbar" aria-label="Architecture toolbar">
      {/* Left: [Logo + CodeStruct] [Current file/project picker] */}
      <div className="cs-toolbar__left">
        <div className="cs-toolbar__brand-group">
          <span className="cs-toolbar__logo">
            <LogoIcon width={24} height={24} />
          </span>
          <span className="cs-toolbar__brand">CodeStruct</span>
        </div>

        {/* Project picker button */}
        <div className="cs-project-picker-wrapper" ref={pickerRef}>
          <button
            type="button"
            className="cs-project-picker-btn"
            onClick={() => setPickerOpen(!pickerOpen)}
            aria-expanded={pickerOpen}
            aria-haspopup="dialog"
            title={`Current analysis: ${currentIdentity}. Click to change or analyze.`}
            aria-label={`Current analysis: ${currentIdentity}`}
          >
            <span className="cs-project-picker-label">{currentIdentity}</span>
            <ChevronDownIcon width={14} height={14} />
          </button>

          {/* Project Picker Dialog / Popover */}
          {pickerOpen && (
            <div className="cs-project-picker-popover" role="dialog" aria-label="Project selection">
              <div className="cs-popover-header">
                <h3>Analysis project</h3>
                <button
                  type="button"
                  className="cs-popover-close"
                  onClick={() => setPickerOpen(false)}
                  aria-label="Close project picker"
                >
                  <CloseIcon width={14} height={14} />
                </button>
              </div>

              <div className="cs-popover-content">
                <p className="cs-popover-current">
                  <strong>Currently viewing:</strong> {currentIdentity}
                </p>

                {isEditorAnalysis ? (
                  <div className="cs-popover-notice">
                    <p>
                      This analysis was initiated from an active editor file.
                      To re-analyze, run <em>Tools → Analyze with CodeStruct</em> in Thonny.
                    </p>
                  </div>
                ) : (
                  <>
                    <label htmlFor="project-picker-select" className="cs-popover-label">
                      Configured projects
                    </label>
                    <div className="cs-popover-select-row">
                      <select
                        id="project-picker-select"
                        value={projectId}
                        onChange={(e) => onSelectProject?.(e.target.value)}
                        disabled={busy}
                        className="cs-popover-select"
                      >
                        <option value="">Select a configured project…</option>
                        {projects.map((p) => (
                          <option key={p.id} value={p.id} disabled={!p.available}>
                            {p.display_name}{p.available ? '' : ' (unavailable)'}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="cs-popover-submit-btn"
                        onClick={() => {
                          if (projectId) {
                            onSubmitProject?.(projectId)
                            setPickerOpen(false)
                          }
                        }}
                        disabled={!projectId || busy}
                      >
                        Analyze
                      </button>
                    </div>

                    {onRefresh && (
                      <div className="cs-popover-actions">
                        <button
                          type="button"
                          className="cs-popover-refresh-btn"
                          onClick={() => {
                            onRefresh()
                            setPickerOpen(false)
                          }}
                          disabled={!provenance || busy}
                          title={!provenance ? 'Select a project and choose Analyze project to run a new analysis.' : undefined}
                        >
                          <RefreshIcon width={14} height={14} />
                          <span>Refresh current analysis</span>
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right: [Search] [Fit] [Fullscreen] [More] */}
      <div className="cs-toolbar__right">
        {/* Search */}
        <div className="cs-toolbar__search" role="search">
          <span className="cs-toolbar__search-icon" aria-hidden="true">
            <SearchIcon width={16} height={16} />
          </span>
          <label htmlFor="architecture-search" className="sr-only">
            Search architecture
          </label>
          <input
            ref={searchInputRef}
            id="architecture-search"
            className="cs-toolbar__search-input"
            type="text"
            value={query}
            onChange={(e) => onQueryChange?.(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search architecture…"
            aria-label="Search architecture"
          />
          {query ? (
            <div className="cs-toolbar__search-actions">
              <span className="cs-toolbar__search-count" aria-live="polite">
                {resultCount ? `${activeIndex + 1}/${resultCount}` : '0'}
              </span>
              <button
                type="button"
                className="cs-toolbar__search-clear"
                onClick={() => {
                  onQueryChange?.('')
                  searchInputRef.current?.focus()
                }}
                title="Clear search"
                aria-label="Clear search"
              >
                <CloseIcon width={14} height={14} />
              </button>
            </div>
          ) : (
            <kbd className="cs-toolbar__search-kbd" title="Shortcut: Ctrl+K">
              Ctrl K
            </kbd>
          )}
        </div>

        {/* Fit button */}
        <button
          type="button"
          className="cs-toolbar__action"
          onClick={() => controller?.fitView?.()}
          title="Fit visible graph (F)"
          aria-label="Fit visible graph"
        >
          <FitIcon width={18} height={18} />
        </button>

        {/* Fullscreen / Focus mode button */}
        <button
          type="button"
          className={`cs-toolbar__action${focusMode ? ' cs-toolbar__action--active' : ''}`}
          onClick={onToggleFocusMode}
          title={focusMode ? 'Exit focus mode (Esc)' : 'Focus mode / Fullscreen (Shift+F)'}
          aria-label={focusMode ? 'Exit focus mode' : 'Focus mode / Fullscreen'}
        >
          {focusMode ? <ExitFullscreenIcon width={18} height={18} /> : <FullscreenIcon width={18} height={18} />}
        </button>

        {/* More button */}
        <div className="cs-toolbar__menu-wrapper" ref={menuRef}>
          <button
            type="button"
            className="cs-toolbar__action"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-expanded={menuOpen}
            aria-haspopup="true"
            title="More actions"
            aria-label="More actions"
          >
            <MoreIcon width={18} height={18} />
          </button>
          {menuOpen && (
            <div className="cs-toolbar__dropdown" role="menu">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onToggleTable?.()
                  setMenuOpen(false)
                }}
              >
                <TableIcon width={16} height={16} />
                <span>Accessible table view</span>
              </button>

              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onToggleDiagnostics?.()
                  setMenuOpen(false)
                }}
              >
                <DiagnosticsIcon width={16} height={16} />
                <span>Diagnostics drawer</span>
              </button>

              <button
                type="button"
                role="menuitem"
                onClick={handleExportJson}
                disabled={!graph}
              >
                <ExportIcon width={16} height={16} />
                <span>Export graph (JSON)</span>
              </button>

              <button
                type="button"
                role="menuitem"
                onClick={handleExportDot}
                disabled={!graph}
              >
                <ExportIcon width={16} height={16} />
                <span>Export Graphviz (DOT)</span>
              </button>

              <div className="cs-dropdown-divider" />

              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setAboutOpen(true)
                  setMenuOpen(false)
                }}
              >
                <span>About CodeStruct</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* About Dialog */}
      {aboutOpen && (
        <div className="cs-dialog-backdrop" onClick={() => setAboutOpen(false)}>
          <div className="cs-dialog" role="dialog" aria-labelledby="about-title" onClick={(e) => e.stopPropagation()}>
            <div className="cs-dialog-header">
              <h2 id="about-title">About CodeStruct</h2>
              <button type="button" className="cs-popover-close" onClick={() => setAboutOpen(false)} aria-label="Close dialog">
                <CloseIcon width={16} height={16} />
              </button>
            </div>
            <div className="cs-dialog-body">
              <div className="cs-about-brand">
                <LogoIcon width={36} height={36} />
                <div>
                  <strong>CodeStruct Architecture Explorer</strong>
                  <p className="cs-about-version">Version 0.1.0.dev0</p>
                </div>
              </div>
              <p>Analyze authorized Python projects and explore architectural structures, classes, call flows, and dependencies.</p>
              <div className="cs-about-shortcuts">
                <h4>Keyboard Shortcuts</h4>
                <ul>
                  <li><kbd>F</kbd> — Fit visible graph</li>
                  <li><kbd>Shift</kbd> + <kbd>F</kbd> — Focus mode</li>
                  <li><kbd>Ctrl</kbd> + <kbd>K</kbd> — Search architecture</li>
                  <li><kbd>Esc</kbd> — Exit focus mode or close active panel</li>
                  <li><kbd>+</kbd> / <kbd>-</kbd> — Zoom in / out</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
