import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import ArchitectureExplorer from './ArchitectureExplorer.jsx'
import GraphStatus from './GraphStatus.jsx'
import {
  partialGraph,
  smallGraph,
  unsupportedGraph,
} from './fixtures/graphFixtures.js'

vi.mock('./ArchitectureGraph.jsx', () => ({
  default: ({ graph, reducedMotion, onSelect }) => {
    return <section aria-label="Mock graph renderer" data-reduced-motion={String(reducedMotion)}>
      <span>{graph.nodes.length} rendered entities</span>
      {graph.nodes[0] && <button type="button" onClick={() => onSelect({ type: 'node', id: graph.nodes[0].id })}>Select first rendered entity</button>}
    </section>
  },
}))

const STATES = [
  ['initial', 'Ready to explore'],
  ['project_selected', 'Project selected'],
  ['validation_failed', 'Validation failed'],
  ['queued', 'Queued'],
  ['scanning', 'Scanning'],
  ['parsing', 'Parsing'],
  ['resolving', 'Resolving'],
  ['building_graph', 'Building graph'],
  ['completed', 'Completed'],
  ['partially_completed', 'Partially completed'],
  ['failed', 'Analysis failed'],
  ['cancellation_requested', 'Stopping safely'],
  ['cancelled', 'Cancelled'],
  ['cache_hit', 'Cached result'],
  ['retrieving_graph', 'Retrieving graph'],
  ['empty', 'Empty graph'],
]

describe('architecture explorer states and interactions', () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false })
  })

  test.each(STATES)('renders the %s state with an announced heading', (state, heading) => {
    render(<GraphStatus state={state} assertive={state.includes('failed')} />)
    expect(screen.getByRole('heading', { name: heading })).toBeVisible()
  })

  test('search, keyboard navigation, table selection, details, and reset filters work', async () => {
    const user = userEvent.setup()
    render(<ArchitectureExplorer graph={smallGraph} />)

    const search = screen.getByRole('textbox', { name: 'Search architecture' })
    await user.type(search, 'service')
    expect(screen.getByText(/1\/2/)).toBeVisible()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('heading', { name: 'Entity details' })).toBeVisible()

    /* Table is accessed via overflow menu */
    await user.click(screen.getByRole('button', { name: 'More actions' }))
    await user.click(screen.getByRole('menuitem', { name: /Accessible table/ }))
    expect(screen.getByRole('table')).toBeVisible()
    await user.click(screen.getAllByRole('button', { name: 'Inspect' })[0])
    expect(screen.getAllByText(/project/i, { selector: 'dd' }).length).toBeGreaterThan(0)

    await user.click(screen.getByText('Filters'))
    await user.click(screen.getByRole('checkbox', { name: 'class' }))
    expect(screen.getByText(/Showing 1 of 5 entities/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Reset all filters' }))
    expect(screen.getByText(/Showing 5 of 5 entities/)).toBeVisible()
  })

  test('partial diagnostics can be filtered and associated with an element', async () => {
    const user = userEvent.setup()
    render(<ArchitectureExplorer graph={partialGraph} />)
    expect(screen.getByRole('heading', { name: 'Partially completed' })).toBeVisible()

    /* Diagnostics are in the drawer, accessed via overflow menu */
    await user.click(screen.getByRole('button', { name: 'More actions' }))
    await user.click(screen.getByRole('menuitem', { name: /Diagnostics/ }))
    expect(screen.getByText(/FILE_SYNTAX_ERROR/)).toBeVisible()
    await user.selectOptions(screen.getByRole('combobox', { name: /Severity/ }), 'warning')
    expect(screen.getByText(/No analysis diagnostics match/)).toBeVisible()
    await user.selectOptions(screen.getByRole('combobox', { name: /Severity/ }), 'error')
    await user.click(screen.getByRole('button', { name: 'Inspect related element' }))
    expect(screen.getByRole('heading', { name: 'Entity details' })).toBeVisible()
  })

  test('unsupported schemas and large graphs fail or pause safely', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<ArchitectureExplorer graph={unsupportedGraph} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Unsupported graph schema')

    rerender(<ArchitectureExplorer graph={smallGraph} largeGraphThreshold={{ nodes: 2, edges: 2 }} />)
    expect(screen.getByRole('heading', { name: 'Large graph' })).toBeVisible()
    expect(screen.getByText('3 rendered entities')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Render complete graph anyway' }))
    expect(screen.getByText('5 rendered entities')).toBeVisible()
  })

  test('partial graph pages report totals and offer keyboard-accessible loading', async () => {
    const user = userEvent.setup()
    const onLoadMore = vi.fn()
    const graph = { ...smallGraph, page: { returned_nodes: 5, total_nodes: 12, returned_edges: 3, total_edges: 20, next_cursor: 'opaque', partial_load: true } }
    render(<ArchitectureExplorer graph={graph} onLoadMore={onLoadMore} />)
    expect(screen.getByText(/Only 5 of 12 entities are loaded/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Load more graph data' }))
    expect(onLoadMore).toHaveBeenCalledOnce()

    /* Switch to table via overflow menu */
    await user.click(screen.getByRole('button', { name: 'More actions' }))
    await user.click(screen.getByRole('menuitem', { name: /Accessible table/ }))
    expect(screen.getByText(/Loaded graph slice: 5 of 12 entities/)).toBeVisible()
  })

  test('reduced motion reaches only the renderer boundary', () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true })
    render(<ArchitectureExplorer graph={smallGraph} />)
    expect(screen.getByLabelText('Mock graph renderer')).toHaveAttribute('data-reduced-motion', 'true')
  })

  test('accessibility scans find no axe violations in completed and partial views', async () => {
    const completed = render(<ArchitectureExplorer graph={smallGraph} />)
    expect(await axe(completed.container)).toHaveNoViolations()
    completed.unmount()
    const partial = render(<ArchitectureExplorer graph={partialGraph} />)
    expect(await axe(partial.container)).toHaveNoViolations()
  })

  test('analysis identity reflects displayed analysis and is independent of project picker', () => {
    render(
      <ArchitectureExplorer
        graph={smallGraph}
        provenance={{ root_id: 'cap_editor_123', relative_path: 'sample_project.py' }}
        projects={[{ id: 'demo_root', display_name: 'Demo Root', available: true }]}
        projectId="demo_root"
      />
    )
    // Current identity button shows real file identity sample_project.py, not internal token or selected demo_root
    expect(screen.getByRole('button', { name: /Current analysis: sample_project\.py/i })).toBeVisible()
    expect(screen.queryByText('cap_editor_123')).not.toBeInTheDocument()
  })

  test('drawer selection opens on-demand and closes cleanly without permanent empty area', async () => {
    const user = userEvent.setup()
    render(<ArchitectureExplorer graph={smallGraph} />)

    // Initially no entity selected -> no large permanent "No element selected" area
    expect(screen.queryByRole('heading', { name: 'Entity details' })).not.toBeInTheDocument()
    expect(screen.queryByText('No element selected')).not.toBeInTheDocument()

    // Select an entity via mock graph button
    await user.click(screen.getByRole('button', { name: 'Select first rendered entity' }))
    expect(screen.getByRole('heading', { name: 'Entity details' })).toBeVisible()

    // Click close button in Details drawer
    await user.click(screen.getByRole('button', { name: 'Close details panel' }))
    expect(screen.queryByRole('heading', { name: 'Entity details' })).not.toBeInTheDocument()
  })

  test('focus mode toggles via keyboard shortcuts and toolbar action', async () => {
    const user = userEvent.setup()
    const { container } = render(<ArchitectureExplorer graph={smallGraph} />)

    // Click fullscreen / focus mode button in toolbar
    const focusBtn = screen.getByRole('button', { name: /Focus mode/i })
    await user.click(focusBtn)
    expect(container.querySelector('.cs-explorer--focus-mode')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Exit focus mode' })).toBeVisible()

    // Press Escape to exit focus mode
    await user.keyboard('{Escape}')
    expect(container.querySelector('.cs-explorer--focus-mode')).not.toBeInTheDocument()
  })

  test('CS-007: graph and table maintain strict data parity across loaded slice and filtered states', async () => {
    const user = userEvent.setup()
    const pagedGraph = {
      ...smallGraph,
      page: {
        returned_nodes: 5,
        total_nodes: 25,
        returned_edges: 4,
        total_edges: 30,
        next_cursor: 'cursor_p2',
        partial_load: true,
      },
    }
    render(<ArchitectureExplorer graph={pagedGraph} />)

    // Graph view status banner clearly identifies partial slice
    expect(screen.getByText(/Only 5 of 25 entities are loaded/)).toBeVisible()
    expect(screen.getByText(/Showing 5 of 5 entities/)).toBeVisible()

    // Switch to table view
    await user.click(screen.getByRole('button', { name: 'More actions' }))
    await user.click(screen.getByRole('menuitem', { name: /Accessible table/ }))

    // Table view header reflects the exact same loaded slice
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.getByText(/Loaded graph slice: 5 of 25 entities and 4 of 30 relationships/)).toBeVisible()

    // Both views have exactly 5 node rows + 3 relationship rows in the table
    const table = screen.getByRole('table')
    expect(table).toBeVisible()
    const rows = table.querySelectorAll('tbody tr')
    expect(rows.length).toBe(8) // 5 entities + 3 relationships
  })

  test('CS-021: renders cancelled state banner with polite live region announcement', () => {
    render(<ArchitectureExplorer graph={null} state="cancelled" />)
    const banner = screen.getByRole('status')
    expect(banner).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Cancelled' })).toBeVisible()
    expect(screen.getByText(/Incomplete work is not presented as a complete result/)).toBeVisible()
  })
})
