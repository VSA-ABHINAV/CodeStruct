import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import DetailsPanel from './DetailsPanel.jsx'

describe('DetailsPanel component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('renders empty state when no element is selected', async () => {
    const { container } = render(<DetailsPanel details={null} />)
    expect(screen.getByRole('heading', { name: 'Details' })).toBeVisible()
    expect(screen.getByText('No element selected')).toBeVisible()
    expect(await axe(container)).toHaveNoViolations()
  })

  test('renders node details with 7 collapsible sections, humanized enums, copy controls, and pagination actions', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const onSelect = vi.fn()
    const onCenter = vi.fn()
    const onNavigateSource = vi.fn()
    const onLoadMore = vi.fn()

    // Mock clipboard API
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: writeTextMock,
      },
      writable: true,
      configurable: true,
    })

    const nodeItem = {
      id: 'n-service',
      kind: 'class',
      displayName: 'Service',
      qualifiedName: 'app.main.Service',
      location: {
        path: 'app/main.py',
        startLine: 10,
        startColumn: 1,
        endLine: 40,
        endColumn: 20,
      },
      classification: 'internal',
    }

    const parentNode = {
      id: 'n-module',
      kind: 'module',
      displayName: 'main',
      qualifiedName: 'app.main',
    }

    const callerNode = {
      id: 'n-caller',
      kind: 'function',
      displayName: 'init_app',
      qualifiedName: 'app.init_app',
    }

    const details = {
      type: 'node',
      item: nodeItem,
      parent: parentNode,
      incoming: [
        {
          id: 'e-call-1',
          kind: 'calls',
          sourceId: 'n-caller',
          targetId: 'n-service',
          resolutionStatus: 'resolved',
          confidence: 'exact',
        },
      ],
      outgoing: [
        {
          id: 'e-unloaded',
          kind: 'imports_symbol',
          sourceId: 'n-service',
          targetId: 'n-external',
          targetReference: 'external_pkg',
          resolutionStatus: 'unresolved',
          confidence: 'unknown',
          targetClassification: 'external',
        },
      ],
      diagnostics: [
        {
          id: 'd-1',
          code: 'TYPE_UNCERTAINTY',
          severity: 'warning',
          message: 'Target could not be statically verified.',
          location: { path: 'app/main.py', startLine: 12 },
          suggestedAction: 'Add type annotation',
        },
      ],
    }

    const graph = {
      nodes: [nodeItem, parentNode, callerNode],
      evidence: [],
      diagnostics: details.diagnostics,
    }

    const { container } = render(
      <DetailsPanel
        details={details}
        onClose={onClose}
        onSelect={onSelect}
        onCenter={onCenter}
        onNavigateSource={onNavigateSource}
        onLoadMore={onLoadMore}
        graph={graph}
      />
    )

    // Heading & overview
    expect(screen.getByRole('heading', { name: 'Entity details' })).toBeVisible()
    expect(screen.getByText('Service', { selector: 'strong.entity-title' })).toBeVisible()
    expect(screen.getByText('Class', { selector: '.badge--kind' })).toBeVisible()
    expect(screen.getByText('app.main.Service')).toBeVisible()

    // 7 Collapsible sections verified by heading
    expect(screen.getByRole('heading', { name: 'Overview' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Source location' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Containment' })).toBeVisible()
    expect(screen.getByRole('heading', { name: /Incoming relationships/ })).toBeVisible()
    expect(screen.getByRole('heading', { name: /Outgoing relationships/ })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Evidence and resolution' })).toBeVisible()
    expect(screen.getByRole('heading', { name: /Diagnostics/ })).toBeVisible()

    // Human-readable enums & labels
    expect(screen.getByText('Internal source unit')).toBeVisible()
    expect(screen.getByText('Static AST evidence')).toBeVisible()
    expect(screen.getByText('Imports symbol')).toBeVisible()

    // Test Copy button for qualified name
    const copyButtons = screen.getAllByRole('button', { name: /Copy qualified name/ })
    expect(copyButtons.length).toBeGreaterThan(0)
    await user.click(copyButtons[0])
    expect(writeTextMock).toHaveBeenCalledWith('app.main.Service')

    // Test Parent selection and center
    const parentButton = screen.getByRole('button', { name: /Select parent/ })
    await user.click(parentButton)
    expect(onSelect).toHaveBeenCalledWith({ type: 'node', id: 'n-module' })

    const centerParentButton = screen.getByRole('button', { name: /Center main in graph/ })
    await user.click(centerParentButton)
    expect(onCenter).toHaveBeenCalledWith('n-module')

    // Test Incoming relationships
    const callerButton = screen.getByRole('button', { name: /Select init_app/ })
    await user.click(callerButton)
    expect(onSelect).toHaveBeenCalledWith({ type: 'node', id: 'n-caller' })

    // Test Outgoing relationships with unloaded endpoint and load more button
    expect(screen.getByText(/external_pkg/)).toBeVisible()
    expect(screen.getByText(/External target/)).toBeVisible()
    const loadMoreBtn = screen.getByRole('button', { name: 'Load more graph data' })
    await user.click(loadMoreBtn)
    expect(onLoadMore).toHaveBeenCalled()

    // Test Diagnostics & Suggested action
    expect(screen.getByText('TYPE_UNCERTAINTY')).toBeVisible()
    expect(screen.getByText('Target could not be statically verified.')).toBeVisible()
    expect(screen.getByText('Add type annotation')).toBeVisible()

    // Test Source navigation
    const openSourceBtn = screen.getByRole('button', { name: 'Open source location' })
    await user.click(openSourceBtn)
    expect(onNavigateSource).toHaveBeenCalledWith(nodeItem.location)

    // Test Escape key closes panel
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()

    // Test Close button closes panel
    const closeBtn = screen.getByRole('button', { name: 'Close details panel' })
    await user.click(closeBtn)
    expect(onClose).toHaveBeenCalledTimes(2)

    // Axe scan
    expect(await axe(container)).toHaveNoViolations()
  })

  test('renders relationship details with hero, evidence observations, and accessibility compliance', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()

    const sourceNode = {
      id: 'n-mod',
      displayName: 'worker',
      qualifiedName: 'app.worker',
    }
    const targetNode = {
      id: 'n-queue',
      displayName: 'TaskQueue',
      qualifiedName: 'app.queue.TaskQueue',
    }

    const edgeItem = {
      id: 'e-import-1',
      kind: 'imports',
      sourceId: 'n-mod',
      targetId: 'n-queue',
      resolutionStatus: 'resolved',
      confidence: 'exact',
      confidenceReason: 'EXACT_STATIC_TARGET',
      occurrenceCount: 2,
    }

    const details = {
      type: 'edge',
      item: edgeItem,
      source: sourceNode,
      target: targetNode,
      evidence: [
        {
          id: 'ev-1',
          origin: 'static_ast',
          observationKind: 'direct_import',
          explanation: 'Imported via static AST statement',
          expression: 'from app.queue import TaskQueue',
          location: {
            path: 'app/worker.py',
            startLine: 3,
            startColumn: 1,
            endLine: 3,
            endColumn: 30,
          },
        },
      ],
      diagnostics: [],
    }

    const { container } = render(
      <DetailsPanel details={details} onSelect={onSelect} />
    )

    expect(screen.getByRole('heading', { name: 'Relationship evidence' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'worker' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'TaskQueue' })).toBeVisible()
    expect(screen.getByText('Exact static match')).toBeVisible()
    expect(screen.getByText('Exact static target resolved')).toBeVisible()
    expect(screen.getAllByText('Static AST evidence').length).toBeGreaterThan(0)
    expect(screen.getByText('from app.queue import TaskQueue')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'TaskQueue' }))
    expect(onSelect).toHaveBeenCalledWith({ type: 'node', id: 'n-queue' })

    expect(await axe(container)).toHaveNoViolations()
  })

  test('renders architecture metrics section when node attributes are present', async () => {
    const nodeItem = {
      id: 'n-controller',
      kind: 'class',
      displayName: 'Controller',
      qualifiedName: 'app.main.Controller',
      classification: 'internal',
      attributes: {
        fan_in: '3',
        fan_out: '5',
        instability: '0.62',
        centrality: '0.450',
        in_cycle: 'true',
        community_id: '2',
        runtime_calls: '14',
        runtime_duration_ms: '8.40',
      },
    }

    const details = {
      type: 'node',
      item: nodeItem,
      incoming: [],
      outgoing: [],
      children: [],
      evidence: [],
      diagnostics: [],
    }

    const { container } = render(<DetailsPanel details={details} />)

    expect(screen.getByRole('heading', { name: 'Architecture metrics' })).toBeVisible()
    expect(screen.getByText('Fan-in (incoming)')).toBeVisible()
    expect(screen.getByText('3')).toBeVisible()
    expect(screen.getByText('Fan-out (outgoing)')).toBeVisible()
    expect(screen.getByText('5')).toBeVisible()
    expect(screen.getByText('Instability (I)')).toBeVisible()
    expect(screen.getByText('0.62')).toBeVisible()
    expect(screen.getByText('Degree centrality')).toBeVisible()
    expect(screen.getByText('0.450')).toBeVisible()
    expect(screen.getByText('In cycle')).toBeVisible()
    expect(screen.getByText('Cluster #2')).toBeVisible()
    expect(screen.getByText('14 calls (8.40 ms)')).toBeVisible()

    expect(screen.getByRole('heading', { name: 'Architecture explanation' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Generate architecture explanation' })).toBeVisible()

    expect(await axe(container)).toHaveNoViolations()
  })
})

