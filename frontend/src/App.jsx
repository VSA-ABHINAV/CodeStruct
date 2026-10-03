import { useCallback, useEffect, useState } from 'react'
import Graph from './Graph.jsx'
import { analysisApi } from './api/analysisApi.js'
import { requestJson } from './api/client.js'
import { useAnalysisJob } from './features/architecture/useAnalysisJob.js'
import './App.css'

const CANCELLABLE = new Set(['submitted', 'validating', 'queued', 'scanning', 'parsing', 'resolving', 'building_graph', 'computing_metrics', 'cancellation_requested'])

function removeAnalysisIdFromUrl() {
  if (typeof window === 'undefined' || !window.history?.replaceState) return
  try {
    const url = new URL(window.location.href)
    let modified = false
    if (url.searchParams.has('analysis_id')) {
      url.searchParams.delete('analysis_id')
      modified = true
    }
    if (url.searchParams.has('session_token')) {
      url.searchParams.delete('session_token')
      modified = true
    }
    if (modified) {
      const search = url.searchParams.toString()
      const next = url.pathname + (search ? `?${search}` : '') + url.hash
      window.history.replaceState(window.history.state, '', next)
    }
  } catch {
    // Ignore in non-browser / test environments
  }
}

function getInitialUrlHandoff() {
  if (typeof window === 'undefined') return { analysisId: null, sessionToken: null }
  try {
    const params = new URLSearchParams(window.location.search)
    return {
      analysisId: params.get('analysis_id'),
      sessionToken: params.get('session_token'),
    }
  } catch {
    return { analysisId: null, sessionToken: null }
  }
}

function App({ api = analysisApi }) {
  const [initialHandoff] = useState(getInitialUrlHandoff)
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [projectsError, setProjectsError] = useState(null)
  const [projectId, setProjectId] = useState('')
  const [editorSession, setEditorSession] = useState(() => {
    if (initialHandoff.sessionToken) {
      return { token: initialHandoff.sessionToken, analysisId: initialHandoff.analysisId }
    }
    return null
  })
  const [navigationFeedback, setNavigationFeedback] = useState(null)
  const analysis = useAnalysisJob(api)

  useEffect(() => {
    let active = true
    api.projects()
      .then((items) => {
        if (!active) return
        setProjects(items)
        setProjectId((current) => current && items.some((item) => item.id === current) ? current : items.find((item) => item.available)?.id || '')
        setProjectsError(null)
      })
      .catch((error) => {
        if (active) setProjectsError(error.message)
      })
      .finally(() => {
        if (active) setProjectsLoading(false)
      })
    return () => { active = false }
  }, [api])

  const { load } = analysis
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      if (initialHandoff.analysisId) {
        load(initialHandoff.analysisId)
      }
      // Immediately scrub sensitive credentials & analysis_id from URL on mount
      if (initialHandoff.analysisId || initialHandoff.sessionToken) {
        removeAnalysisIdFromUrl()
      }
    } catch {
      // Ignore URL parsing errors
    }
  }, [load, initialHandoff])

  const state = analysis.graphLoading ? 'retrieving_graph' : analysis.job?.cache_hit ? 'cache_hit' : analysis.job?.state || (analysis.submitting ? 'validating' : 'initial')
  const progress = analysis.job?.progress
  const busy = analysis.submitting || Boolean(analysis.job && !analysis.job.terminal)
  const selectedProject = projects.find((p) => p.id === projectId)

  const handleSelectProject = (newProjectId) => {
    setProjectId(newProjectId)
    setEditorSession(null)
    setNavigationFeedback(null)
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!projectId || busy) return
    removeAnalysisIdFromUrl()
    setEditorSession(null)
    setNavigationFeedback(null)
    analysis.submit({ root_id: projectId, relative_path: '.' })
  }

  // Source navigation: POST to the backend navigate endpoint so that Thonny
  // (which polls /api/v1/editor/navigate/pending) can open the correct file.
  // The session_token is the active capability ID (cap_...) passed from Thonny
  // via URL or stored in provenance.
  const handleNavigateSource = useCallback((loc) => {
    if (!loc) return
    const path = loc.path
    const line = loc.line ?? loc.startLine
    const column = loc.column ?? loc.startColumn ?? null
    const currentAnalysisId = analysis.job?.analysis_id
    const sessionToken =
      (editorSession && (!editorSession.analysisId || editorSession.analysisId === currentAnalysisId)
        ? editorSession.token
        : null) ||
      analysis.provenance?.capability_id ||
      (analysis.provenance?.root_id?.startsWith('cap_') ? analysis.provenance.root_id : null)

    if (!sessionToken) {
      setNavigationFeedback({
        status: 'failed',
        message: 'Editor navigation unavailable: No active IDE session is connected for this analysis.',
      })
      return
    }

    if (!path || !line) {
      setNavigationFeedback({
        status: 'failed',
        message: 'Editor navigation unavailable: Selected element has no source location.',
      })
      return
    }

    setNavigationFeedback({
      status: 'pending',
      message: `Navigating to ${path}:${line} in editor…`,
    })

    requestJson('/api/v1/editor/navigate', {
      method: 'POST',
      body: JSON.stringify({ session_token: sessionToken, relative_path: path, line, column }),
    })
      .then(() => {
        setNavigationFeedback({
          status: 'success',
          message: `Navigation command sent to editor (${path}:${line}).`,
        })
      })
      .catch((err) => {
        setNavigationFeedback({
          status: 'failed',
          message: `Editor navigation unavailable: ${err?.message || 'Connection refused or session expired'}.`,
        })
      })
  }, [analysis.job?.analysis_id, analysis.provenance, editorSession])

  return <div className={`app-shell${analysis.graph ? ' app-shell--active' : ''}`}>
    {!analysis.graph ? (
      <header className="application-header">
        <div><h1>CodeStruct</h1><p>Analyze an authorized Python project and explore its architecture.</p><p className="version">Version {__CODESTRUCT_VERSION__}</p></div>
        <form className="analysis-form" onSubmit={handleSubmit}>
          <label htmlFor="project-selector">Configured project</label>
          <p id="project-help" className="form-help">Choose a server-authorized project. Private server paths are never displayed.</p>
          <div>
            <select id="project-selector" aria-describedby="project-help" value={projectId} onChange={(event) => handleSelectProject(event.target.value)} disabled={projectsLoading || busy}>
              <option value="">{projectsLoading ? 'Loading configured projects…' : 'Select a project'}</option>
              {projects.map((project) => <option key={project.id} value={project.id} disabled={!project.available}>{project.display_name}{project.available ? '' : ' (unavailable)'}</option>)}
            </select>
            <button type="submit" disabled={!projectId || projectsLoading || busy}>Analyze project</button>
            {analysis.job && CANCELLABLE.has(analysis.job.state) && <button type="button" onClick={analysis.cancel} disabled={analysis.cancelling || analysis.job.state === 'cancellation_requested'}>{analysis.cancelling || analysis.job.state === 'cancellation_requested' ? 'Stopping…' : 'Cancel'}</button>}
          </div>
        </form>
      </header>
    ) : (
      /* Retained in DOM for testing & assistive accessibility fallback when explorer is active */
      <div className="cs-compat-controls" style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', border: 0 }}>
        <form onSubmit={handleSubmit}>
          <label htmlFor="project-selector">Configured project</label>
          <select id="project-selector" value={projectId} onChange={(event) => handleSelectProject(event.target.value)}>
            {projects.map((project) => <option key={project.id} value={project.id} disabled={!project.available}>{project.display_name}{project.available ? '' : ' (unavailable)'}</option>)}
          </select>
          <button type="button" onClick={() => analysis.provenance && analysis.submit(analysis.provenance, { refresh: true })} disabled={!analysis.provenance || busy}>Refresh analysis</button>
          {!analysis.provenance && <p className="form-help">Select a project and choose Analyze project to run a new analysis.</p>}
        </form>
      </div>
    )}
    {projectsError && <p role="alert">Configured projects could not be loaded. {projectsError}</p>}
    {!projectsLoading && !projectsError && !projects.length && <p role="status">No projects are configured. Ask the local administrator to add an authorized project alias.</p>}
    {!analysis.graph && progress && <p className="job-progress" role="status">{analysis.graphLoading ? 'analysis complete · retrieving bounded graph' : `${progress.message_code.replaceAll('_', ' ').toLowerCase()} · ${progress.percent ?? '—'}%`}</p>}
    {navigationFeedback && (
      <div
        role={navigationFeedback.status === 'failed' ? 'alert' : 'status'}
        className={`navigation-feedback navigation-feedback--${navigationFeedback.status}`}
        aria-live="polite"
      >
        {navigationFeedback.message}
      </div>
    )}
    <Graph
      graph={analysis.graph}
      state={state}
      error={analysis.error?.message || null}
      onLoadMore={analysis.loadMore}
      pageLoading={analysis.pageLoading}
      projectName={selectedProject?.display_name || ''}
      projects={projects}
      projectId={projectId}
      onSelectProject={handleSelectProject}
      onSubmitProject={(rootId) => {
        removeAnalysisIdFromUrl()
        setEditorSession(null)
        setNavigationFeedback(null)
        analysis.submit({ root_id: rootId, relative_path: '.' })
      }}
      onRefresh={() => analysis.provenance && analysis.submit(analysis.provenance, { refresh: true })}
      provenance={analysis.provenance}
      busy={busy}
      analysisId={analysis.job?.analysis_id || ''}
      onNavigateSource={handleNavigateSource}
    />
  </div>
}

export default App


