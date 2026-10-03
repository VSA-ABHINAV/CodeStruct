# ADR-006: API versioning and compatibility

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

The current unversioned synchronous `GET /analyze` returns unvalidated legacy
dictionaries and the frontend depends on them. MVP needs jobs, partial results,
diagnostics, pagination, safe path selection, and explicit schema evolution.

## Decision

Introduce resource-oriented `/api/v1` endpoints with strict Pydantic DTOs,
OpenAPI, a common error envelope, explicit graph `schema_version`, opaque cursors,
and additive minor evolution. Retain `GET /analyze` temporarily as a frozen
legacy projection or old implementation. The frontend uses a dedicated v1 client;
breaking changes require `/api/v2`. Removal follows documented deprecation and
exit gates, not a date guessed in Phase 5.

## Alternatives considered

- Replace `/analyze` in place: simplest routing but silently breaks the current UI.
- Header-only versioning: less visible and harder to debug/cache locally.
- GraphQL: flexible selection but unnecessary schema/query/security complexity.
- WebSockets/SSE: useful progress transport but bounded polling/long-poll is enough
  for MVP.

## Reasons

Path versioning is explicit and testable. Pydantic gives validation/OpenAPI while
domain models stay independent. Side-by-side compatibility enables incremental
frontend migration and focused rollback.

## Consequences and risks

Two endpoints exist temporarily and require contract tests. DTO/domain/legacy
mapping adds code. Long polling may be less efficient than streaming but is
bounded. Tolerant readers must handle additive enum/field growth safely.

## Reconsider when

Measured polling load warrants SSE, an external supported client ecosystem needs
generated SDK governance, or legacy exit criteria are satisfied. Remote exposure
requires a separate authenticated API profile and threat model.

