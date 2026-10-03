export default function DiagnosticsPanel({ diagnostics, severity, onSeverity, onSelect }) {
  const visible = severity === 'all' ? diagnostics : diagnostics.filter((item) => item.severity === severity)
  return <section className="diagnostics-panel" aria-labelledby="diagnostics-title">
    <div className="panel-heading"><h2 id="diagnostics-title">Analysis diagnostics ({diagnostics.length})</h2>
      <label>Severity <select value={severity} onChange={(event) => onSeverity(event.target.value)}><option value="all">All</option><option value="error">Error</option><option value="warning">Warning</option><option value="info">Info</option></select></label>
    </div>
    {!visible.length ? <p>No analysis diagnostics match this filter. Application failures appear in the status region.</p> : <ul className="diagnostic-list">{visible.map((item) => <li key={item.id} className={`diagnostic diagnostic--${item.severity}`}><strong>{item.severity} · {item.code}</strong><span>{item.message}</span><span>{item.location ? `${item.location.path}${item.location.startLine ? `:${item.location.startLine}:${item.location.startColumn || 1}` : ''}` : 'No source location'}</span>{(item.entityId || item.edgeId) && <button type="button" onClick={() => onSelect({ type: item.entityId ? 'node' : 'edge', id: item.entityId || item.edgeId })}>Inspect related element</button>}</li>)}</ul>}
  </section>
}
