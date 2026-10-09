# Antigravity task: Milestone 5 — Runtime tracing and graph merge

Date: 2026-10-09. Repository: `D:\REP\Codestruct\Codestruct`.

M4 was accepted in `docs/verification/M4_CODEX_REVIEW_13_ACCEPTED.md`. Read that review, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, the technology summary at `D:\REP\# CodeStruct – Technology Summary.txt`, and the existing runtime tracer, merger, API/job pipeline, storage, and tests before changing code. Implement only **CS-012, CS-013, and CS-014 (M5)**. Do not redesign the frontend or begin M6/M7/M8.

## Required outcomes

1. Add an explicit, opt-in, user-selected runtime analysis session to the normal job/API pipeline. Static analysis must never execute analyzed source. Bound execution time, output/event volume, and target selection; make cancellation and failures terminal and diagnosable. Persist run-specific results separately from static cache identity and expose a unified graph retrieval path with run provenance and coverage/overhead metadata.
2. Correct runtime event attribution: use canonical source identity and qualified symbols; retain ambiguity rather than choosing the first suffix/name match; support recursive calls. Capture per-event timing and thread identity for the supported thread model, restore prior profiling hooks on every exit, and define/test exception, generator, and async behavior. Do not claim unsupported thread coverage.
3. Define repeat-run aggregation semantics. Recompute derived graph metrics after merging new runtime edges, preserve static/runtime origins, avoid double counting, and keep runtime attributes in the graph shape consumed by explanations and API serializers.
4. Add meaningful regression tests for explicit opt-in versus static-only execution, execution bounds/cancellation, same-name definitions and ambiguity, recursion, exceptions, repeated sessions, metric recomputation, and provenance. Keep tests local and deterministic; do not execute user projects as part of ordinary static analysis.
5. Update API/technology documentation and fixtures only where the implementation changes the contract. Keep all frontend work limited to the integration needed to expose the existing product capability; no visual redesign.

## Verification and stop condition

Run focused tracer/merger/API/storage tests, full backend coverage gate, Thonny plugin tests, frontend tests/lint/build if affected, Ruff check/format, mypy, and `git diff --check`. Exercise an explicit runtime session through the real backend/API and record the source project, execution opt-in, bounded outcome, persisted run identity, unified graph provenance, and measured overhead. Update `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and `docs/verification/M5.md`; preserve earlier review evidence. Commit the completed phase and verify the repository state. Stop for Codex review. Do not begin M6.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md, docs/verification/M4_CODEX_REVIEW_13_ACCEPTED.md, PROCESS_TRACKER.md, docs/codestruct_audit.md, and the CodeStruct technology summary. Implement only M5 issues CS-012, CS-013, and CS-014: integrate explicit bounded opt-in runtime analysis into the normal pipeline while preserving static-only non-execution, correct source/symbol attribution and recursion with defined hook/thread/exception/generator/async behavior, and merge repeated runs with fresh metrics and truthful provenance. Add focused deterministic regressions, run all required gates and a real backend/API runtime-session workflow, record evidence in docs/verification/M5.md and PROCESS_TRACKER.md, update the audit, commit the phase, then stop for Codex review. Preserve the completed Lovable frontend; no redesign. Do not begin M6.</span>
