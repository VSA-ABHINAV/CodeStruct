# ADR-004: Background-job execution model

- **Status:** Accepted for MVP target
- **Date:** 2026-09-12

## Context

Analysis includes filesystem I/O, CPU-bound AST/resolution/metrics, progress,
cancellation, memory/time limits, and crash handling. Running it in a FastAPI
handler or an in-process asyncio task cannot isolate CPU or terminate runaway work.

## Decision

Use async FastAPI handlers and an application coordinator, plus a configured
bounded launcher that creates one fresh `multiprocessing` spawn worker per active
analysis. A semaphore bounds active/queued jobs. Workers receive only an
authorized project capability and immutable policy, publish bounded progress via
IPC, check cancellation cooperatively, and are terminated after timeout/grace.
Persist lifecycle/revisions in SQLite. On application restart, mark nonterminal
jobs failed; automatic resumption is deferred.

## Alternatives considered

- Threads: easy shared progress, but GIL limits CPU and a runaway thread cannot be
  safely killed or memory-isolated.
- Asyncio tasks only: appropriate for coordination, not CPU/static analysis.
- `ProcessPoolExecutor`: pooling is efficient but individual hard cancellation,
  per-job resource accounting, and contaminated-worker recovery are weaker.
- Celery/external queue: distributed durability exceeds local MVP needs.

## Reasons

Spawned processes work consistently on Windows/macOS/Linux only after packaging
is corrected, isolate failures, permit hard termination, and keep the API
responsive. One job per worker gives clear ownership at acceptable MVP scale.

## Consequences and risks

IPC/progress and cross-platform spawn add complexity and startup overhead.
Cancellation is checkpoint-based, not instantaneous. Process termination may lose
uncommitted work; transactions preserve prior valid results. Concurrency defaults
must come from Phase 10 resource benchmarks.

## Reconsider when

Startup cost dominates small analyses, resumable/distributed jobs are required,
or process sandbox requirements change. Threads may serve strictly bounded I/O
inside a worker, but cannot replace the worker isolation boundary without an ADR.

