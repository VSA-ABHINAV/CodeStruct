const GROUPS = [
  ['nodeKinds', 'Entity kinds', ['project', 'package', 'module', 'file', 'class', 'function', 'async_function', 'method', 'async_method', 'external_module', 'unresolved_symbol']],
  ['relationshipKinds', 'Relationships', ['contains', 'defines', 'imports', 'inherits', 'calls', 'constructs', 'references']],
  ['resolutionStatuses', 'Resolution', ['resolved', 'ambiguous', 'unresolved', 'syntactic_only', 'not_applicable']],
  ['targetClasses', 'Target classification', ['internal', 'external', 'unresolved', 'missing']],
  ['diagnosticSeverities', 'Diagnostic severity', ['error', 'warning', 'info']],
]

export default function FilterPanel({ filters, onChange, onReset }) {
  function toggle(group, value) {
    const current = filters[group] || []
    onChange({ ...filters, [group]: current.includes(value) ? current.filter((item) => item !== value) : [...current, value].sort() })
  }
  return <details className="filter-panel">
    <summary>Filters</summary>
    <div className="filter-groups">
      {GROUPS.map(([key, label, values]) => <fieldset key={key}>
        <legend>{label}</legend>
        {values.map((value) => <label key={value}><input type="checkbox" checked={(filters[key] || []).includes(value)} onChange={() => toggle(key, value)} /> {value.replaceAll('_', ' ')}</label>)}
      </fieldset>)}
    </div>
    <button type="button" onClick={onReset}>Reset all filters</button>
  </details>
}
