import { AnalysisApiError } from './analysisErrors.js'
import { requestJson } from './client.js'
const STATES = new Set(['submitted', 'validating', 'queued', 'scanning', 'parsing', 'resolving', 'building_graph', 'computing_metrics', 'completed', 'partially_completed', 'failed', 'cancellation_requested', 'cancelled', 'cache_hit'])
export function validateJob(payload) { if (!payload || payload.api_version !== 'v1' || typeof payload.analysis_id !== 'string' || !STATES.has(payload.state) || typeof payload.terminal !== 'boolean') throw new AnalysisApiError('MALFORMED_RESPONSE', 'The backend returned an invalid analysis status.'); return payload }
export function createAnalysisApi({ transport = fetch, base } = {}) { return {
  async projects() { const payload = (await requestJson('/api/v1/projects', {}, transport, base)).payload; if (!payload || payload.api_version !== 'v1' || !Array.isArray(payload.projects)) throw new AnalysisApiError('MALFORMED_RESPONSE', 'The backend returned an invalid project list.'); return payload.projects.filter((project) => project && typeof project.id === 'string' && typeof project.display_name === 'string' && typeof project.available === 'boolean') },
  async submit(project, { refresh = false } = {}) { const { payload, response } = await requestJson('/api/v1/analyses', { method: 'POST', body: JSON.stringify({ project, options: { metrics: false }, refresh }) }, transport, base); return { job: validateJob(payload), retryAfter: Number(response.headers?.get?.('Retry-After')) || null } },
  async status(id) { return validateJob((await requestJson(`/api/v1/analyses/${encodeURIComponent(id)}`, {}, transport, base)).payload) },
  async graph(id, query = {}) { const parameters = new URLSearchParams(Object.entries(query).filter(([, value]) => value !== null && value !== undefined)); const suffix = parameters.size ? `?${parameters}` : ''; return (await requestJson(`/api/v1/analyses/${encodeURIComponent(id)}/graph${suffix}`, {}, transport, base)).payload },
  async diagnostics(id) { return (await requestJson(`/api/v1/analyses/${encodeURIComponent(id)}/diagnostics`, {}, transport, base)).payload },
  async cancel(id) { return validateJob((await requestJson(`/api/v1/analyses/${encodeURIComponent(id)}`, { method: 'DELETE' }, transport, base)).payload) },
} }
export const analysisApi = createAnalysisApi()

export function mergeGraphSlices(slices) {
  if (!slices.length) return null
  const schema = slices[0].schema_version; const graphId = slices[0].metadata?.graph_id
  if (slices.some((slice) => slice.schema_version !== schema || slice.metadata?.graph_id !== graphId)) throw new AnalysisApiError('MALFORMED_RESPONSE', 'Graph pages do not belong to the same result.')
  const mergeBy = (field, id) => [...new Map(slices.flatMap((slice) => slice[field] || []).map((item) => [item[id], item])).values()].sort((a, b) => a[id].localeCompare(b[id]))
  const nodes = mergeBy('nodes', 'id'); const edges = mergeBy('edges', 'id'); const last = slices.at(-1)
  return { ...slices[0], nodes, edges, evidence: mergeBy('evidence', 'evidence_id'), diagnostics: mergeBy('diagnostics', 'id'), page: { ...last.page, returned_nodes: nodes.length, returned_edges: edges.length, partial_load: Boolean(last.page?.next_cursor) || nodes.length < (last.page?.total_nodes ?? nodes.length) } }
}

export async function retrieveGraph(api, id, pageSize = 1000) {
  return api.graph(id, { limit: pageSize })
}
