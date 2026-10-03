import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import NodeContextMenu from './NodeContextMenu.jsx'

describe('NodeContextMenu component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('renders menu items and passes accessibility check', async () => {
    const node = {
      id: 'node-auth-service',
      data: {
        label: 'AuthService',
        qualifiedName: 'auth.service.AuthService',
        kind: 'class',
        kindLabel: 'Class',
        location: {
          path: 'auth/service.py',
          startLine: 15,
          startColumn: 1,
        },
      },
    }

    const onClose = vi.fn()
    const onNavigateSource = vi.fn()
    const onSelect = vi.fn()
    const onCenter = vi.fn()

    const { container } = render(
      <NodeContextMenu
        node={node}
        position={{ x: 100, y: 100 }}
        onClose={onClose}
        onNavigateSource={onNavigateSource}
        onSelect={onSelect}
        onCenter={onCenter}
      />
    )

    expect(screen.getByRole('menu')).toBeVisible()
    expect(screen.getByText('AuthService')).toBeVisible()
    expect(screen.getByText('Class')).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Open in Editor/i })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /View Details/i })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Center on Canvas/i })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Copy Qualified Name/i })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Copy File Path/i })).toBeVisible()

    expect(await axe(container)).toHaveNoViolations()
  })

  test('triggers open in editor and closes menu', async () => {
    const user = userEvent.setup()
    const node = {
      id: 'node-user',
      data: {
        label: 'User',
        kind: 'class',
        location: {
          path: 'models/user.py',
          startLine: 25,
          startColumn: 5,
        },
      },
    }

    const onClose = vi.fn()
    const onNavigateSource = vi.fn()

    render(
      <NodeContextMenu
        node={node}
        position={{ x: 50, y: 50 }}
        onClose={onClose}
        onNavigateSource={onNavigateSource}
      />
    )

    const openBtn = screen.getByRole('menuitem', { name: /Open in Editor/i })
    await user.click(openBtn)

    expect(onNavigateSource).toHaveBeenCalledWith({
      path: 'models/user.py',
      line: 25,
      column: 5,
    })
    expect(onClose).toHaveBeenCalled()
  })

  test('triggers view details and center on canvas', async () => {
    const user = userEvent.setup()
    const node = {
      id: 'node-func',
      data: { label: 'compute_hash', kind: 'function' },
    }

    const onClose = vi.fn()
    const onSelect = vi.fn()
    const onCenter = vi.fn()

    const { rerender } = render(
      <NodeContextMenu
        node={node}
        position={{ x: 50, y: 50 }}
        onClose={onClose}
        onSelect={onSelect}
        onCenter={onCenter}
      />
    )

    // View details
    const detailsBtn = screen.getByRole('menuitem', { name: /View Details/i })
    await user.click(detailsBtn)
    expect(onSelect).toHaveBeenCalledWith({ type: 'node', id: 'node-func' })
    expect(onClose).toHaveBeenCalled()

    // Center
    rerender(
      <NodeContextMenu
        node={node}
        position={{ x: 50, y: 50 }}
        onClose={onClose}
        onSelect={onSelect}
        onCenter={onCenter}
      />
    )
    const centerBtn = screen.getByRole('menuitem', { name: /Center on Canvas/i })
    await user.click(centerBtn)
    expect(onCenter).toHaveBeenCalledWith('node-func')
  })

  test('closes on Escape key press', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const node = { id: 'n1', data: { label: 'Node 1' } }

    render(
      <NodeContextMenu
        node={node}
        position={{ x: 50, y: 50 }}
        onClose={onClose}
      />
    )

    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })
})
