import { normalizeGraphContract } from './graphContract.js'
import { adaptLegacyGraph } from './legacyGraphAdapter.js'

export function normalizeGraph(payload) {
  if (payload && Array.isArray(payload.files) && Array.isArray(payload.dependencies)) {
    return adaptLegacyGraph(payload)
  }
  return normalizeGraphContract(payload)
}

export function emptyNormalizedGraph() {
  return { source: 'none', schemaVersion: null, metadata: {}, summary: {}, page: null, nodes: [], edges: [], evidence: [], diagnostics: [] }
}
