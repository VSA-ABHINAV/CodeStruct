/**
 * Unified professional SVG icon library for the CodeStruct Architecture Explorer.
 * All icons are inline SVG, zero-dependency, accessible via aria-hidden, and
 * rendered at a consistent 20×20 default viewport.
 */

const defaults = { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': 'true' }
const icon = (props, ...children) => <svg {...defaults} {...props}>{children.map((c, i) => <g key={i}>{c}</g>)}</svg>

/* ── Brand ── */
export function LogoIcon(props) {
  return icon({ ...props, viewBox: '0 0 24 24', strokeWidth: 0, fill: 'currentColor' },
    <path d="M12 2L3 7v10l9 5 9-5V7l-9-5zm0 2.18L18.36 7.5 12 11 5.64 7.5 12 4.18zM5 9.09l6 3.33v6.5L5 15.59V9.09zm8 9.83v-6.5l6-3.33v6.5L13 18.92z" />
  )
}

/* ── Navigation ── */
export function OverviewIcon(props) {
  return icon(props,
    <circle cx="6" cy="6" r="2" />, <circle cx="14" cy="6" r="2" />, <circle cx="10" cy="14" r="2" />,
    <line x1="7.5" y1="7.5" x2="9" y2="12.5" />, <line x1="12.5" y1="7.5" x2="11" y2="12.5" />
  )
}

export function ClassesIcon(props) {
  return icon(props,
    <rect x="3" y="3" width="14" height="14" rx="2" />, <line x1="3" y1="7" x2="17" y2="7" />,
    <line x1="7" y1="10" x2="13" y2="10" />, <line x1="7" y1="13" x2="11" y2="13" />
  )
}

export function CallFlowIcon(props) {
  return icon(props,
    <path d="M4 4v6c0 2 2 4 6 4h4" />, <polyline points="12 10 16 14 12 18" />
  )
}

/* ── Entity types ── */
export function ClassIcon(props) {
  return icon(props,
    <rect x="3" y="3" width="14" height="14" rx="2" />, <line x1="3" y1="7.5" x2="17" y2="7.5" />,
    <circle cx="6" cy="5.25" r="0.8" fill="currentColor" stroke="none" />
  )
}

export function MethodIcon(props) {
  return icon(props,
    <polyline points="5 6 2 10 5 14" />, <polyline points="15 6 18 10 15 14" />,
    <line x1="11" y1="4" x2="9" y2="16" />
  )
}

export function FunctionIcon(props) {
  return icon({ ...props, strokeWidth: 0, fill: 'currentColor', viewBox: '0 0 20 20' },
    <text x="10" y="15" textAnchor="middle" fontSize="15" fontFamily="serif" fontStyle="italic">λ</text>
  )
}

export function ModuleIcon(props) {
  return icon(props,
    <path d="M4 4h5l2 2h5a1 1 0 011 1v8a1 1 0 01-1 1H4a1 1 0 01-1-1V5a1 1 0 011-1z" />
  )
}

/* ── Actions ── */
export function SearchIcon(props) {
  return icon(props,
    <circle cx="8.5" cy="8.5" r="5" />, <line x1="12.5" y1="12.5" x2="17" y2="17" />
  )
}

export function FitIcon(props) {
  return icon(props,
    <polyline points="4 8 4 4 8 4" />, <polyline points="16 8 16 4 12 4" />,
    <polyline points="4 12 4 16 8 16" />, <polyline points="16 12 16 16 12 16" />
  )
}

export function FullscreenIcon(props) {
  return icon(props,
    <polyline points="4 7 4 4 7 4" />, <polyline points="16 7 16 4 13 4" />,
    <polyline points="4 13 4 16 7 16" />, <polyline points="16 13 16 16 13 16" />
  )
}

export function ExitFullscreenIcon(props) {
  return icon(props,
    <polyline points="7 4 7 7 4 7" />, <polyline points="13 4 13 7 16 7" />,
    <polyline points="7 16 7 13 4 13" />, <polyline points="13 16 13 13 16 13" />
  )
}

export function ExportIcon(props) {
  return icon(props,
    <path d="M4 13v2a2 2 0 002 2h8a2 2 0 002-2v-2" />,
    <polyline points="7 8 10 11 13 8" />, <line x1="10" y1="3" x2="10" y2="11" />
  )
}

export function MoreIcon(props) {
  return icon({ ...props, strokeWidth: 0, fill: 'currentColor' },
    <circle cx="4" cy="10" r="1.5" />, <circle cx="10" cy="10" r="1.5" />, <circle cx="16" cy="10" r="1.5" />
  )
}

export function CloseIcon(props) {
  return icon(props, <line x1="5" y1="5" x2="15" y2="15" />, <line x1="15" y1="5" x2="5" y2="15" />)
}

export function ExternalLinkIcon(props) {
  return icon(props,
    <path d="M11 3h6v6" />, <line x1="17" y1="3" x2="9" y2="11" />,
    <path d="M14 11v4a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h4" />
  )
}

export function ZoomInIcon(props) {
  return icon(props, <line x1="10" y1="5" x2="10" y2="15" />, <line x1="5" y1="10" x2="15" y2="10" />)
}

export function ZoomOutIcon(props) {
  return icon(props, <line x1="5" y1="10" x2="15" y2="10" />)
}

export function ChevronDownIcon(props) {
  return icon({ ...props, width: 16, height: 16, viewBox: '0 0 16 16' },
    <polyline points="4 6 8 10 12 6" />
  )
}

export function ChevronUpIcon(props) {
  return icon({ ...props, width: 16, height: 16, viewBox: '0 0 16 16' },
    <polyline points="4 10 8 6 12 10" />
  )
}

export function RefreshIcon(props) {
  return icon(props,
    <path d="M3 10a7 7 0 0113.6-2.3" />, <polyline points="17 3 17 8 12 8" />,
    <path d="M17 10a7 7 0 01-13.6 2.3" />, <polyline points="3 17 3 12 8 12" />
  )
}

export function TableIcon(props) {
  return icon(props,
    <rect x="3" y="3" width="14" height="14" rx="2" />,
    <line x1="3" y1="8" x2="17" y2="8" />, <line x1="3" y1="13" x2="17" y2="13" />,
    <line x1="8" y1="3" x2="8" y2="17" />
  )
}

export function DiagnosticsIcon(props) {
  return icon(props,
    <path d="M10 2l8 16H2L10 2z" />,
    <line x1="10" y1="8" x2="10" y2="11" />,
    <circle cx="10" cy="13.5" r="0.5" fill="currentColor" stroke="none" />
  )
}

export function FileIcon(props) {
  return icon(props,
    <path d="M5 3h7l4 4v10a1 1 0 01-1 1H5a1 1 0 01-1-1V4a1 1 0 011-1z" />,
    <polyline points="12 3 12 7 16 7" />
  )
}
