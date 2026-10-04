import { useEffect, useMemo, useState } from 'react'
import { analysisApi } from '../../api/analysisApi.js'

const NODE_KIND_LABELS = {
  project: 'Project',
  directory: 'Directory',
  file: 'File',
  package: 'Package',
  module: 'Module',
  class: 'Class',
  function: 'Function',
  async_function: 'Async function',
  method: 'Method',
  async_method: 'Async method',
  external_module: 'External module',
  unresolved_symbol: 'Unresolved symbol',
}

const RELATIONSHIP_KIND_LABELS = {
  contains: 'Contains',
  defines: 'Defines',
  imports: 'Imports',
  imports_symbol: 'Imports symbol',
  inherits: 'Inherits from',
  calls: 'Calls',
  constructs: 'Constructs',
  references: 'References',
  type_annotation: 'Type annotation',
}

const RESOLUTION_BADGES = {
  resolved: { symbol: '✓', label: 'Resolved', variant: 'success' },
  unresolved: { symbol: '?', label: 'Unresolved', variant: 'warning' },
  ambiguous: { symbol: '~', label: 'Ambiguous', variant: 'warning' },
  syntactic_only: { symbol: '○', label: 'Syntactic only', variant: 'muted' },
  not_applicable: { symbol: '—', label: 'Not applicable', variant: 'muted' },
}

const EVIDENCE_ORIGIN_LABELS = {
  static_ast: 'Static AST evidence',
  import_scan: 'Import scan',
  type_inference: 'Type inference',
  heuristic: 'Heuristic evidence',
}

const CONFIDENCE_LABELS = {
  exact: 'Exact static match',
  probable: 'Probable static match',
  heuristic: 'Heuristic match',
  unknown: 'Unknown / Unresolved',
}

const REASON_LABELS = {
  EXACT_STATIC_TARGET: 'Exact static target resolved',
  NO_SUPPORTED_STATIC_TARGET: 'No supported static target found',
  AMBIGUOUS_MATCH: 'Multiple candidate targets found',
  DYNAMIC_DISPATCH: 'Dynamic dispatch reference',
}

const CLASSIFICATION_LABELS = {
  internal: 'Internal source unit',
  external: 'External library module',
  unresolved: 'Unresolved symbol',
  missing: 'Missing target',
}

function humanize(str) {
  if (!str) return ''
  return str.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase())
}

function formatSpan(location) {
  if (!location) return 'Unavailable'
  if (location.startLine) {
    const start = `${location.path}:${location.startLine}:${location.startColumn || 1}`
    return location.endLine ? `${start}–${location.endLine}:${location.endColumn || 1}` : start
  }
  return location.path || 'Unavailable'
}

function CopyButton({ text, label = 'Copy to clipboard' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    if (!text) return
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <span className="copy-container">
      <button
        type="button"
        className="copy-button"
        onClick={handleCopy}
        title={label}
        aria-label={label}
      >
        <span aria-hidden="true">⎘</span>
        <span className="copy-label">{copied ? 'Copied!' : 'Copy'}</span>
      </button>
      <span className="sr-only" aria-live="polite">
        {copied ? `${label} copied to clipboard` : ''}
      </span>
    </span>
  )
}

export default function DetailsPanel({
  details,
  onClose,
  onNavigateSource,
  onSelect = null,
  onCenter = null,
  graph = null,
  onLoadMore = null,
  pageLoading = false,
  api = analysisApi,
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose?.()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const [explanationMap, setExplanationMap] = useState({})
  const [explainLoadingMap, setExplainLoadingMap] = useState({})
  const [explainErrorMap, setExplainErrorMap] = useState({})

  const selectedItemId = details?.item?.id
  const explanation = selectedItemId ? explanationMap[selectedItemId] : null
  const explainLoading = selectedItemId ? Boolean(explainLoadingMap[selectedItemId]) : false
  const explainError = selectedItemId ? explainErrorMap[selectedItemId] : null

  const handleFetchExplanation = async () => {
    const analysisId = graph?.metadata?.analysis_id || graph?.metadata?.result_id
    if (!analysisId || !selectedItemId) return
    setExplainLoadingMap((prev) => ({ ...prev, [selectedItemId]: true }))
    setExplainErrorMap((prev) => ({ ...prev, [selectedItemId]: null }))
    try {
      const data = await api.explain(analysisId, selectedItemId)
      setExplanationMap((prev) => ({ ...prev, [selectedItemId]: data }))
    } catch (err) {
      setExplainErrorMap((prev) => ({ ...prev, [selectedItemId]: err.message || 'Error generating explanation' }))
    } finally {
      setExplainLoadingMap((prev) => ({ ...prev, [selectedItemId]: false }))
    }
  }

  const nodesMap = useMemo(() => {
    const map = new Map()
    if (graph?.nodes) {
      for (const n of graph.nodes) {
        map.set(n.id, n)
      }
    }
    return map
  }, [graph])

  const evidenceMap = useMemo(() => {
    const map = new Map()
    if (graph?.evidence) {
      for (const ev of graph.evidence) {
        map.set(ev.id, ev)
      }
    }
    return map
  }, [graph])

  const diagnosticsMap = useMemo(() => {
    const map = new Map()
    if (graph?.diagnostics) {
      for (const d of graph.diagnostics) {
        map.set(d.id, d)
      }
    }
    return map
  }, [graph])

  if (!details) {
    return (
      <aside className="details-panel details-panel--empty" aria-labelledby="details-title">
        <div className="panel-heading">
          <h2 id="details-title">Details</h2>
        </div>
        <div className="empty-selection-prompt">
          <span className="empty-icon" aria-hidden="true">🔍</span>
          <p className="empty-lead">No element selected</p>
          <p className="muted">
            Select an entity or relationship from the graph or table to inspect its architecture, hierarchy, dependencies, and diagnostics.
          </p>
        </div>
      </aside>
    )
  }

  const isNode = details.type === 'node'
  const item = details.item
  const location = isNode ? item.location : details.evidence[0]?.location

  const renderRelationshipCard = (edge, direction) => {
    const isIncoming = direction === 'incoming'
    const endpointId = isIncoming ? edge.sourceId : edge.targetId
    const endpointNode = endpointId ? nodesMap.get(endpointId) : null
    const isLoaded = Boolean(endpointNode)
    const res = RESOLUTION_BADGES[edge.resolutionStatus] || { symbol: '·', label: humanize(edge.resolutionStatus) || 'Not applicable', variant: 'muted' }
    const kindLabel = RELATIONSHIP_KIND_LABELS[edge.kind] || humanize(edge.kind)
    const confidenceText = CONFIDENCE_LABELS[edge.confidence] || (edge.confidence ? humanize(edge.confidence) : null)

    const firstEvidence = edge.evidenceIds?.[0] ? evidenceMap.get(edge.evidenceIds[0]) : null
    const evidenceOrigin = firstEvidence?.origin
      ? EVIDENCE_ORIGIN_LABELS[firstEvidence.origin] || humanize(firstEvidence.origin)
      : null
    const edgeSpan = formatSpan(firstEvidence?.location || edge.location)

    const edgeDiags = (edge.diagnosticIds || [])
      .map((id) => diagnosticsMap.get(id))
      .filter(Boolean)

    const endpointClassification = edge.targetClassification || (endpointNode ? endpointNode.classification : 'internal')

    return (
      <li key={edge.id} className="relationship-card">
        <div className="relationship-card-header">
          <div className="direction-and-kind">
            <span
              className="relationship-direction"
              title={isIncoming ? 'Incoming dependency' : 'Outgoing dependency'}
              aria-label={isIncoming ? 'Incoming' : 'Outgoing'}
            >
              {isIncoming ? '←' : '→'}
            </span>
            <span className="relationship-kind-badge">{kindLabel}</span>
          </div>
          <span className={`details-badge badge--${res.variant}`}>
            <span aria-hidden="true" className="badge-symbol">{res.symbol}</span> {res.label}
          </span>
        </div>

        <div className="relationship-endpoint">
          <span className="endpoint-label">{isIncoming ? 'From:' : 'To:'}</span>{' '}
          {isLoaded ? (
            <button
              type="button"
              className="link-button endpoint-name"
              onClick={() => onSelect?.({ type: 'node', id: endpointNode.id })}
              aria-label={`Select ${endpointNode.displayName}`}
              title={`Select ${endpointNode.displayName}`}
            >
              {endpointNode.displayName}
              <span className="endpoint-kind"> ({NODE_KIND_LABELS[endpointNode.kind] || humanize(endpointNode.kind)})</span>
            </button>
          ) : (
            <span className="unloaded-endpoint">
              <span className="unloaded-text">{edge.targetReference || endpointId || 'Unresolved target'}</span>
              <span className="badge-unloaded">
                {endpointClassification === 'external'
                  ? ' [External target]'
                  : endpointClassification === 'missing'
                    ? ' [Missing target]'
                    : ' [Unloaded / Paginated]'}
              </span>
            </span>
          )}
        </div>

        <div className="relationship-meta-grid">
          {confidenceText && (
            <div className="meta-item">
              <span className="meta-label">Confidence:</span>
              <span className="meta-val">{confidenceText}</span>
            </div>
          )}
          {evidenceOrigin && (
            <div className="meta-item">
              <span className="meta-label">Evidence:</span>
              <span className="meta-val">{evidenceOrigin}</span>
            </div>
          )}
          {edgeSpan && edgeSpan !== 'Unavailable' && (
            <div className="meta-item">
              <span className="meta-label">Location:</span>
              <code className="meta-val">{edgeSpan}</code>
            </div>
          )}
          {edgeDiags.length > 0 && (
            <div className="meta-item diagnostic-alert">
              <span className="meta-label">Diagnostic:</span>
              <span className="badge-diag-alert">
                ⚠ {edgeDiags.map((d) => d.code).join(', ')}
              </span>
            </div>
          )}
        </div>

        <div className="relationship-actions">
          <button
            type="button"
            className="action-link"
            onClick={() => onSelect?.({ type: 'edge', id: edge.id })}
          >
            Inspect relationship
          </button>
          {isLoaded && onCenter && (
            <button
              type="button"
              className="action-link"
              onClick={() => onCenter(endpointNode.id)}
            >
              Center entity
            </button>
          )}
          {!isLoaded && onLoadMore && (
            <button
              type="button"
              className="action-link action-load-more"
              onClick={onLoadMore}
              disabled={pageLoading}
            >
              {pageLoading ? 'Loading…' : 'Load more graph data'}
            </button>
          )}
        </div>
      </li>
    )
  }

  return (
    <aside className="details-panel" aria-labelledby="details-title">
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {isNode
          ? `Selected entity: ${item.displayName}, ${NODE_KIND_LABELS[item.kind] || humanize(item.kind)}`
          : `Selected relationship: ${RELATIONSHIP_KIND_LABELS[item.kind] || humanize(item.kind)} from ${details.source?.displayName || item.sourceId} to ${details.target?.displayName || item.targetReference || 'unresolved target'}`}
      </div>

      <div className="panel-heading">
        <div>
          <h2 id="details-title">{isNode ? 'Entity details' : 'Relationship evidence'}</h2>
          <p className="panel-subtitle">
            {isNode ? item.displayName : `${RELATIONSHIP_KIND_LABELS[item.kind] || humanize(item.kind)} relationship`}
          </p>
        </div>
        <button
          type="button"
          className="close-panel-button"
          onClick={onClose}
          aria-label="Close details panel"
          title="Close details (Esc)"
        >
          ✕ Close
        </button>
      </div>

      {isNode ? (
        <>
          {/* 1. Overview */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="entity-overview-heading">Overview</h3>
            </summary>
            <dl className="details-dl">
              <dt>Name</dt>
              <dd className="details-val-row">
                <strong className="entity-title">{item.displayName}</strong>
              </dd>

              <dt>Kind</dt>
              <dd className="details-badge badge--kind" data-kind={item.kind}>
                {NODE_KIND_LABELS[item.kind] || humanize(item.kind)}
              </dd>

              <dt>Qualified name</dt>
              <dd className="details-val-row">
                <code className="code-wrap">{item.qualifiedName || 'Unavailable in this contract'}</code>
                {item.qualifiedName && (
                  <CopyButton text={item.qualifiedName} label="Copy qualified name" />
                )}
              </dd>

              <dt>Diagnostics</dt>
              <dd>
                <span className={`count-pill ${details.diagnostics.length ? 'count-pill--alert' : ''}`}>
                  {details.diagnostics.length}
                </span>
              </dd>

              <dt>Incoming</dt>
              <dd>
                <span className="count-pill">{details.incoming.length}</span>
              </dd>

              <dt>Outgoing</dt>
              <dd>
                <span className="count-pill">{details.outgoing.length}</span>
              </dd>
            </dl>
          </details>

          {/* 2. Source location */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="entity-location-heading">Source location</h3>
            </summary>
            <dl className="details-dl">
              <dt>Project path</dt>
              <dd className="details-val-row">
                <code className="code-wrap">{item.location?.path || 'Unavailable'}</code>
                {item.location?.path && (
                  <CopyButton text={item.location.path} label="Copy project path" />
                )}
              </dd>

              <dt>Start position</dt>
              <dd>
                {item.location?.startLine != null
                  ? `Line ${item.location.startLine}, Col ${item.location.startColumn || 1}`
                  : 'Unavailable'}
              </dd>

              <dt>End position</dt>
              <dd>
                {item.location?.endLine != null
                  ? `Line ${item.location.endLine}, Col ${item.location.endColumn || 1}`
                  : 'Unavailable'}
              </dd>

              <dt>Source span</dt>
              <dd className="details-val-row">
                <code>{formatSpan(item.location)}</code>
                {item.location?.path && (
                  <CopyButton text={formatSpan(item.location)} label="Copy source span" />
                )}
              </dd>
            </dl>

            {/* Open in editor button — only shown when source location is available and
                the host application has wired in an editor navigation handler. */}
            {onNavigateSource && item.location?.path && item.location?.startLine != null && (
              <div className="source-navigate-row">
                <button
                  type="button"
                  id={`open-in-editor-${item.id}`}
                  className="source-navigate-button"
                  onClick={() =>
                    onNavigateSource({
                      path: item.location.path,
                      line: item.location.startLine,
                      column: item.location.startColumn || null,
                    })
                  }
                  title={`Open ${item.location.path} at line ${item.location.startLine} in editor`}
                  aria-label={`Open ${item.location.path} at line ${item.location.startLine} in editor`}
                >
                  <span aria-hidden="true">⌖</span> Open in editor
                </button>
              </div>
            )}
          </details>

          {/* Architecture metrics */}
          {(item.attributes?.fan_in != null || item.attributes?.fan_out != null || item.attributes?.centrality != null) && (
            <details className="details-section" open>
              <summary className="details-section-summary">
                <h3 id="entity-metrics-heading">Architecture metrics</h3>
              </summary>
              <dl className="details-dl">
                <dt>Fan-in (incoming)</dt>
                <dd>
                  <span className="count-pill">{item.attributes.fan_in ?? details.incoming.length}</span>
                </dd>

                <dt>Fan-out (outgoing)</dt>
                <dd>
                  <span className="count-pill">{item.attributes.fan_out ?? details.outgoing.length}</span>
                </dd>

                {item.attributes?.instability != null && (
                  <>
                    <dt>Instability (I)</dt>
                    <dd>
                      <code className="code-wrap">{item.attributes.instability}</code>
                    </dd>
                  </>
                )}

                {item.attributes?.centrality != null && (
                  <>
                    <dt>Degree centrality</dt>
                    <dd>
                      <code className="code-wrap">{item.attributes.centrality}</code>
                    </dd>
                  </>
                )}

                {item.attributes?.in_cycle != null && (
                  <>
                    <dt>Dependency cycle</dt>
                    <dd>
                      <span className={`count-pill ${item.attributes.in_cycle === 'true' ? 'count-pill--alert' : ''}`}>
                        {item.attributes.in_cycle === 'true' ? 'In cycle' : 'No cycle'}
                      </span>
                    </dd>
                  </>
                )}

                {item.attributes?.community_id != null && (
                  <>
                    <dt>Community cluster</dt>
                    <dd>
                      <span className="count-pill">Cluster #{item.attributes.community_id}</span>
                    </dd>
                  </>
                )}

                {item.attributes?.runtime_calls != null && (
                  <>
                    <dt>Runtime profiling</dt>
                    <dd>
                      <span className="count-pill">
                        {item.attributes.runtime_calls} call{item.attributes.runtime_calls === '1' || item.attributes.runtime_calls === 1 ? '' : 's'}
                        {item.attributes.runtime_duration_ms != null ? ` (${item.attributes.runtime_duration_ms} ms)` : ''}
                      </span>
                    </dd>
                  </>
                )}
              </dl>
            </details>
          )}

          {/* Architecture explanation */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="entity-explanation-heading">Architecture explanation</h3>
            </summary>
            <div className="explanation-container" style={{ padding: '0.5rem 0' }}>
              {!explanation && !explainLoading && (
                <button
                  type="button"
                  className="open-editor-button"
                  onClick={handleFetchExplanation}
                  aria-label="Generate architecture explanation"
                  title="Generate semantic architectural summary and risk analysis"
                >
                  <span aria-hidden="true">💡</span> Explain entity architecture
                </button>
              )}
              {explainLoading && (
                <p className="muted" aria-live="polite">Analyzing entity architecture...</p>
              )}
              {explainError && (
                <p className="error-message" role="alert">{explainError}</p>
              )}
              {explanation && (
                <div className="explanation-content">
                  <div style={{ marginBottom: '0.5rem' }}>
                    <span className="count-pill" style={{ fontWeight: 'bold' }}>{explanation.role}</span>
                    <span className="muted" style={{ marginLeft: '0.5rem', fontSize: '0.8rem' }}>({explanation.provider})</span>
                  </div>
                  <p style={{ margin: '0.5rem 0' }}>{explanation.summary}</p>
                  {explanation.dependencies_summary && (
                    <p className="muted" style={{ margin: '0.5rem 0', fontSize: '0.85rem' }}>
                      <strong>Dependencies:</strong> {explanation.dependencies_summary}
                    </p>
                  )}
                  {explanation.recommendations?.length > 0 && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <strong style={{ fontSize: '0.85rem' }}>Architectural notes:</strong>
                      <ul style={{ margin: '0.25rem 0 0 1rem', padding: 0, fontSize: '0.85rem' }}>
                        {explanation.recommendations.map((rec, i) => (
                          <li key={i}>{rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </details>

          {/* 3. Containment */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="entity-containment-heading">Containment</h3>
            </summary>
            <dl className="details-dl">
              <dt>Parent entity</dt>
              <dd>
                {details.parent ? (
                  <span className="parent-entity">
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => onSelect?.({ type: 'node', id: details.parent.id })}
                      aria-label={`Select parent: ${details.parent.displayName || details.parent.qualifiedName}`}
                      title={`Select parent: ${details.parent.qualifiedName || details.parent.displayName}`}
                    >
                      {details.parent.displayName || details.parent.qualifiedName}
                      <span className="endpoint-kind"> ({NODE_KIND_LABELS[details.parent.kind] || humanize(details.parent.kind)})</span>
                    </button>
                    {onCenter && (
                      <button
                        type="button"
                        className="action-icon-button"
                        onClick={() => onCenter(details.parent.id)}
                        title="Center parent in graph"
                        aria-label={`Center ${details.parent.displayName} in graph`}
                      >
                        ⊙
                      </button>
                    )}
                  </span>
                ) : (
                  <span className="muted">None or root module</span>
                )}
              </dd>

              {item.moduleId && (
                <>
                  <dt>Module</dt>
                  <dd><code>{item.moduleId}</code></dd>
                </>
              )}

              {item.fileId && (
                <>
                  <dt>File ID</dt>
                  <dd><code>{item.fileId}</code></dd>
                </>
              )}
            </dl>
          </details>

          {/* 4. Incoming relationships */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="incoming-rel-heading">
                Incoming relationships <span className="section-count">({details.incoming.length})</span>
              </h3>
            </summary>
            {details.incoming.length === 0 ? (
              <p className="details-empty">No incoming relationships detected for this entity.</p>
            ) : (
              <ul className="relationship-list" aria-label="Incoming relationships list">
                {details.incoming.map((edge) => renderRelationshipCard(edge, 'incoming'))}
              </ul>
            )}
          </details>

          {/* 5. Outgoing relationships */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="outgoing-rel-heading">
                Outgoing relationships <span className="section-count">({details.outgoing.length})</span>
              </h3>
            </summary>
            {details.outgoing.length === 0 ? (
              <p className="details-empty">No outgoing relationships detected for this entity.</p>
            ) : (
              <ul className="relationship-list" aria-label="Outgoing relationships list">
                {details.outgoing.map((edge) => renderRelationshipCard(edge, 'outgoing'))}
              </ul>
            )}
          </details>

          {/* 6. Evidence and resolution */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="entity-evidence-heading">Evidence and resolution</h3>
            </summary>
            <dl className="details-dl">
              <dt>Classification</dt>
              <dd>
                <span className="details-badge badge--info">
                  {CLASSIFICATION_LABELS[item.classification] || humanize(item.classification) || 'Internal source unit'}
                </span>
              </dd>

              <dt>Resolution status</dt>
              <dd>
                {(() => {
                  const statusKey = item.resolutionStatus || (item.classification === 'unresolved' ? 'unresolved' : 'resolved')
                  const res = RESOLUTION_BADGES[statusKey] || { symbol: '✓', label: 'Resolved (source declaration)', variant: 'success' }
                  return (
                    <span className={`details-badge badge--${res.variant}`}>
                      <span aria-hidden="true" className="badge-symbol">{res.symbol}</span> {res.label}
                    </span>
                  )
                })()}
              </dd>

              <dt>Confidence</dt>
              <dd>{CONFIDENCE_LABELS[item.confidence] || 'Exact static declaration'}</dd>

              <dt>Evidence origin</dt>
              <dd>{EVIDENCE_ORIGIN_LABELS[item.attributes?.evidence_origin] || 'Static AST evidence'}</dd>

              <dt>Modifiers</dt>
              <dd>{item.modifiers?.length ? item.modifiers.join(', ') : 'None'}</dd>
            </dl>
          </details>

          {/* 7. Diagnostics */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="details-diagnostics-heading">
                Diagnostics <span className="section-count">({details.diagnostics.length})</span>
              </h3>
            </summary>
            {details.diagnostics.length === 0 ? (
              <p className="details-empty">No diagnostics reported for this element.</p>
            ) : (
              <ul className="details-diagnostic-list" aria-label="Related diagnostics list">
                {details.diagnostics.map((diag) => (
                  <li key={diag.id || diag.code} className={`details-diagnostic-card severity--${diag.severity || 'info'}`}>
                    <div className="diag-card-header">
                      <span className={`details-badge badge--${diag.severity === 'error' ? 'error' : diag.severity === 'warning' ? 'warning' : 'info'}`}>
                        {diag.severity?.toUpperCase() || 'INFO'}
                      </span>
                      <code className="diag-code">{diag.code}</code>
                    </div>
                    <p className="diag-message">{diag.message}</p>
                    {diag.location && (
                      <p className="diag-location">
                        <span aria-hidden="true">📍</span> {formatSpan(diag.location)}
                      </p>
                    )}
                    {diag.suggestedAction && (
                      <p className="diag-action">
                        <strong>Suggested action:</strong> {diag.suggestedAction}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </details>
        </>
      ) : (
        /* Edge Selection View */
        <>
          {/* 1. Overview */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="rel-overview-heading">Overview</h3>
            </summary>
            <div className="relationship-hero">
              <div className="hero-endpoint">
                <span className="hero-label">Source</span>
                {details.source ? (
                  <button
                    type="button"
                    className="link-button hero-name"
                    onClick={() => onSelect?.({ type: 'node', id: details.source.id })}
                  >
                    {details.source.displayName || details.source.qualifiedName}
                  </button>
                ) : (
                  <span className="hero-unloaded">{item.sourceId}</span>
                )}
              </div>
              <span className="hero-arrow" aria-hidden="true">→</span>
              <div className="hero-endpoint">
                <span className="hero-label">Target</span>
                {details.target ? (
                  <button
                    type="button"
                    className="link-button hero-name"
                    onClick={() => onSelect?.({ type: 'node', id: details.target.id })}
                  >
                    {details.target.displayName || details.target.qualifiedName}
                  </button>
                ) : (
                  <span className="hero-unloaded">
                    {item.targetReference || 'unresolved target'}
                  </span>
                )}
              </div>
            </div>
            <dl className="details-dl" style={{ marginTop: '0.75rem' }}>
              <dt>Kind</dt>
              <dd>
                <span className="relationship-kind-badge">
                  {RELATIONSHIP_KIND_LABELS[item.kind] || humanize(item.kind)}
                </span>
              </dd>

              <dt>Direction</dt>
              <dd>Directed (Source → Target)</dd>

              {item.occurrenceCount > 1 && (
                <>
                  <dt>Occurrences</dt>
                  <dd>{item.occurrenceCount}</dd>
                </>
              )}
            </dl>
          </details>

          {/* 2. Source location */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="rel-location-heading">Source location</h3>
            </summary>
            <dl className="details-dl">
              <dt>Project path</dt>
              <dd className="details-val-row">
                <code className="code-wrap">{location?.path || 'Unavailable'}</code>
                {location?.path && (
                  <CopyButton text={location.path} label="Copy project path" />
                )}
              </dd>

              <dt>Start position</dt>
              <dd>
                {location?.startLine != null
                  ? `Line ${location.startLine}, Col ${location.startColumn || 1}`
                  : 'Unavailable'}
              </dd>

              <dt>End position</dt>
              <dd>
                {location?.endLine != null
                  ? `Line ${location.endLine}, Col ${location.endColumn || 1}`
                  : 'Unavailable'}
              </dd>

              <dt>Source span</dt>
              <dd className="details-val-row">
                <code>{formatSpan(location)}</code>
                {location?.path && (
                  <CopyButton text={formatSpan(location)} label="Copy source span" />
                )}
              </dd>
            </dl>
          </details>

          {/* 3. Containment */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="rel-containment-heading">Containment</h3>
            </summary>
            <dl className="details-dl">
              <dt>Source entity</dt>
              <dd>
                {details.source ? (
                  <span className="parent-entity">
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => onSelect?.({ type: 'node', id: details.source.id })}
                      aria-label={`Select source: ${details.source.displayName || details.source.qualifiedName}`}
                      title={`Select source: ${details.source.displayName || details.source.qualifiedName}`}
                    >
                      {details.source.displayName || details.source.qualifiedName}
                    </button>
                    {onCenter && (
                      <button
                        type="button"
                        className="action-icon-button"
                        onClick={() => onCenter(details.source.id)}
                        title="Center source in graph"
                        aria-label={`Center ${details.source.displayName} in graph`}
                      >
                        ⊙
                      </button>
                    )}
                  </span>
                ) : (
                  <span className="muted">Unloaded or missing</span>
                )}
              </dd>
              <dt>Target entity</dt>
              <dd>
                {details.target ? (
                  <span className="parent-entity">
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => onSelect?.({ type: 'node', id: details.target.id })}
                      aria-label={`Select target: ${details.target.displayName || details.target.qualifiedName}`}
                      title={`Select target: ${details.target.displayName || details.target.qualifiedName}`}
                    >
                      {details.target.displayName || details.target.qualifiedName}
                    </button>
                    {onCenter && (
                      <button
                        type="button"
                        className="action-icon-button"
                        onClick={() => onCenter(details.target.id)}
                        title="Center target in graph"
                      >
                        ⊙
                      </button>
                    )}
                  </span>
                ) : (
                  <span className="unloaded-endpoint">
                    <span className="unloaded-text">{item.targetReference || item.targetId || 'Unresolved target'}</span>
                    <span className="badge-unloaded">
                      {item.targetClassification === 'external'
                        ? ' [External target]'
                        : item.targetClassification === 'missing'
                          ? ' [Missing target]'
                          : ' [Unloaded endpoint]'}
                    </span>
                    {onLoadMore && (
                      <button
                        type="button"
                        className="action-link action-load-more"
                        onClick={onLoadMore}
                        disabled={pageLoading}
                      >
                        {pageLoading ? 'Loading…' : 'Load more graph data'}
                      </button>
                    )}
                  </span>
                )}
              </dd>
            </dl>
          </details>

          {/* 6. Evidence and resolution */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="rel-evidence-heading">Evidence and resolution</h3>
            </summary>
            <dl className="details-dl">
              <dt>Resolution</dt>
              <dd>
                {(() => {
                  const res = RESOLUTION_BADGES[item.resolutionStatus] || { symbol: '·', label: humanize(item.resolutionStatus) || 'Not applicable', variant: 'muted' }
                  return (
                    <span className={`details-badge badge--${res.variant}`}>
                      <span aria-hidden="true" className="badge-symbol">{res.symbol}</span> {res.label}
                    </span>
                  )
                })()}
              </dd>

              <dt>Confidence</dt>
              <dd>{CONFIDENCE_LABELS[item.confidence] || humanize(item.confidence) || 'Unavailable'}</dd>

              <dt>Reason</dt>
              <dd>{REASON_LABELS[item.confidenceReason] || humanize(item.confidenceReason) || 'Unavailable'}</dd>

              <dt>Evidence origin</dt>
              <dd>
                {details.evidence.length
                  ? details.evidence.map((v) => EVIDENCE_ORIGIN_LABELS[v.origin] || humanize(v.origin) || 'Unavailable').join(', ')
                  : 'Unavailable in legacy data'}
              </dd>
            </dl>

            {details.evidence.length > 0 && (
              <div className="evidence-list-container">
                <h4 className="sub-heading">Detailed observations</h4>
                <ul className="evidence-obs-list">
                  {details.evidence.map((ev, idx) => (
                    <li key={ev.id || idx} className="evidence-obs-card">
                      <div className="obs-header">
                        <span className="details-badge badge--info">
                          {EVIDENCE_ORIGIN_LABELS[ev.origin] || humanize(ev.origin)}
                        </span>
                        {ev.observationKind && (
                          <span className="obs-kind">{humanize(ev.observationKind)}</span>
                        )}
                      </div>
                      {ev.explanation && <p className="obs-explanation">{ev.explanation}</p>}
                      {ev.expression && (
                        <div className="obs-expression">
                          <code>{ev.expression}</code>
                        </div>
                      )}
                      {ev.location && (
                        <p className="obs-location">📍 {formatSpan(ev.location)}</p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </details>

          {/* 7. Diagnostics */}
          <details className="details-section" open>
            <summary className="details-section-summary">
              <h3 id="rel-diagnostics-heading">
                Related diagnostics <span className="section-count">({details.diagnostics.length})</span>
              </h3>
            </summary>
            {details.diagnostics.length === 0 ? (
              <p className="details-empty">No diagnostics reported for this element.</p>
            ) : (
              <ul className="details-diagnostic-list" aria-label="Related diagnostics list">
                {details.diagnostics.map((diag) => (
                  <li key={diag.id || diag.code} className={`details-diagnostic-card severity--${diag.severity || 'info'}`}>
                    <div className="diag-card-header">
                      <span className={`details-badge badge--${diag.severity === 'error' ? 'error' : diag.severity === 'warning' ? 'warning' : 'info'}`}>
                        {diag.severity?.toUpperCase() || 'INFO'}
                      </span>
                      <code className="diag-code">{diag.code}</code>
                    </div>
                    <p className="diag-message">{diag.message}</p>
                    {diag.location && (
                      <p className="diag-location">
                        <span aria-hidden="true">📍</span> {formatSpan(diag.location)}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </details>
        </>
      )}

      <section className="details-actions">
        {onNavigateSource && location ? (
          <button
            type="button"
            className="action-button-primary"
            onClick={() => onNavigateSource(location)}
          >
            Open source location
          </button>
        ) : (
          <p className="muted">Source navigation is unavailable in this prototype.</p>
        )}
      </section>
    </aside>
  )
}
