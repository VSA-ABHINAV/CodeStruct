import { useEffect, useLayoutEffect, useRef, useState } from 'react'

/**
 * NodeContextMenu — Accessible, keyboard-navigable context menu
 * for graph nodes on right-click.
 */
export default function NodeContextMenu({
  node,
  position,
  onClose,
  onNavigateSource,
  onSelect,
  onCenter,
}) {
  const menuRef = useRef(null)
  const [copiedAction, setCopiedAction] = useState(null)
  const [adjustedPos, setAdjustedPos] = useState({ x: position.x, y: position.y })

  const location = node?.data?.location
  const qualifiedName = node?.data?.qualifiedName || node?.data?.description || node?.data?.label || node?.id
  const kindLabel = node?.data?.kindLabel || node?.data?.kind || 'Entity'

  // Clamp menu position to stay within viewport bounds
  useLayoutEffect(() => {
    if (!menuRef.current) return
    const rect = menuRef.current.getBoundingClientRect()
    const padding = 12
    let x = position.x
    let y = position.y

    if (x + rect.width > window.innerWidth - padding) {
      x = Math.max(padding, window.innerWidth - rect.width - padding)
    }
    if (y + rect.height > window.innerHeight - padding) {
      y = Math.max(padding, window.innerHeight - rect.height - padding)
    }

    setAdjustedPos({ x, y })
  }, [position])

  // Focus the first button on mount and set up outside click + Escape dismissal
  useEffect(() => {
    const el = menuRef.current
    if (el) {
      const firstBtn = el.querySelector('button')
      firstBtn?.focus()
    }

    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose()
      }
    }

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        if (!menuRef.current) return
        const buttons = Array.from(menuRef.current.querySelectorAll('button:not(:disabled)'))
        if (!buttons.length) return
        const currentIndex = buttons.indexOf(document.activeElement)
        const nextIndex = e.key === 'ArrowDown'
          ? (currentIndex >= 0 && currentIndex < buttons.length - 1 ? currentIndex + 1 : 0)
          : (currentIndex > 0 ? currentIndex - 1 : buttons.length - 1)
        buttons[nextIndex]?.focus()
      }

      if (e.key === 'Tab') {
        onClose()
      }
    }

    document.addEventListener('mousedown', handleClickOutside, true)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside, true)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  const copyText = async (text, actionKey) => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedAction(actionKey)
      setTimeout(() => {
        onClose()
      }, 600)
    } catch {
      onClose()
    }
  }

  const handleOpenEditor = () => {
    if (onNavigateSource && location?.path && location?.startLine != null) {
      onNavigateSource({
        path: location.path,
        line: location.startLine,
        column: location.startColumn || null,
      })
    }
    onClose()
  }

  const handleSelectDetails = () => {
    onSelect?.({ type: 'node', id: node.id })
    onClose()
  }

  const handleCenter = () => {
    onCenter?.(node.id)
    onClose()
  }

  return (
    <div
      ref={menuRef}
      className="cs-context-menu"
      role="menu"
      aria-label={`Actions for ${node.data?.label || node.id}`}
      style={{
        left: `${adjustedPos.x}px`,
        top: `${adjustedPos.y}px`,
      }}
    >
      <div className="cs-context-menu__header">
        <span className="cs-context-menu__badge">{kindLabel}</span>
        <span className="cs-context-menu__title" title={node.data?.label || node.id}>
          {node.data?.label || node.id}
        </span>
      </div>

      <div className="cs-context-menu__items">
        {location?.path && location?.startLine != null && (
          <button
            type="button"
            className="cs-context-menu__item cs-context-menu__item--primary"
            role="menuitem"
            onClick={handleOpenEditor}
          >
            <span className="cs-context-menu__icon" aria-hidden="true">⌖</span>
            <span className="cs-context-menu__label-group">
              <span className="cs-context-menu__label">Open in Editor</span>
              <span className="cs-context-menu__hint">{location.path}:{location.startLine}</span>
            </span>
          </button>
        )}

        <button
          type="button"
          className="cs-context-menu__item"
          role="menuitem"
          onClick={handleSelectDetails}
        >
          <span className="cs-context-menu__icon" aria-hidden="true">ℹ</span>
          <span className="cs-context-menu__label-group">
            <span className="cs-context-menu__label">View Details</span>
          </span>
        </button>

        {onCenter && (
          <button
            type="button"
            className="cs-context-menu__item"
            role="menuitem"
            onClick={handleCenter}
          >
            <span className="cs-context-menu__icon" aria-hidden="true">⊙</span>
            <span className="cs-context-menu__label-group">
              <span className="cs-context-menu__label">Center on Canvas</span>
            </span>
          </button>
        )}

        <hr className="cs-context-menu__divider" />

        <button
          type="button"
          className="cs-context-menu__item"
          role="menuitem"
          onClick={() => copyText(qualifiedName, 'qualifiedName')}
        >
          <span className="cs-context-menu__icon" aria-hidden="true">⎘</span>
          <span className="cs-context-menu__label-group">
            <span className="cs-context-menu__label">
              {copiedAction === 'qualifiedName' ? 'Copied Qualified Name!' : 'Copy Qualified Name'}
            </span>
            <span className="cs-context-menu__hint">{qualifiedName}</span>
          </span>
        </button>

        {location?.path && (
          <button
            type="button"
            className="cs-context-menu__item"
            role="menuitem"
            onClick={() => copyText(location.path, 'filePath')}
          >
            <span className="cs-context-menu__icon" aria-hidden="true">⎘</span>
            <span className="cs-context-menu__label-group">
              <span className="cs-context-menu__label">
                {copiedAction === 'filePath' ? 'Copied Path!' : 'Copy File Path'}
              </span>
              <span className="cs-context-menu__hint">{location.path}</span>
            </span>
          </button>
        )}
      </div>
    </div>
  )
}

