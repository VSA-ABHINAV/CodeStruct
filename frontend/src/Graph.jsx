import ArchitectureExplorer from './features/architecture/ArchitectureExplorer.jsx'

// Compatibility entry point retained until the Phase 9 v1 API migration.
export default function Graph({ files = [], dependencies = [], graph: versionedGraph = null, state = 'completed', error = null, onLoadMore = null, pageLoading = false, projectName = '', ...rest }) {
  const hasLegacyResult = files.length > 0 || dependencies.length > 0
  const graph = versionedGraph || (hasLegacyResult ? { files, dependencies } : null)
  return <ArchitectureExplorer graph={graph} state={state} error={error} onLoadMore={onLoadMore} pageLoading={pageLoading} projectName={projectName} {...rest} />
}
