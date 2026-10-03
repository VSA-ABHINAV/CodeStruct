import { act, renderHook } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { useAnalysisJob } from './useAnalysisJob.js'
import { AnalysisApiError } from '../../api/analysisErrors.js'

const job = {
  api_version: 'v1', analysis_id: 'ana-new', state: 'completed', terminal: true,
  cache_hit: false, progress: { percent: 100, message_code: 'ANALYSIS_COMPLETED' },
}
const page = (nodes, cursor) => ({
  schema_version: '1.0.0', metadata: { graph_id: 'graph-new' }, summary: {},
  nodes, edges: [], evidence: [], diagnostics: [],
  page: { returned_nodes: nodes.length, total_nodes: 2, returned_edges: 0, total_edges: 0, next_cursor: cursor, partial_load: Boolean(cursor) },
})

test('loads a bounded first page then merges one requested page without duplicates', async () => {
  const api = {
    submit: vi.fn().mockResolvedValue({ job }),
    status: vi.fn().mockResolvedValue(job),
    diagnostics: vi.fn().mockResolvedValue({ items: [] }),
    graph: vi.fn()
      .mockResolvedValueOnce(page([{ id: 'a' }], 'next'))
      .mockResolvedValueOnce(page([{ id: 'a' }, { id: 'b' }], null)),
    cancel: vi.fn(),
  }
  const { result } = renderHook(() => useAnalysisJob(api))
  await act(async () => result.current.submit({ root_id: 'team', relative_path: '.' }))
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })
  expect(result.current.graph.nodes.map(({ id }) => id)).toEqual(['a'])
  expect(result.current.hasMore).toBe(true)
  expect(result.current.provenance).toEqual({ root_id: 'team', relative_path: '.' })
  await act(async () => result.current.loadMore())
  expect(result.current.graph.nodes.map(({ id }) => id)).toEqual(['a', 'b'])
  expect(result.current.hasMore).toBe(false)
  expect(api.graph.mock.calls).toEqual([
    ['ana-new', { limit: 1000 }],
    ['ana-new', { limit: 1000, cursor: 'next' }],
  ])
})

test('loads an existing completed analysis by ID without submitting a job (no POST)', async () => {
  const existingJob = {
    api_version: 'v1', analysis_id: 'ana-existing', state: 'completed', terminal: true,
    cache_hit: false, progress: { percent: 100, message_code: 'ANALYSIS_COMPLETED' },
  }
  const api = {
    submit: vi.fn(),
    status: vi.fn().mockResolvedValue(existingJob),
    diagnostics: vi.fn().mockResolvedValue({ items: [{ id: 'd1', severity: 'info', message: 'test diagnostic' }] }),
    graph: vi.fn().mockResolvedValue(page([{ id: 'node-1' }], null)),
    cancel: vi.fn(),
  }
  const { result } = renderHook(() => useAnalysisJob(api))
  await act(async () => result.current.load('ana-existing'))
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })

  expect(api.submit).not.toHaveBeenCalled()
  expect(api.status).toHaveBeenCalledWith('ana-existing')
  expect(api.graph).toHaveBeenCalledWith('ana-existing', { limit: 1000 })
  expect(api.diagnostics).toHaveBeenCalledWith('ana-existing')
  expect(result.current.job.analysis_id).toBe('ana-existing')
  expect(result.current.graph.nodes.map((n) => n.id)).toEqual(['node-1'])
  expect(result.current.graph.diagnostics).toEqual([{ id: 'd1', severity: 'info', message: 'test diagnostic' }])
  expect(result.current.provenance).toBeNull()
})

test('polls an in-progress analysis loaded by ID until completion', async () => {
  const pendingJob = {
    api_version: 'v1', analysis_id: 'ana-progress', state: 'parsing', terminal: false,
    progress: { percent: 40, message_code: 'PARSING_FILES' },
  }
  const completedJob = {
    api_version: 'v1', analysis_id: 'ana-progress', state: 'completed', terminal: true,
    progress: { percent: 100, message_code: 'ANALYSIS_COMPLETED' },
  }
  const api = {
    submit: vi.fn(),
    status: vi.fn()
      .mockResolvedValueOnce(pendingJob)
      .mockResolvedValueOnce(completedJob),
    diagnostics: vi.fn().mockResolvedValue({ items: [] }),
    graph: vi.fn().mockResolvedValue(page([{ id: 'node-p' }], null)),
    cancel: vi.fn(),
  }
  const { result } = renderHook(() => useAnalysisJob(api))
  await act(async () => result.current.load('ana-progress'))
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })
  expect(result.current.job.state).toBe('parsing')
  expect(result.current.graph).toBeNull()

  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 800)) })
  expect(result.current.job.state).toBe('completed')
  expect(result.current.graph.nodes.map((n) => n.id)).toEqual(['node-p'])
})

test('loads a partially completed analysis by ID and displays diagnostics', async () => {
  const partialJob = {
    api_version: 'v1', analysis_id: 'ana-partial', state: 'partially_completed', terminal: true,
    partial: true, progress: { percent: 100, message_code: 'PARTIAL_RESULTS' },
  }
  const api = {
    submit: vi.fn(),
    status: vi.fn().mockResolvedValue(partialJob),
    diagnostics: vi.fn().mockResolvedValue({ items: [{ id: 'd-err', severity: 'warning', message: 'Syntax error in module' }] }),
    graph: vi.fn().mockResolvedValue(page([{ id: 'node-ok' }], null)),
    cancel: vi.fn(),
  }
  const { result } = renderHook(() => useAnalysisJob(api))
  await act(async () => result.current.load('ana-partial'))
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })

  expect(result.current.job.state).toBe('partially_completed')
  expect(result.current.graph.nodes.map((n) => n.id)).toEqual(['node-ok'])
  expect(result.current.graph.diagnostics).toHaveLength(1)
  expect(result.current.provenance).toBeNull()
})

test('handles failed and cancelled analyses cleanly without fetching graph', async () => {
  const failedJob = {
    api_version: 'v1', analysis_id: 'ana-failed', state: 'failed', terminal: true,
    progress: { percent: 10, message_code: 'ANALYSIS_FAILED' },
  }
  const api = {
    submit: vi.fn(),
    status: vi.fn().mockResolvedValue(failedJob),
    diagnostics: vi.fn(),
    graph: vi.fn(),
    cancel: vi.fn(),
  }
  const { result } = renderHook(() => useAnalysisJob(api))
  await act(async () => result.current.load('ana-failed'))
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })

  expect(result.current.job.state).toBe('failed')
  expect(result.current.graph).toBeNull()
  expect(api.graph).not.toHaveBeenCalled()
  expect(api.diagnostics).not.toHaveBeenCalled()
})

test('rejects empty or malformed analysis IDs immediately', async () => {
  const api = { submit: vi.fn(), status: vi.fn(), diagnostics: vi.fn(), graph: vi.fn(), cancel: vi.fn() }
  const { result } = renderHook(() => useAnalysisJob(api))

  await act(async () => result.current.load('   '))
  expect(result.current.error.code).toBe('MALFORMED_ID')
  expect(api.status).not.toHaveBeenCalled()

  await act(async () => result.current.load('invalid\x00char'))
  expect(result.current.error.code).toBe('MALFORMED_ID')
  expect(api.status).not.toHaveBeenCalled()
})

test('stops polling immediately on 404 (JOB_NOT_FOUND) or 410 (RESULT_EXPIRED) without retrying', async () => {
  const notFoundError = new AnalysisApiError('JOB_NOT_FOUND', 'The analysis no longer exists or its result expired.', 404, false)
  const api = {
    submit: vi.fn(),
    status: vi.fn().mockRejectedValue(notFoundError),
    diagnostics: vi.fn(),
    graph: vi.fn(),
    cancel: vi.fn(),
  }
  const { result } = renderHook(() => useAnalysisJob(api))
  await act(async () => result.current.load('ana-missing'))
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })

  expect(api.status).toHaveBeenCalledTimes(1)
  expect(result.current.error.code).toBe('JOB_NOT_FOUND')
  expect(result.current.graph).toBeNull()

  // Wait to verify no retry tick happens
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 800)) })
  expect(api.status).toHaveBeenCalledTimes(1)
})

test('newer load action cancels older in-flight response (race protection)', async () => {
  let resolveFirst
  const firstPromise = new Promise((resolve) => { resolveFirst = resolve })
  const firstJob = {
    api_version: 'v1', analysis_id: 'ana-first', state: 'completed', terminal: true,
    progress: { percent: 100, message_code: 'ANALYSIS_COMPLETED' },
  }
  const secondJob = {
    api_version: 'v1', analysis_id: 'ana-second', state: 'completed', terminal: true,
    progress: { percent: 100, message_code: 'ANALYSIS_COMPLETED' },
  }

  const api = {
    submit: vi.fn(),
    status: vi.fn().mockImplementation((id) => {
      if (id === 'ana-first') return firstPromise
      return Promise.resolve(secondJob)
    }),
    diagnostics: vi.fn().mockResolvedValue({ items: [] }),
    graph: vi.fn().mockImplementation((id) => Promise.resolve(page([{ id: `node-${id}` }], null))),
    cancel: vi.fn(),
  }
  const { result } = renderHook(() => useAnalysisJob(api))

  // Start first load and allow its tick to initiate api.status('ana-first')
  act(() => { result.current.load('ana-first') })
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)) })
  expect(api.status).toHaveBeenCalledWith('ana-first')

  // Switch to second load immediately
  await act(async () => { result.current.load('ana-second') })
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })
  expect(api.status).toHaveBeenCalledWith('ana-second')

  // Now resolve late first response
  resolveFirst(firstJob)
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })

  expect(result.current.job.analysis_id).toBe('ana-second')
  expect(result.current.graph.nodes.map((n) => n.id)).toEqual(['node-ana-second'])
})


