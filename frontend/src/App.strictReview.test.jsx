import { StrictMode } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App.jsx'

// Exercise the real hook and poller; replace only the graph renderer.
vi.mock('./Graph.jsx', () => ({
  default: ({ graph }) => <div data-testid="review-graph">{graph ? 'loaded' : 'waiting'}</div>,
}))

afterEach(() => {
  cleanup()
  window.history.replaceState({}, '', '/')
})

test.each([false, true])('IDE URL loads a real analysis hook with StrictMode=%s', async (strict) => {
  window.history.replaceState({}, '', '/?analysis_id=ana-review&session_token=cap-review')
  const api = {
    projects: vi.fn().mockResolvedValue([]),
    status: vi.fn().mockResolvedValue({ analysis_id: 'ana-review', state: 'completed', terminal: true }),
    graph: vi.fn().mockResolvedValue({ schema_version: '1.0.0', nodes: [], edges: [], evidence: [], diagnostics: [], page: { next_cursor: null } }),
    diagnostics: vi.fn().mockResolvedValue({ items: [] }),
  }
  render(strict ? <StrictMode><App api={api} /></StrictMode> : <App api={api} />)
  await waitFor(() => expect(screen.getByTestId('review-graph')).toHaveTextContent('loaded'), { timeout: 1000 })
  expect(window.location.search).toBe('')
})

test.each([false, true])('loads plain analysis_id without session token under StrictMode=%s', async (strict) => {
  window.history.replaceState({}, '', '/?analysis_id=ana-plain')
  const api = {
    projects: vi.fn().mockResolvedValue([]),
    status: vi.fn().mockResolvedValue({ analysis_id: 'ana-plain', state: 'completed', terminal: true }),
    graph: vi.fn().mockResolvedValue({ schema_version: '1.0.0', nodes: [], edges: [], evidence: [], diagnostics: [], page: { next_cursor: null } }),
    diagnostics: vi.fn().mockResolvedValue({ items: [] }),
  }
  render(strict ? <StrictMode><App api={api} /></StrictMode> : <App api={api} />)
  await waitFor(() => expect(screen.getByTestId('review-graph')).toHaveTextContent('loaded'), { timeout: 1000 })
  expect(window.location.search).toBe('')
})
