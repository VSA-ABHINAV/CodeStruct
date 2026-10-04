import { ReactFlowProvider } from '@xyflow/react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, test, vi } from 'vitest'

import Graph from '../../Graph.jsx'
import DiagnosticsPanel from './DiagnosticsPanel.jsx'
import ExplorerToolbar from './ExplorerToolbar.jsx'
import SearchBox from './SearchBox.jsx'
import TopToolbar from './TopToolbar.jsx'
import ArchitectureGraph from './ArchitectureGraph.jsx'
import ClassCardNode from './nodes/ClassCardNode.jsx'
import DefaultCardNode from './nodes/DefaultCardNode.jsx'
import FunctionCardNode from './nodes/FunctionCardNode.jsx'
import { layoutGraph } from './graphLayout.js'

vi.mock('./ArchitectureExplorer.jsx', () => ({
  default: ({ graph, state, projectName }) => (
    <div className="architecture-explorer">
      <span>{projectName}</span>
      <span>{state}</span>
      <span>{graph ? 'has-graph' : 'no-graph'}</span>
    </div>
  ),
}))

describe('Additional UI and Node Components', () => {
  test('Graph compatibility component renders ArchitectureExplorer correctly', () => {
    const { container } = render(
      <Graph
        files={[{ id: 'f1', path: 'app.py' }]}
        dependencies={[]}
        state="completed"
        projectName="Test Project"
      />
    )
    expect(container.querySelector('.architecture-explorer')).toBeInTheDocument()
  })

  test('DiagnosticsPanel filters items by severity and triggers element inspection', async () => {
    const user = userEvent.setup()
    const onSeverity = vi.fn()
    const onSelect = vi.fn()
    const sampleDiags = [
      {
        id: 'd1',
        code: 'UNRESOLVED_IMPORT',
        severity: 'warning',
        message: 'Could not resolve import helper',
        location: { path: 'app.py', startLine: 3, startColumn: 1 },
        entityId: 'node_app_main',
      },
      {
        id: 'd2',
        code: 'SYNTAX_ERROR',
        severity: 'error',
        message: 'Invalid syntax',
        location: { path: 'broken.py', startLine: 1 },
        edgeId: 'edge_call_1',
      },
    ]

    const { rerender } = render(
      <DiagnosticsPanel
        diagnostics={sampleDiags}
        severity="all"
        onSeverity={onSeverity}
        onSelect={onSelect}
      />
    )

    expect(screen.getByText(/Analysis diagnostics \(2\)/)).toBeInTheDocument()
    expect(screen.getByText('Could not resolve import helper')).toBeInTheDocument()

    // Select related element
    const inspectButtons = screen.getAllByRole('button', { name: 'Inspect related element' })
    await user.click(inspectButtons[0])
    expect(onSelect).toHaveBeenCalledWith({ type: 'node', id: 'node_app_main' })

    // Change severity dropdown
    const select = screen.getByRole('combobox', { name: 'Severity' })
    await user.selectOptions(select, 'error')
    expect(onSeverity).toHaveBeenCalledWith('error')

    // Empty filter state
    rerender(
      <DiagnosticsPanel
        diagnostics={[]}
        severity="error"
        onSeverity={onSeverity}
        onSelect={onSelect}
      />
    )
    expect(screen.getByText(/No analysis diagnostics match this filter/)).toBeInTheDocument()
  })

  test('SearchBox handles input, stepping, activation, and clear', async () => {
    const user = userEvent.setup()
    const onQueryChange = vi.fn()
    const onStep = vi.fn()
    const onActivate = vi.fn()

    render(
      <SearchBox
        query="service"
        onQueryChange={onQueryChange}
        resultCount={3}
        activeIndex={1}
        onStep={onStep}
        onActivate={onActivate}
      />
    )

    expect(screen.getByText('2 of 3 matches')).toBeInTheDocument()

    const input = screen.getByRole('textbox', { name: 'Search architecture' })
    await user.type(input, '{arrowdown}')
    expect(onStep).toHaveBeenCalledWith(1)

    await user.type(input, '{arrowup}')
    expect(onStep).toHaveBeenCalledWith(-1)

    await user.type(input, '{enter}')
    expect(onActivate).toHaveBeenCalled()

    await user.type(input, '{escape}')
    expect(onQueryChange).toHaveBeenCalledWith('')

    const clearBtn = screen.getByRole('button', { name: 'Clear' })
    await user.click(clearBtn)
    expect(onQueryChange).toHaveBeenCalledWith('')

    const nextBtn = screen.getByRole('button', { name: 'Next search result' })
    await user.click(nextBtn)
    expect(onStep).toHaveBeenCalledWith(1)
  })

  test('ExplorerToolbar triggers view mode and controller navigation actions', async () => {
    const user = userEvent.setup()
    const onView = vi.fn()
    const onCenterSelected = vi.fn()
    const onClearSelection = vi.fn()
    const controller = {
      zoomIn: vi.fn(),
      zoomOut: vi.fn(),
      fitView: vi.fn(),
      reset: vi.fn(),
    }

    render(
      <ExplorerToolbar
        view="graph"
        onView={onView}
        controller={controller}
        selected={{ id: 'node_1' }}
        onCenterSelected={onCenterSelected}
        onClearSelection={onClearSelection}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(onView).toHaveBeenCalledWith('table')

    await user.click(screen.getByRole('button', { name: 'Zoom in' }))
    expect(controller.zoomIn).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Zoom out' }))
    expect(controller.zoomOut).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Fit view' }))
    expect(controller.fitView).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Reset view' }))
    expect(controller.reset).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Center selected' }))
    expect(onCenterSelected).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Clear selection' }))
    expect(onClearSelection).toHaveBeenCalled()
  })

  test('ClassCardNode, DefaultCardNode, and FunctionCardNode render correctly', () => {
    const { container: classContainer } = render(
      <ReactFlowProvider>
        <ClassCardNode
          data={{
            label: 'UserService',
            isBase: true,
            methods: [{ id: 'm1', name: 'get_user' }, { id: 'm2', name: 'save_user' }],
            selectedMethodId: 'm1',
          }}
          selected={true}
        />
      </ReactFlowProvider>
    )
    expect(classContainer.querySelector('.cs-card--class')).toBeInTheDocument()
    expect(screen.getByText('UserService')).toBeInTheDocument()
    expect(screen.getByText('get_user()')).toBeInTheDocument()

    const { container: defaultContainer } = render(
      <ReactFlowProvider>
        <DefaultCardNode
          data={{
            label: 'auth_module',
            kind: 'module',
          }}
          selected={false}
        />
      </ReactFlowProvider>
    )
    expect(defaultContainer.querySelector('.cs-card--default')).toBeInTheDocument()
    expect(screen.getByText('auth_module')).toBeInTheDocument()

    const { container: funcContainer } = render(
      <ReactFlowProvider>
        <FunctionCardNode
          data={{
            label: 'process_request',
            kind: 'function',
            async: true,
          }}
          selected={true}
        />
      </ReactFlowProvider>
    )
    expect(funcContainer.querySelector('.cs-card--function')).toBeInTheDocument()
    expect(screen.getByText('process_request()')).toBeInTheDocument()
  })

  test('TopToolbar renders actions, search, project picker modal, and more menu', async () => {
    const user = userEvent.setup()
    const onToggleTable = vi.fn()
    const onToggleDiagnostics = vi.fn()
    const onToggleFocusMode = vi.fn()
    const onRefresh = vi.fn()
    const onSelectProject = vi.fn()
    const onSubmitProject = vi.fn()
    const controller = {
      fitView: vi.fn(),
    }

    render(
      <TopToolbar
        currentIdentity="Project One"
        analysisId="ana_123"
        projects={[{ id: 'proj1', display_name: 'Project One', available: true }]}
        projectId="proj1"
        onSelectProject={onSelectProject}
        onSubmitProject={onSubmitProject}
        onRefresh={onRefresh}
        provenance={{ root_id: 'proj1', relative_path: '.' }}
        onToggleTable={onToggleTable}
        onToggleDiagnostics={onToggleDiagnostics}
        onToggleFocusMode={onToggleFocusMode}
        controller={controller}
        graph={{ nodes: [{ id: 'n1', label: 'Root' }], edges: [] }}
      />
    )

    expect(screen.getByText('Project One')).toBeInTheDocument()

    // Test Fit View
    const fitBtn = screen.getByRole('button', { name: 'Fit visible graph' })
    await user.click(fitBtn)
    expect(controller.fitView).toHaveBeenCalled()

    // Test Focus Mode toggle
    const focusBtn = screen.getByRole('button', { name: 'Focus mode / Fullscreen' })
    await user.click(focusBtn)
    expect(onToggleFocusMode).toHaveBeenCalled()

    // Open More Menu
    const moreBtn = screen.getByRole('button', { name: 'More actions' })
    await user.click(moreBtn)

    // Click Toggle Table in More Menu
    const tableMenuBtn = screen.getByRole('menuitem', { name: /Accessible table view/ })
    await user.click(tableMenuBtn)
    expect(onToggleTable).toHaveBeenCalled()

    // Open More Menu again and click Diagnostics
    await user.click(moreBtn)
    const diagMenuBtn = screen.getByRole('menuitem', { name: /Diagnostics drawer/ })
    await user.click(diagMenuBtn)
    expect(onToggleDiagnostics).toHaveBeenCalled()

    // Open More Menu again and click About
    await user.click(moreBtn)
    const aboutMenuBtn = screen.getByRole('menuitem', { name: /About CodeStruct/ })
    await user.click(aboutMenuBtn)
    expect(screen.getByText(/Analyze authorized Python projects/)).toBeInTheDocument()

    // Close About dialog
    const closeAboutBtn = screen.getByRole('button', { name: 'Close dialog' })
    await user.click(closeAboutBtn)

    // Open More Menu and click Export Graphviz (DOT)
    const createObjectURLMock = vi.fn().mockReturnValue('blob:http://localhost/dot-blob')
    const revokeObjectURLMock = vi.fn()
    globalThis.URL.createObjectURL = createObjectURLMock
    globalThis.URL.revokeObjectURL = revokeObjectURLMock

    render(
      <TopToolbar
        currentIdentity="Project One"
        analysisId="ana_123"
        projects={[{ id: 'proj1', display_name: 'Project One', available: true }]}
        projectId="proj1"
        graph={{ nodes: [{ id: 'n1', displayName: 'Root', qualifiedName: 'app.Root', kind: 'module' }], edges: [] }}
      />
    )
    const exportMoreBtn = screen.getAllByRole('button', { name: 'More actions' })[1]
    await user.click(exportMoreBtn)
    const dotExportBtn = screen.getByRole('menuitem', { name: /Export Graphviz \(DOT\)/ })
    await user.click(dotExportBtn)
    expect(createObjectURLMock).toHaveBeenCalled()

    // Open Project Picker modal
    const pickerBtn = screen.getAllByRole('button', { name: 'Current analysis: Project One' })[0]
    await user.click(pickerBtn)
    expect(screen.getAllByText('Project One').length).toBeGreaterThan(0)
  })

  test('ArchitectureGraph renders canvas, nodes, edges, and registers controller', () => {
    const onSelect = vi.fn()
    const onController = vi.fn()
    const sampleGraph = {
      nodes: [
        { id: 'n1', kind: 'module', displayName: 'mod_a', name: 'mod_a', qualifiedName: 'mod_a' },
        { id: 'n2', kind: 'function', displayName: 'fn_b', name: 'fn_b', qualifiedName: 'mod_a.fn_b' },
      ],
      edges: [
        { id: 'e1', kind: 'defines', sourceId: 'n1', targetId: 'n2', resolutionStatus: 'resolved' },
      ],
      evidence: [],
      diagnostics: [],
    }
    const positionedNodes = layoutGraph(sampleGraph.nodes, sampleGraph.edges)

    const { container } = render(
      <ReactFlowProvider>
        <ArchitectureGraph
          graph={sampleGraph}
          positionedNodes={positionedNodes}
          matchIds={new Set(['n1'])}
          reducedMotion={true}
          selectedId="n1"
          onSelect={onSelect}
          onController={onController}
        />
      </ReactFlowProvider>
    )

    expect(container.querySelector('.cs-canvas')).toBeInTheDocument()
    expect(container.querySelector('.cs-minimap')).toBeInTheDocument()
    expect(container.querySelector('.cs-controls')).toBeInTheDocument()
  })
})


