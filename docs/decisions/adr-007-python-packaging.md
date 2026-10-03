# ADR-007: Python packaging and module layout

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

Current modules are un-packaged, use `from analyzer import ...`, and depend on the
backend working directory. The frontend is separately served in development, but
the local product should start reliably from any directory.

## Decision

Keep setuptools and move production Python into `src/codestruct/` packages with
absolute imports, typed public ports, package data, and a `codestruct` console
script. Continue supporting CPython 3.10–3.14 as current metadata states; test the
minimum and maximum, and record exact runtime in results. Locate mutable data with
platform user-data APIs, never relative to CWD.

Keep `frontend/` as a Vite workspace during development. The release build copies
hashed static assets into `codestruct/web/` as package data and FastAPI serves them
same-origin on loopback. Build the frontend before the wheel in release automation;
source distributions document Node requirements. Shared JSON Schema lives in a
versioned repository directory; generated frontend types/client are justified only
if reproducible generation and drift checks are added. Reserve a separate future
adapter package/entry point for Thonny; it may call application/API ports only.

## Alternatives considered

- Keep flat modules: preserves prototype but cannot provide CWD-independent imports.
- Poetry/Hatch/PDM migration: useful workflows but no requirement justifies changing
  the configured backend now.
- Separate deployed frontend server: useful for remote hosting, unnecessary and
  riskier CORS for local MVP.
- Electron/native wrapper: excessive packaging surface.

## Reasons

The standard `src` layout prevents accidental repository-root imports, supports
clean wheels and spawned processes, and minimizes build-tool change. Bundling the
frontend yields one local install and same-origin security while retaining fast
Vite development.

## Consequences and risks

Migration needs legacy import shims/entry points and wheel/sdist tests. Supporting
five Python minors increases CI/parser fixtures. Frontend asset build integration
must be reproducible and must not make editable backend work require Node unless
the UI is being built.

## Reconsider when

Python-version maintenance becomes unsustainable, remote deployment becomes an
approved product, reproducible cross-language generation needs a dedicated build
backend, or native desktop distribution is required.

