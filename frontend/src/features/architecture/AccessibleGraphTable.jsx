export default function AccessibleGraphTable({ graph, selected, onSelect }) {
  const names = new Map(graph.nodes.map((node) => [node.id, node.qualifiedName || node.displayName]))
  return <section className="graph-table" aria-labelledby="structure-table-title">
    <h2 id="structure-table-title">Structure table</h2>
    <div className="table-scroll"><table><caption>{graph.page?.partial_load ? `Loaded graph slice: ${graph.page.returned_nodes} of ${graph.page.total_nodes} entities and ${graph.page.returned_edges} of ${graph.page.total_edges} relationships.` : 'Complete loaded graph data.'}</caption><thead><tr><th>Entity or relationship</th><th>Type</th><th>State</th><th>Confidence</th><th>Source</th><th>Action</th></tr></thead>
      <tbody>
        {graph.nodes.map((node) => <tr key={node.id} className={selected?.id === node.id ? 'is-selected' : ''}><td>{node.qualifiedName || node.displayName}</td><td>{node.kind.replaceAll('_', ' ')}</td><td>Entity</td><td>Not applicable</td><td>{node.location?.path || 'Unavailable'}</td><td><button type="button" onClick={() => onSelect({ type: 'node', id: node.id })}>Inspect</button></td></tr>)}
        {graph.edges.map((edge) => <tr key={edge.id} className={selected?.id === edge.id ? 'is-selected' : ''}><td>{names.get(edge.sourceId) || edge.sourceId} → {names.get(edge.targetId) || edge.targetReference || 'unresolved target'}</td><td>{edge.kind}</td><td>{edge.resolutionStatus}</td><td>{edge.confidence || 'Unavailable'}</td><td>{edge.evidenceIds.length ? `${edge.evidenceIds.length} evidence record(s)` : 'Unavailable'}</td><td><button type="button" onClick={() => onSelect({ type: 'edge', id: edge.id })}>Inspect</button></td></tr>)}
      </tbody></table></div>
  </section>
}
