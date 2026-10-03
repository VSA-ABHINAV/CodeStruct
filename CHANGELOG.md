# Changelog

## Unreleased

### Added

- A `0.1.0.dev0` package version shared by CLI, API, and bundled frontend.
- `codestruct serve`, `codestruct doctor`, liveness/readiness, and version endpoints.
- Reproducible local wheel/sdist tooling, artifact checksums, container examples,
  and inactive review-only release automation.
- Safe configured-project discovery through `GET /api/v1/projects`.
- Keyboard-accessible project selection and incremental bounded graph loading.
- User, developer, API, configuration, operations, security, and contributor guidance.
- Trusted loopback active Python file analysis for Thonny (`/api/v1/editor/selection`) with single-file scoping and capability-bound execution without demo fallback.
- Redesigned 7-section collapsible Entity Details panel with humanized enums, detailed relationship cards, copy controls, and pagination integration.

### Changed

- Graph retrieval starts with a bounded page and loads more only on request.
- Dense-graph warnings activate at 80 nodes or 240 edges.
- Graph retrieval has a distinct announced state and the page title names CodeStruct.
- Non-JSON server failures are reported as backend unavailability.
- Entity Details presentation restructured into 7 clearly separated, collapsible sections with independent scrolling and responsive desktop/mobile layouts.

### Security

- Duplicate aliases and canonical authorized-root locations are rejected.
- Project discovery never exposes canonical server paths.
- Editor file registration is restricted to loopback clients with strict single-file scope, denying directory traversal, symlinks, and absolute path exposure.

### Known limitations

- Client virtualization and advanced aggregation remain future work.
- macOS/Linux, real screen readers, browser zoom, and full fault injection remain pending.
