export default function ExplorerToolbar({ view, onView, controller, selected, onCenterSelected, onClearSelection }) {
  return <nav className="explorer-toolbar" aria-label="Architecture view controls">
    <div role="group" aria-label="View mode">
      <button type="button" aria-pressed={view === 'graph'} onClick={() => onView('graph')}>Graph</button>
      <button type="button" aria-pressed={view === 'table'} onClick={() => onView('table')}>Table</button>
    </div>
    <div role="group" aria-label="Graph navigation">
      <button type="button" onClick={() => controller?.zoomOut()}>Zoom out</button>
      <button type="button" onClick={() => controller?.zoomIn()}>Zoom in</button>
      <button type="button" onClick={() => controller?.fitView()}>Fit view</button>
      <button type="button" onClick={() => controller?.reset()}>Reset view</button>
      <button type="button" onClick={onCenterSelected} disabled={!selected}>Center selected</button>
      <button type="button" onClick={onClearSelection} disabled={!selected}>Clear selection</button>
    </div>
  </nav>
}
