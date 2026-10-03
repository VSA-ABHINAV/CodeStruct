export default function SearchBox({ query, onQueryChange, resultCount, activeIndex, onStep, onActivate }) {
  function keyDown(event) {
    if (event.key === 'ArrowDown') { event.preventDefault(); onStep(1) }
    if (event.key === 'ArrowUp') { event.preventDefault(); onStep(-1) }
    if (event.key === 'Enter' && resultCount) { event.preventDefault(); onActivate() }
    if (event.key === 'Escape') onQueryChange('')
  }
  return <div className="search-box" role="search">
    <label htmlFor="architecture-search">Search architecture</label>
    <div className="control-row">
      <input id="architecture-search" value={query} onChange={(event) => onQueryChange(event.target.value)} onKeyDown={keyDown} placeholder="Name, qualified name, path, or kind" />
      <button type="button" onClick={() => onQueryChange('')} disabled={!query}>Clear</button>
      <button type="button" onClick={() => onStep(-1)} disabled={!resultCount} aria-label="Previous search result">Previous</button>
      <button type="button" onClick={() => onStep(1)} disabled={!resultCount} aria-label="Next search result">Next</button>
    </div>
    <p className="compact-status" aria-live="polite">{resultCount ? `${activeIndex + 1} of ${resultCount} matches` : query ? 'No matches' : 'Enter a search term'}</p>
  </div>
}
