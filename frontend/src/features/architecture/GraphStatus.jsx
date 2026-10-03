const LABELS = {
  initial: ['Ready to explore', 'Analyze the sample project to create an architecture view.'],
  project_selected: ['Project selected', 'The project is ready for analysis.'],
  validation_failed: ['Validation failed', 'The selected project could not be safely validated.'],
  queued: ['Queued', 'Analysis is waiting to start.'],
  scanning: ['Scanning', 'Discovering eligible source files.'],
  parsing: ['Parsing', 'Extracting source metadata.'],
  resolving: ['Resolving', 'Resolving supported static relationships.'],
  building_graph: ['Building graph', 'Preparing the architecture result.'],
  completed: ['Completed', 'The available analysis result is ready.'],
  partially_completed: ['Partially completed', 'Usable results were retained; review diagnostics for omitted work.'],
  failed: ['Analysis failed', 'No usable result is available.'],
  cancellation_requested: ['Stopping safely', 'Cancellation will take effect at a safe checkpoint.'],
  cancelled: ['Cancelled', 'Incomplete work is not presented as a complete result.'],
  cache_hit: ['Cached result', 'A compatible cached result is ready.'],
  retrieving_graph: ['Retrieving graph', 'Analysis is complete; loading the first bounded graph page.'],
  unsupported_schema: ['Unsupported graph schema', 'This result requires a compatible explorer version.'],
  empty: ['Empty graph', 'No architecture entities matched the current result or presentation filters.'],
  large_graph: ['Large graph', 'Full canvas rendering is paused to protect responsiveness.'],
}

export default function GraphStatus({ state = 'initial', detail, assertive = false }) {
  const [heading, description] = LABELS[state] || [state.replaceAll('_', ' '), 'Analysis status updated.']
  return <section className={`graph-status graph-status--${state}`} aria-labelledby="graph-status-title" role={assertive ? 'alert' : 'status'} aria-live={assertive ? 'assertive' : 'polite'}>
    <h2 id="graph-status-title">{heading}</h2>
    <p>{detail || description}</p>
  </section>
}
