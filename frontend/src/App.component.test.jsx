import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'

import App from './App.jsx'

const submit = vi.fn()
const cancel = vi.fn()
const load = vi.fn()
const setError = vi.fn()
let analysis
let api

vi.mock('./features/architecture/useAnalysisJob.js', () => ({
  useAnalysisJob: () => analysis,
}))

vi.mock('./Graph.jsx', () => ({
  default: ({ state, error, graph, onNavigateSource }) => (
    <section aria-label="Graph compatibility entry">
      {state}|{error || 'no error'}|{graph ? 'graph loaded' : 'no graph'}
      {onNavigateSource && (
        <button
          type="button"
          onClick={() => onNavigateSource({ path: 'app.py', line: 10, column: 2 })}
        >
          Trigger Navigation
        </button>
      )}
    </section>
  ),
}))

beforeEach(() => {
  submit.mockReset()
  cancel.mockReset()
  load.mockReset()
  setError.mockReset()
  analysis = {
    job: null,
    graph: null,
    error: null,
    submitting: false,
    cancelling: false,
    graphLoading: false,
    pageLoading: false,
    provenance: null,
    submit,
    cancel,
    load,
    setError,
  }
  api = {
    projects: vi.fn().mockResolvedValue([
      { id: 'team', display_name: 'Team project', available: true },
      { id: 'other_proj', display_name: 'Other project', available: true },
    ]),
    navigateEditor: vi.fn().mockResolvedValue({ status: 'ok' }),
  }
  window.history.replaceState({}, '', '/')
})

test('shows the authoritative application version', async () => {
  render(<App api={api} />)
  expect(screen.getByText('Version 0.1.0.dev0')).toBeInTheDocument()
  await screen.findByRole('option', { name: 'Team project' })
})

test('submits the selected authorized-root-relative project', async () => {
  const user = userEvent.setup()
  render(<App api={api} />)
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Configured project' }), 'team')
  await user.click(screen.getByRole('button', { name: 'Analyze project' }))
  expect(submit).toHaveBeenCalledWith({ root_id: 'team', relative_path: '.' })
})

test('announces empty and failed configured-project discovery', async () => {
  api.projects.mockResolvedValueOnce([])
  const { unmount } = render(<App api={api} />)
  expect(await screen.findByRole('status')).toHaveTextContent('No projects are configured')
  unmount()
  api.projects.mockRejectedValueOnce(new Error('Unable to connect to the CodeStruct backend.'))
  render(<App api={api} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Configured projects could not be loaded')
})

test('does not allow an unavailable configured project to be submitted', async () => {
  api.projects.mockResolvedValueOnce([{ id: 'offline', display_name: 'Offline project', available: false }])
  render(<App api={api} />)
  expect(await screen.findByRole('option', { name: 'Offline project (unavailable)' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Analyze project' })).toBeDisabled()
})

test('announces progress and offers cancellation for an active job', async () => {
  const user = userEvent.setup()
  analysis.job = { state: 'parsing', terminal: false, progress: { message_code: 'PARSING_FILES', percent: 40 } }
  render(<App api={api} />)
  expect(screen.getByRole('status')).toHaveTextContent('parsing files · 40%')
  expect(screen.getByRole('button', { name: 'Analyze project' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(cancel).toHaveBeenCalledOnce()
})

test('preserves the last graph and requests an explicit forced refresh when provenance is present', async () => {
  const user = userEvent.setup()
  analysis.graph = { schema_version: '1.0.0' }
  analysis.job = { state: 'completed', terminal: true, cache_hit: true }
  analysis.provenance = { root_id: 'team', relative_path: '.' }
  render(<App api={api} />)
  expect(screen.getByLabelText('Graph compatibility entry')).toHaveTextContent('cache_hit|no error|graph loaded')
  await screen.findByRole('option', { name: 'Team project' })
  await user.click(screen.getByRole('button', { name: 'Refresh analysis' }))
  expect(submit).toHaveBeenCalledWith({ root_id: 'team', relative_path: '.' }, { refresh: true })
})

test('disables refresh and displays guidance when analysis has no provenance (URL-loaded)', async () => {
  analysis.graph = { schema_version: '1.0.0' }
  analysis.job = { state: 'completed', terminal: true, cache_hit: false }
  analysis.provenance = null
  render(<App api={api} />)
  await screen.findByRole('option', { name: 'Team project' })
  const refreshBtn = screen.getByRole('button', { name: 'Refresh analysis' })
  expect(refreshBtn).toBeDisabled()
  expect(screen.getByText('Select a project and choose Analyze project to run a new analysis.')).toBeInTheDocument()
})

test('loads analysis from URL query parameter ?analysis_id=ana_xyz and immediately scrubs URL on mount', async () => {
  window.history.replaceState({}, '', '/?analysis_id=ana_xyz&session_token=cap_secret_123&keep=1')
  render(<App api={api} />)
  await screen.findByRole('option', { name: 'Team project' })
  expect(load).toHaveBeenCalledWith('ana_xyz')
  expect(submit).not.toHaveBeenCalled()
  // Verified: credentials and analysis_id are scrubbed immediately from address bar
  expect(window.location.search).toBe('?keep=1')
})

test('cleans analysis_id parameter from URL on manual submission', async () => {
  window.history.replaceState({}, '', '/?analysis_id=ana_old&other=keep')
  const user = userEvent.setup()
  render(<App api={api} />)
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Configured project' }), 'team')
  await user.click(screen.getByRole('button', { name: 'Analyze project' }))
  expect(submit).toHaveBeenCalledWith({ root_id: 'team', relative_path: '.' })
  expect(window.location.search).toBe('?other=keep')
})

test('renders a redacted application error without discarding the form', async () => {
  analysis.error = { message: 'The analysis service is unavailable.' }
  render(<App api={api} />)
  await screen.findByRole('option', { name: 'Team project' })
  expect(screen.getByLabelText('Graph compatibility entry')).toHaveTextContent('initial|The analysis service is unavailable.|no graph')
  expect(await screen.findByRole('button', { name: 'Analyze project' })).toBeEnabled()
})

test('displays loaded analysis even if configured project discovery fails', async () => {
  api.projects.mockRejectedValueOnce(new Error('Backend connection refused.'))
  analysis.graph = { schema_version: '1.0.0' }
  analysis.job = { state: 'completed', terminal: true }
  render(<App api={api} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Configured projects could not be loaded')
  expect(screen.getByLabelText('Graph compatibility entry')).toHaveTextContent('completed|no error|graph loaded')
})

test('handles source navigation with bound session token and displays visible feedback', async () => {
  api.navigateEditor.mockResolvedValueOnce({ status: 'queued' })

  window.history.replaceState({}, '', '/?analysis_id=ana_1&session_token=cap_bound_tok')
  analysis.graph = { schema_version: '1.0.0' }
  analysis.job = { analysis_id: 'ana_1', state: 'completed', terminal: true }

  const user = userEvent.setup()
  render(<App api={api} />)

  const triggerBtn = screen.getByRole('button', { name: 'Trigger Navigation' })
  await user.click(triggerBtn)

  expect(api.navigateEditor).toHaveBeenCalledWith({
    session_token: 'cap_bound_tok',
    relative_path: 'app.py',
    line: 10,
    column: 2,
  })

  expect(await screen.findByRole('status')).toHaveTextContent('Navigation command sent to editor (app.py:10).')
})

test('clears session token on project change so project B cannot use project A credentials', async () => {
  api.navigateEditor.mockClear()

  window.history.replaceState({}, '', '/?analysis_id=ana_1&session_token=cap_bound_tok')
  analysis.graph = { schema_version: '1.0.0' }
  analysis.job = { analysis_id: 'ana_1', state: 'completed', terminal: true }

  const user = userEvent.setup()
  render(<App api={api} />)

  // Wait for projects to load
  await screen.findByRole('option', { name: 'Other project' })

  // Switch project from team to other_proj
  const projectSelect = screen.getByRole('combobox', { name: 'Configured project' })
  await user.selectOptions(projectSelect, 'other_proj')

  // Now trigger navigation: token should be cleared/unbound
  const triggerBtn = screen.getByRole('button', { name: 'Trigger Navigation' })
  await user.click(triggerBtn)

  expect(api.navigateEditor).not.toHaveBeenCalled()
  expect(await screen.findByRole('alert')).toHaveTextContent('Editor navigation unavailable: No active IDE session is connected')
})

test('displays visible error alert when editor navigation request fails', async () => {
  api.navigateEditor.mockRejectedValueOnce(new Error('Session cap_expired is expired or invalid'))

  window.history.replaceState({}, '', '/?analysis_id=ana_1&session_token=cap_expired')
  analysis.graph = { schema_version: '1.0.0' }
  analysis.job = { analysis_id: 'ana_1', state: 'completed', terminal: true }

  const user = userEvent.setup()
  render(<App api={api} />)

  const triggerBtn = screen.getByRole('button', { name: 'Trigger Navigation' })
  await user.click(triggerBtn)

  expect(await screen.findByRole('alert')).toHaveTextContent('Editor navigation unavailable: Session cap_expired is expired or invalid.')
})



