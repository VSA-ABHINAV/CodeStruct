# Milestone 5 Codex Review 1 — Changes Required

**Date:** 2026-10-09  
**Reviewed commit:** `1325bb3453214ae2f1472e676ebc1c461da5a962`  
**Decision:** M5 is not accepted. Do not begin M6.

The submitted static and focused tests pass, and the real API smoke creates two persisted runtime sessions, merges runtime evidence, and rejects a target path outside the project. Independent verification also reproduced three unresolved M5 correctness gaps.

## Findings

1. **CS-012 — Runtime timeout is not an execution bound and has no cancellation path.** In `backend/src/codestruct/analysis/dynamic_tracer.py`, `trace_project_target()` runs analyzed code in a daemon thread and only calls `join(timeout=...)`. If it remains alive, the caller reports a timeout and returns, but the thread continues executing. Independent probe: a target with a 0.6-second delay returned a timeout after 0.11 seconds for a 0.1-second limit and still wrote its post-timeout marker (`continued=True`). The helper also changes process-global `sys.argv` and `sys.path` while the thread is running, then restores them while target code may still use them. Target stdout/stderr are not captured or capped, so opted-in code can emit unbounded data into backend output. Move target execution to a killable isolated process, enforce timeout/event/output bounds there, restore state by process exit, and define how an in-flight runtime session is cancelled and recorded as terminal. Add a regression proving no target side effect occurs after timeout/cancellation.

2. **CS-013/CS-014 — Ambiguous attribution still chooses the first candidate.** The `find_node()` helper in `dynamic_tracer.py` returns `matching_candidates[0]` when several candidates remain after line matching, while marking the edge `AMBIGUOUS` and attaching candidate IDs. The graph therefore still attaches runtime invocation statistics and the edge target to an arbitrary symbol. Preserve candidate ambiguity without assigning counts or a canonical target to one candidate; add a regression that checks node-level stats and edge target semantics when two candidates remain.

3. **CS-013 — Event duration and instrumentation overhead are unmeasured placeholders.** `RuntimeCallEvent.duration_seconds` and `RuntimeTraceResult.overhead_seconds` default to `0.0`; the tracer never supplies measured values. The live verification output reported `overhead_seconds: 0.0` for both sessions, so it does not provide the requested overhead evidence. Implement and document a defensible timing/overhead measurement, or remove/rename unavailable metrics and update the API/report claims. Add tests that verify non-placeholder measurements and honest behavior when measurement is unavailable.

## Independent verification

- Full backend suite: 196 passed, 1 skipped; coverage 84.79% (gate 84%).
- Focused tracer/API suite: 19 passed.
- Thonny plugin suite: 53 passed, 1 skipped.
- Frontend: 104 passed; lint and production build passed.
- Ruff check/format, mypy, and compilation/whitespace checks passed.
- Real M5 API verification passed with two sessions and graph merge, but reported `overhead_seconds: 0.0`; this does not resolve Finding 3.
- Timeout probe returned at 0.11 seconds with the configured 0.1-second timeout and confirmed the target wrote a marker afterward.

Update `ANTIGRAVITY_TASK.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and `docs/verification/M5.md` to reflect these findings and the next correction pass. Preserve M1–M4 evidence and do not begin M6.
