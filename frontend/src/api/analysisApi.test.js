import assert from 'node:assert/strict'
import { test } from 'vitest'
import { createAnalysisApi, mergeGraphSlices, retrieveGraph, validateJob } from './analysisApi.js'
import { AnalysisPoller } from './analysisPoller.js'
import { apiUrl, normalizeApiBase } from './client.js'

const job = (state = 'queued') => ({ api_version: 'v1', analysis_id: 'ana_test', state, terminal: ['completed', 'partially_completed', 'failed', 'cancelled'].includes(state), progress: { percent: 5 } })
const response = (payload, status = 200) => ({ ok: status < 400, status, headers: { get: () => null }, json: async () => payload })

test('normalizes configured and same-origin API URLs', () => {
  assert.equal(normalizeApiBase('http://127.0.0.1:8000/'), 'http://127.0.0.1:8000')
  assert.equal(apiUrl('/api/v1/analyses', ''), '/api/v1/analyses')
  assert.throws(() => normalizeApiBase('file:///private'))
})

test('submits the v1 contract exactly once and validates status', async () => {
  const calls = []
  const api = createAnalysisApi({ base: 'http://localhost:8000', transport: async (...args) => { calls.push(args); return response(job()) } })
  await api.submit({ root_id: 'sample', relative_path: '.' })
  assert.equal(calls.length, 1)
  assert.deepEqual(JSON.parse(calls[0][1].body).project, { root_id: 'sample', relative_path: '.' })
  assert.throws(() => validateJob({ state: 'invented' }), (error) => error.code === 'MALFORMED_RESPONSE')
})

test('discovers only validated configured-project capabilities', async () => {
  const api = createAnalysisApi({ transport: async () => response({ api_version: 'v1', projects: [{ id: 'team', display_name: 'Team project', available: true }, { id: 1, display_name: 'unsafe', available: true }] }) })
  assert.deepEqual(await api.projects(), [{ id: 'team', display_name: 'Team project', available: true }])
})

test('poller avoids overlap and retrieves a partial graph plus diagnostics', async () => {
  const scheduled = []; const updates = []; let statusCalls = 0
  const api = { status: async () => { statusCalls += 1; return job('partially_completed') }, graph: async () => ({ schema_version: '1.0.0', metadata: { partial: true }, nodes: [], edges: [], evidence: [], diagnostics: [] }), diagnostics: async () => ({ items: [{ code: 'FILE_SYNTAX_ERROR' }] }) }
  const poller = new AnalysisPoller(api, { schedule: (fn) => { scheduled.push(fn); return scheduled.length }, cancelSchedule: () => {} })
  poller.start(job(), (value) => updates.push(value))
  await Promise.all([scheduled[0](), scheduled[0]()])
  assert.equal(statusCalls, 1)
  assert.equal(updates.at(-1).graph.diagnostics[0].code, 'FILE_SYNTAX_ERROR')
  assert.equal(scheduled.length, 1)
})

test('stopping invalidates stale polling responses and public errors redact paths', async () => {
  const scheduled = []; const updates = []
  const poller = new AnalysisPoller({ status: async () => job() }, { schedule: (fn) => { scheduled.push(fn); return scheduled.length }, cancelSchedule: () => {} })
  poller.start(job(), (value) => updates.push(value)); poller.stop(); await scheduled[0](); assert.equal(updates.length, 1)
  const api = createAnalysisApi({ transport: async () => response({ error: { code: 'PROJECT_UNAUTHORIZED', message: 'D:/private' } }, 403) })
  await assert.rejects(api.submit({ root_id: 'sample', relative_path: '..' }), (error) => error.code === 'PROJECT_UNAUTHORIZED' && !error.message.includes('private'))
})

test('forced refresh and deterministic graph slice merging preserve loaded counts', async () => {
  const calls = []
  const api = createAnalysisApi({ transport: async (...args) => { calls.push(args); return response(job()) } })
  await api.submit({ root_id: 'sample', relative_path: '.' }, { refresh: true })
  assert.equal(JSON.parse(calls[0][1].body).refresh, true)
  const base = { schema_version: '1.0.0', metadata: {}, summary: {}, diagnostics: [] }
  const merged = mergeGraphSlices([
    { ...base, nodes: [{ id: 'b' }], edges: [], evidence: [], page: { next_cursor: 'next', total_nodes: 2 } },
    { ...base, nodes: [{ id: 'a' }, { id: 'b' }], edges: [], evidence: [], page: { next_cursor: null, total_nodes: 2 } },
  ])
  assert.deepEqual(merged.nodes.map((item) => item.id), ['a', 'b'])
  assert.equal(merged.page.returned_nodes, 2)
  assert.equal(merged.page.partial_load, false)
})

test('graph retrieval starts bounded and never requests the eager full graph', async () => {
  const requested = []
  const api = { graph: async (_id, query) => { requested.push(query); return { schema_version: '1.0.0', metadata: { graph_id: 'g' }, summary: {}, nodes: [{ id: 'a' }], edges: [], evidence: [], diagnostics: [], page: { next_cursor: 'second', total_nodes: 2 } } } }
  const graph = await retrieveGraph(api, 'ana', 1)
  assert.deepEqual(requested, [{ limit: 1 }])
  assert.deepEqual(graph.nodes.map((item) => item.id), ['a'])
  assert.equal(graph.page.next_cursor, 'second')
})

test('graph slices reject cross-result pages and deduplicate repeated elements', () => {
  const base = { schema_version: '1.0.0', metadata: { graph_id: 'g' }, summary: {}, evidence: [], diagnostics: [] }
  const merged = mergeGraphSlices([
    { ...base, nodes: [{ id: 'a' }], edges: [{ id: 'e' }], page: { next_cursor: 'next', total_nodes: 2, total_edges: 1 } },
    { ...base, nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ id: 'e' }], page: { next_cursor: null, total_nodes: 2, total_edges: 1 } },
  ])
  assert.deepEqual(merged.nodes.map(({ id }) => id), ['a', 'b'])
  assert.equal(merged.edges.length, 1)
  assert.throws(() => mergeGraphSlices([{ ...base, nodes: [], edges: [], page: {} }, { ...base, metadata: { graph_id: 'other' }, nodes: [], edges: [], page: {} }]), (error) => error.code === 'MALFORMED_RESPONSE')
})

test('explain, exportDot, and navigateEditor call authoritative endpoints', async () => {
  const calls = []
  const api = createAnalysisApi({
    base: 'http://localhost:8000',
    transport: async (url, opts) => {
      calls.push({ url, opts })
      if (url.endsWith('/explain')) {
        return response({ role: 'Controller', summary: 'Orchestrates calls' })
      }
      if (url.endsWith('/export/dot')) {
        return { ok: true, status: 200, text: async () => 'digraph G { a -> b; }' }
      }
      if (url.endsWith('/editor/navigate')) {
        return response({ status: 'ok', line: 10 })
      }
      return response({})
    },
  })

  const exp = await api.explain('ana_1', 'node_a')
  assert.equal(exp.role, 'Controller')
  assert.equal(calls[0].url, 'http://localhost:8000/api/v1/analyses/ana_1/nodes/node_a/explain')

  const dot = await api.exportDot('ana_1')
  assert.equal(dot, 'digraph G { a -> b; }')
  assert.equal(calls[1].url, 'http://localhost:8000/api/v1/analyses/ana_1/export/dot')

  const nav = await api.navigateEditor({ session_token: 'cap_test', relative_path: 'app.py', line: 10, column: 1 })
  assert.equal(nav.status, 'ok')
  assert.equal(calls[2].url, 'http://localhost:8000/api/v1/editor/navigate')
  assert.deepEqual(JSON.parse(calls[2].opts.body), { session_token: 'cap_test', relative_path: 'app.py', line: 10, column: 1 })
})
