# ADR-008: API framework and serialization

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

The project already uses FastAPI. MVP needs strict request/response validation,
OpenAPI, typed errors, pagination, background job resources, and independently
versioned graph serialization without coupling the domain to transport.

## Decision

Retain FastAPI and use Pydantic models only in the API adapter.
Map explicitly between frozen domain dataclasses and DTOs. Use standard UTF-8
JSON with snake_case, canonical serialization for fingerprints, HTTP ETags, and
explicit API and graph SemVer fields. Use Uvicorn for the local loopback process.

## Alternatives considered

- Flask plus manual schemas: smaller core but recreates validation/OpenAPI.
- Django/DRF: capable but excessive persistence/application surface.
- MessagePack/Protobuf: compact/typed but adds browser tooling and makes local
  inspection harder before performance evidence.
- Pydantic domain objects: reduces mapping but contaminates core semantics with
  transport validation and serialization lifecycle.

## Reasons

This retains proven repository dependencies and gives contract validation with
minimal framework change. Ordinary JSON is interoperable, debuggable, and adequate
under response caps and pagination.

## Consequences and risks

Mapping code and contract fixtures are mandatory. JSON can be verbose; page and
response-byte caps manage it. FastAPI/Pydantic version changes can alter OpenAPI or
coercion, so compatible ranges and snapshots must be tested. Strict models must
still allow documented additive response evolution in clients.

## Reconsider when

Benchmarks prove JSON serialization dominant, external clients require a formal
binary IDL, or the application moves beyond local HTTP. Domain independence and
version semantics remain mandatory.
