# ADR-003: Visualization library strategy

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

The prototype already uses React Flow. MVP needs bounded interactive graphs,
selection, pan/zoom/fit/reset, a text equivalent, and large-result controls; no
measurement currently justifies migration.

## Decision

Retain `@xyflow/react` for the MVP renderer. A pure renderer-independent adapter
produces generic visual records; React Flow owns only canvas rendering and input
events. Keep the table/text view equally capable. Use `@dagrejs/dagre` for
deterministic layered layout behind a replaceable layout port in a Web Worker,
with aggregation and hard render caps before layout. Its exact version is locked
during implementation after license and maintenance verification.

## Alternatives considered

- Cytoscape.js: stronger built-in graph algorithms but migration cost without
  measured need and explicitly outside MVP.
- D3/custom canvas/WebGL: flexible but much larger accessibility/interaction burden.
- Fixed grid: current behavior is deterministic but inadequate for relationships.

## Reasons

React Flow is already integrated and supports the required interaction base. The
adapter prevents library types from becoming contract types. Worker layout and
bounded slices protect responsiveness; the table protects accessibility.

## Consequences and risks

Large dense graphs still require aggregation. React Flow accessibility must be
supplemented by application controls/table semantics. Dagre may not suit cyclic or
compound graphs; layout output is presentation state and never persisted as graph
truth.

## Reconsider when

Phase 10 render/layout benchmarks miss approved budgets after aggregation, user
testing identifies navigation blockers, or required compound graph behavior is
not feasible. Compare alternatives with the same adapter fixtures before migration.
