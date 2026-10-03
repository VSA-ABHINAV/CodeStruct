# ADR-001: Python parser strategy

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

CodeStruct must deterministically extract scoped Python syntax and exact locations
without executing source. The current analyzer already uses `ast`, while the MVP
supports Python source rather than error-tolerant live editing.

## Decision

Use the standard-library `ast` module behind `ParserAdapter`. Support regular
`.py` files and configured grammar versions 3.10–3.14 only when the running
interpreter can parse that version. Record exact runtime/grammar in metadata and
cache keys. Parse one bounded file at a time in a spawned worker; preserve raw
syntax observations, lexical scope, aliases, async/method/nested kinds, and source
spans. Convert syntax/encoding errors into per-file diagnostics. Never import,
execute, compile for execution, evaluate, or invoke project code.

## Alternatives considered

- Tree-sitter: error-tolerant, cross-version parsing and incremental syntax.
- LibCST: richer concrete syntax and rewriting support.
- Executing/importing modules: rejected categorically for security and semantic
  nondeterminism.

## Reasons

`ast` is dependency-free, mature, exposes required constructs/locations, and is
adequate for batch static analysis. Tree-sitter adds native grammar/version and
query maintenance without an approved error-recovery requirement; LibCST solves
format-preserving transformation that MVP does not need.

## Consequences and risks

Malformed files yield diagnostics rather than partial trees. Syntax newer than the
runtime cannot be parsed, comments/formatting are mostly absent, and AST changes
across CPython can alter results; runtime and analyzer versioning plus fixtures
make this explicit. Parser adapters remain replaceable without changing domain or
API semantics.

## Reconsider when

Requirements add live incomplete-code analysis, source rewriting, syntax newer
than the shipped runtime, non-Python languages, or benchmarks show `ast` cannot
meet supported scale. A replacement must pass the same adapter/evidence contract.

