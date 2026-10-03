# ADR-009: Frontend state management and layout

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

The current React UI has three local state variables and fixed node positions.
MVP needs a job/UI state machine, stale-request protection, search/filter/slices,
selection parity, progressive expansion, and nonblocking deterministic layout.

## Decision

Use React `useReducer` for the explicit explorer state machine with scoped
contexts for API/session, query, and selection state. Keep immutable server DTOs
separate from derived view state. Use AbortController and monotonic request tokens.
Do not add Redux or a server-state library for MVP. Implement a layout port with
an `@dagrejs/dagre` layered adapter executed in a Web Worker; persist only user
viewport/preferences, never layout as semantic graph data.

## Alternatives considered

- Independent `useState`: insufficient transition/invariant control.
- Redux/Zustand: valuable at larger cross-feature scale but another dependency and
  abstraction before need is measured.
- TanStack Query: mature server cache but overlaps the explicit local job/cache
  lifecycle and does not replace reducer UI states.
- Main-thread/fixed layout: simplest but violates responsiveness/usability goals.
- ELK: stronger compound layout but larger and more complex than current needs.

## Reasons

A reducer is testable against all documented states and is native to installed
React. A worker-based adapter isolates layout cost and can be replaced after
benchmarks. Bounded server slices keep client state comprehensible.

## Consequences and risks

Polling, caching, and reducer effects require disciplined cancellation and tests.
Context overuse can rerender broad subtrees; split selectors/memoization address
measured cases. Worker bundling and `@dagrejs/dagre` licensing/version must be
verified in implementation. Dense/cyclic layouts still need aggregation and table
fallback.

## Reconsider when

State crosses multiple routes/editors, reducer complexity or render profiling
exceeds agreed thresholds, offline mutation appears, or Phase 10 layout evidence
favors another engine. Preserve API client and renderer/layout ports.
