# ADR-002: Graph domain model and NetworkX boundary

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

Graph records require stable IDs, evidence, partial results, serialization, and
frontend independence. NetworkX is useful for metrics but its mutable graph and
attribute dictionaries are not a durable product contract.

## Decision

Use frozen, slotted Python dataclasses and enums for canonical domain nodes,
edges, evidence, locations, diagnostics, and metadata. The model is edge-centric.
Use Pydantic only for API DTOs. Implement `GraphAlgorithmPort` with a transient
NetworkX adapter that projects bounded domain slices, computes approved metrics,
and returns typed results without leaking NetworkX objects.

## Alternatives considered

- Pydantic as the domain model: convenient validation but couples core semantics
  to transport/runtime behavior.
- NetworkX as canonical storage: convenient algorithms but mutable, unversioned,
  and unsuitable as persistent/API schema.
- Custom algorithms only: fewer dependencies but needless risk for established
  graph operations.
- Graph database: operationally excessive and explicitly outside MVP.

## Reasons

Dataclasses keep parsing/resolution testable and framework-neutral. An adapter
captures NetworkX value while allowing limits, replacement, and deterministic
conversion. API and UI can evolve without corrupting semantic ownership.

## Consequences and risks

Explicit DTO/storage mapping is required. Full projection can duplicate memory,
so algorithms operate on capped slices and may return a limit diagnostic. Some
NetworkX algorithms/orderings need canonical input and output sorting.

## Reconsider when

Approved metrics exceed NetworkX performance at benchmark scale, persistence
requires a different query engine, or another language consumes the domain
in-process. Any change preserves the graph schema and evidence semantics.

