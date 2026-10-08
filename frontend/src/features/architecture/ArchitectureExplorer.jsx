import { useCallback, useEffect, useMemo, useState } from 'react'
import ArchitectureGraph from './ArchitectureGraph.jsx'
import AccessibleGraphTable from './AccessibleGraphTable.jsx'
import DetailsPanel from './DetailsPanel.jsx'
import DiagnosticsDrawer from './DiagnosticsDrawer.jsx'
import TopToolbar from './TopToolbar.jsx'
import LeftSidebar from './LeftSidebar.jsx'
import GraphStatus from './GraphStatus.jsx'
import FilterPanel from './FilterPanel.jsx'
import { emptyNormalizedGraph, normalizeGraph } from './graphAdapter.js'
import {
  DEFAULT_FILTERS,
  DEFAULT_VISIBILITY,
  applyVisibility,
  applyViewMode,
  exceedsGraphThreshold,
  filterGraph,
  getAnalysisIdentity,
  nextSearchIndex,
  overviewGraph,
  searchNodes,
  selectElementDetails,
} from './graphSelectors.js'
import { layoutGraph } from './graphLayout.js'
import { DEFAULT_LARGE_GRAPH_THRESHOLD } from './explorerConfig.js'
import './architecture.css'

export default function ArchitectureExplorer({
  graph: input,
  state = 'completed',
  error = null,
  onNavigateSource = null,
  onLoadMore = null,
  pageLoading = false,
  largeGraphThreshold = DEFAULT_LARGE_GRAPH_THRESHOLD,
  projectName = '',
  projects = [],
  projectId = '',
  onSelectProject = null,
  onSubmitProject = null,
  onRefresh = null,
  provenance = null,
  busy = false,
  api = null,
}) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [query, setQuery] = useState('')
  const [activeMatch, setActiveMatch] = useState(0)
  const [selection, setSelection] = useState(null)
  const [view, setView] = useState('graph')
  const [sidebarView, setSidebarView] = useState('overview')
  const [visibility, setVisibility] = useState(DEFAULT_VISIBILITY)
  const [diagnosticSeverity, setDiagnosticSeverity] = useState('all')
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false)
  const [controller, setController] = useState(null)
  const [renderLargeGraph, setRenderLargeGraph] = useState(false)
  const [focusMode, setFocusMode] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const reducedMotion = useMemo(
    () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    []
  )

  const contract = useMemo(() => {
    if (!input) return { graph: emptyNormalizedGraph(), error: null }
    try {
      return { graph: normalizeGraph(input), error: null }
    } catch (caught) {
      return { graph: emptyNormalizedGraph(), error: caught }
    }
  }, [input])
  const normalized = contract.graph

  const currentIdentity = useMemo(
    () => getAnalysisIdentity(normalized, provenance, projects) || projectName || 'Architecture',
    [normalized, provenance, projects, projectName]
  )

  // Pipeline: normalize → filter → visibility → view mode → large-graph cutoff → layout
  const filtered = useMemo(() => filterGraph(normalized, filters), [normalized, filters])
  const withVisibility = useMemo(() => applyVisibility(filtered, visibility), [filtered, visibility])
  const withView = useMemo(() => applyViewMode(withVisibility, sidebarView), [withVisibility, sidebarView])
  const matches = useMemo(() => searchNodes(withView, query), [withView, query])
  const matchIds = useMemo(() => matches.map((item) => item.id), [matches])
  const isLarge = exceedsGraphThreshold(normalized, largeGraphThreshold)
  const presentation = useMemo(
    () => (isLarge && !renderLargeGraph ? overviewGraph(withView) : withView),
    [withView, isLarge, renderLargeGraph]
  )
  const positioned = useMemo(
    () => layoutGraph(presentation.nodes, presentation.edges),
    [presentation.nodes, presentation.edges]
  )

  const details = useMemo(() => selectElementDetails(normalized, selection), [normalized, selection])

  const activeState = contract.error?.code === 'UNSUPPORTED_SCHEMA'
    ? 'unsupported_schema'
    : contract.error
      ? 'failed'
      : error
        ? 'failed'
        : isLarge && !renderLargeGraph
          ? 'large_graph'
          : input && !normalized.nodes.length
            ? 'empty'
            : normalized.metadata.partial
              ? 'partially_completed'
              : state
  const assertive = ['validation_failed', 'failed', 'unsupported_schema'].includes(activeState)

  const boundedActiveMatch = matches.length ? activeMatch % matches.length : 0
  const setGraphController = useCallback((value) => setController(() => value), [])

  const activateMatch = useCallback(() => {
    const match = matches[boundedActiveMatch]
    if (!match) return
    setSelection({ type: 'node', id: match.id })
    setView('graph')
    // If it's a nested method, center its owning class so it's in view
    if (match.kind === 'method' && match.parentId) {
      controller?.center(match.parentId)
    } else {
      controller?.center(match.id)
    }
  }, [boundedActiveMatch, controller, matches])

  const stepMatch = (step) => {
    if (!matches.length) return
    const next = nextSearchIndex(boundedActiveMatch, step, matches.length)
    setActiveMatch(next)
    setSelection({ type: 'node', id: matches[next].id })
    if (matches[next].kind === 'method' && matches[next].parentId) {
      controller?.center(matches[next].parentId)
    } else {
      controller?.center(matches[next].id)
    }
  }

  // Toggle Focus Mode / Fullscreen
  const toggleFocusMode = useCallback(async () => {
    if (!document.fullscreenElement && !focusMode) {
      try {
        if (document.documentElement.requestFullscreen) {
          await document.documentElement.requestFullscreen()
        }
      } catch {
        // Fullscreen API not allowed or available, fallback to focus mode
      }
      setFocusMode(true)
    } else {
      if (document.fullscreenElement && document.exitFullscreen) {
        await document.exitFullscreen().catch(() => {})
      }
      setFocusMode(false)
    }
    setTimeout(() => controller?.fitView?.(), 150)
  }, [controller, focusMode])

  // Sync fullscreen exit via browser UI
  useEffect(() => {
    function onFullscreenChange() {
      if (!document.fullscreenElement && focusMode) {
        setFocusMode(false)
        setTimeout(() => controller?.fitView?.(), 150)
      }
    }
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
  }, [controller, focusMode])

  // Global keyboard shortcuts (F: fit, Shift+F: focus mode, Esc: exit, +/-: zoom)
  useEffect(() => {
    function handleGlobalKey(e) {
      const target = e.target
      const isInput = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable)
      if (isInput) return

      if (e.key === 'F' && e.shiftKey) {
        e.preventDefault()
        toggleFocusMode()
      } else if (e.key.toLowerCase() === 'f' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault()
        controller?.fitView?.()
      } else if (e.key === 'Escape') {
        if (focusMode) {
          setFocusMode(false)
          setTimeout(() => controller?.fitView?.(), 150)
        } else if (diagnosticsOpen) {
          setDiagnosticsOpen(false)
        } else if (selection) {
          setSelection(null)
        }
      } else if (e.key === '+' || e.key === '=') {
        e.preventDefault()
        controller?.zoomIn?.()
      } else if (e.key === '-' || e.key === '_') {
        e.preventDefault()
        controller?.zoomOut?.()
      }
    }
    window.addEventListener('keydown', handleGlobalKey)
    return () => window.removeEventListener('keydown', handleGlobalKey)
  }, [controller, diagnosticsOpen, focusMode, selection, toggleFocusMode])

  const selectedId = selection?.type === 'node' ? selection.id : null

  return (
    <main className={`architecture-explorer cs-explorer${focusMode ? ' cs-explorer--focus-mode' : ''}`}>
      {/* Remove completed-state card; only show status banner for partial, large, failed, or schema errors */}
      {activeState !== 'completed' && (
        <GraphStatus state={activeState} detail={contract.error?.message || error} assertive={assertive} />
      )}

      {input && !contract.error && (
        <>
          {/* Single Vertically Aligned Header */}
          <TopToolbar
            currentIdentity={currentIdentity}
            projects={projects}
            projectId={projectId}
            onSelectProject={onSelectProject}
            onSubmitProject={onSubmitProject}
            onRefresh={onRefresh}
            provenance={provenance}
            busy={busy}
            query={query}
            onQueryChange={(value) => {
              setQuery(value)
              setActiveMatch(0)
            }}
            resultCount={matches.length}
            activeIndex={boundedActiveMatch}
            onStep={stepMatch}
            onActivate={activateMatch}
            controller={controller}
            onToggleTable={() => setView(view === 'table' ? 'graph' : 'table')}
            onToggleDiagnostics={() => setDiagnosticsOpen(!diagnosticsOpen)}
            focusMode={focusMode}
            onToggleFocusMode={toggleFocusMode}
            graph={normalized}
          />

          {/* Advanced filters (collapsed by default) */}
          <section className="cs-explorer__filters" aria-labelledby="find-title">
            <h2 id="find-title" className="sr-only">
              Find and narrow
            </h2>
            <FilterPanel filters={filters} onChange={setFilters} onReset={() => setFilters(DEFAULT_FILTERS)} />
            <p className="visible-counts" aria-live="polite">
              Showing {presentation.counts?.visibleNodes ?? withView.nodes.length} of{' '}
              {filtered.counts?.totalNodes ?? normalized.nodes.length} entities and{' '}
              {presentation.counts?.visibleEdges ?? withView.edges.length} of{' '}
              {filtered.counts?.totalEdges ?? normalized.edges.length} relationships.
            </p>
            {normalized.page?.partial_load && (
              <p className="compact-status" role="status">
                Loaded {normalized.page.returned_nodes} of {normalized.page.total_nodes} entities and{' '}
                {normalized.page.returned_edges} of {normalized.page.total_edges} relationships. Unloaded elements
                still exist and are not represented by the current table or canvas.
              </p>
            )}
            {normalized.page?.partial_load && (
              <div className="partial-load" role="status">
                <p>
                  Only {normalized.page.returned_nodes} of {normalized.page.total_nodes} entities are loaded;
                  search and the accessible table cover this loaded slice.
                </p>
                {normalized.page.next_cursor && onLoadMore && (
                  <button type="button" onClick={onLoadMore} disabled={pageLoading}>
                    {pageLoading ? 'Loading more…' : 'Load more graph data'}
                  </button>
                )}
              </div>
            )}
          </section>

          {isLarge && !renderLargeGraph && (
            <section className="large-graph-actions">
              <p>The bounded overview changes presentation only; the complete result remains available in the table.</p>
              <button type="button" onClick={() => setRenderLargeGraph(true)}>
                Render complete graph anyway
              </button>
              <button type="button" onClick={() => setView('table')}>
                Open complete table
              </button>
            </section>
          )}

          {/* Dynamic Workspace: Nav rail + Graph canvas + On-demand details drawer */}
          <section className="cs-explorer__workspace" aria-label="Architecture workspace">
            {!focusMode && (
              <LeftSidebar
                activeView={sidebarView}
                onViewChange={setSidebarView}
                visibility={visibility}
                onVisibilityChange={setVisibility}
                collapsed={sidebarCollapsed}
                onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
              />
            )}

            <div className="cs-explorer__main">
              {view === 'graph' ? (
                <ArchitectureGraph
                  graph={presentation}
                  positionedNodes={positioned}
                  matchIds={matchIds}
                  reducedMotion={reducedMotion}
                  selectedId={selectedId}
                  onSelect={setSelection}
                  onController={setGraphController}
                  viewMode={sidebarView}
                  onNavigateSource={onNavigateSource}
                />
              ) : (
                <AccessibleGraphTable graph={filtered} selected={selection} onSelect={setSelection} />
              )}
              {!withView.nodes.length && (
                <p className="empty-filter">
                  Filters hide every entity. Reset filters to restore the result; hidden data has not been removed.
                </p>
              )}

              {/* Floating Exit button in Focus Mode */}
              {focusMode && (
                <button
                  type="button"
                  className="cs-focus-mode-exit"
                  onClick={toggleFocusMode}
                  aria-label="Exit focus mode (Esc)"
                  title="Exit focus mode (Esc)"
                >
                  Exit focus mode (Esc)
                </button>
              )}
            </div>

            {/* Right Drawer: Only rendered when an element is selected */}
            {!focusMode && details && (
              <DetailsPanel
                details={details}
                onClose={() => setSelection(null)}
                onNavigateSource={onNavigateSource}
                onSelect={(sel) => {
                  setSelection(sel)
                  if (sel?.type === 'node') controller?.center(sel.id)
                }}
                onCenter={(nodeId) => controller?.center(nodeId)}
                graph={normalized}
                onLoadMore={onLoadMore}
                pageLoading={pageLoading}
                {...(api ? { api } : {})}
              />
            )}
          </section>

          {/* Diagnostics drawer (on-demand bottom panel) */}
          <DiagnosticsDrawer
            diagnostics={normalized.diagnostics}
            open={diagnosticsOpen}
            onClose={() => setDiagnosticsOpen(false)}
            severity={diagnosticSeverity}
            onSeverity={setDiagnosticSeverity}
            onSelect={setSelection}
          />
        </>
      )}
    </main>
  )
}
