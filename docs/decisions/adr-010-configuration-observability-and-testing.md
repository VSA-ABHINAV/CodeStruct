# ADR-010: Configuration, observability, and test tooling

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

Security policy must be immutable and fingerprinted, logs must be useful without
leaking source/path data, and the architecture needs enforceable unit, contract,
security, integration, frontend, accessibility, packaging, and performance gates.

## Decision

Load built-in secure defaults, then an explicit trusted per-user/admin TOML file
using `tomllib`, then a narrow allowlist of environment overrides for deployment
values; validate into an immutable dataclass and fail closed. Request options may
only narrow the effective policy. Use Python stdlib `logging` with a small JSON
formatter and central redaction filter; emit request/job IDs, phase, duration,
counts, limit codes, and terminal state, never source, secret values, or protected
absolute paths.

Keep pytest, pytest-cov, Ruff, and mypy for Python; ESLint and Vite checks for the
frontend. Add standard-library/unittest-compatible domain fixtures, API/OpenAPI
snapshots, import-boundary tests, fault/security/property-style parameterized
cases, Vitest with React Testing Library, `user-event`, `jest-dom`, and `axe-core`
for reducer/component/accessibility tests, Playwright for the ten browser journeys,
manual WCAG procedures, wheel smoke tests, and Phase 10 benchmark harnesses. Exact
versions are selected and locked during implementation after license/maintenance
review. Existing pending Phase 2 tools must actually run before a release gate is
claimed.

## Alternatives considered

- `pydantic-settings`: convenient but another dependency when TOML/env needs are
  small and policy belongs outside API DTOs.
- YAML: flexible but another parser and unsafe-loading concern.
- Third-party structured logging/APM: richer but unnecessary and potentially
  conflicts with local-data privacy.
- One end-to-end suite only: misses component/security boundaries and is slow.
- Ad hoc manual testing only: cannot enforce determinism or compatibility.

## Reasons

Standard-library configuration/logging minimizes dependencies and permits explicit
redaction. Existing quality tools match repository intent; layered tests align with
ports and isolate failures while acceptance tests prove journeys.

## Consequences and risks

Custom JSON formatting/redaction requires tests and stable event names. Environment
configuration can leak or drift, so only named non-secret keys are accepted and
effective policy digests exclude values that reveal paths. More test layers add
maintenance cost; shared fixtures and requirement IDs prevent duplication.

## Reconsider when

Configuration becomes remotely managed or secret-bearing, observability must join
an approved external platform, multiple processes require richer log transport,
or test scale justifies specialized property/contract tooling. Privacy and fail-
closed policy remain prerequisites.
