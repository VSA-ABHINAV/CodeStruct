# Antigravity task: Milestone 6 — Grounded semantic explanations

Date: 2026-10-12. Repository: `D:\REP\Codestruct\Codestruct`.

M5 is considered complete based on the user's instruction to rely on Antigravity's report; see `docs/verification/M5_REPORT_ACCEPTED.md` and `docs/verification/M5.md`. This is not a direct Codex source-code review. Read the CodeStruct technology summary at `D:\REP\# CodeStruct – Technology Summary.txt`, `docs/codestruct_audit.md` (CS-016), `PROCESS_TRACKER.md`, and the existing explanation/provider/API implementation. Implement only **M6 / CS-016**. Do not begin M7 or M8, and do not redesign the frontend.

## Required outcomes

1. Add a bounded retrieval layer that assembles relevant authorized source snippets, canonical graph relationships, runtime observations when available, metrics, and evidence identifiers for the requested explanation. Enforce file/count/byte or token limits and project-root containment; never include secrets or unrelated project files.
2. Validate provider output with strict Pydantic models rather than permissive dictionary `.get()` parsing. Validate all evidence references against the retrieved canonical evidence set. Distinguish observed facts from interpretations and label model-derived claims as `LLM_INFERRED`; do not present an inference as a direct static/runtime fact.
3. Keep semantic generation optional and explicitly selected by the user/provider configuration. Preserve a deterministic offline/rule-based fallback when the provider is disabled, unavailable, times out, or returns invalid data. Do not make paid or remote provider calls in tests; use injected fake providers.
4. Return truthful provider, inference, evidence, and fallback metadata through the API. Update schemas, documentation, fixtures, and UI integration only as required by the contract; no visual redesign.
5. Add deterministic tests for bounded retrieval and path containment, canonical source/graph/runtime/metric evidence, malformed or unsupported provider output, invalid/unknown evidence IDs, provider timeout/failure, opt-in behavior, offline fallback, and inference labeling. Ensure static analysis itself never invokes a semantic provider.

## Run-to-completion, verification, and report

Keep working within CS-016 until all required behavior is implemented and the verification matrix passes. On a failure, fix it, rerun the focused check, then rerun affected and full gates; do not return a partial result. Run full backend coverage (at least 84%), focused explanation/retrieval/API tests, Thonny plugin tests, frontend tests/lint/build if affected, Ruff check/format, mypy, compilation, and `git diff --check`. Exercise the real backend/API with an injected deterministic provider and with provider disabled/failing; record request, retrieved evidence, validated output, inference labels, fallback, and bounded limits in `docs/verification/M6.md`.

Make the report identify the exact tested code commit and report commit. Any later implementation/test/dependency/configuration commit invalidates earlier gate results and requires rerunning them. Update `PROCESS_TRACKER.md` and `docs/codestruct_audit.md` only to match actual evidence. Commit non-empty M6 changes only after gates pass, then stop and report **Ready for review**. Do not begin M7.

## M6 file cleanup after verification

Inventory files created during this phase and search references before removal. Delete only M6-created scratch files, temporary databases/logs, or redundant artifacts proven unused and unnecessary for reproducibility. Preserve source, tests, fixtures, required scripts, `docs/verification/M6.md`, historical review/acceptance records, audit/tracker files, and all pre-existing or user/project data. Avoid broad cleanup or reset commands. Record removals and verify the final test state and `git status`.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md, docs/verification/M5_REPORT_ACCEPTED.md, docs/verification/M5.md, docs/codestruct_audit.md, PROCESS_TRACKER.md, and the CodeStruct technology summary. Implement only M6 / CS-016: build bounded authorized source+graph+runtime+metric retrieval; strictly validate provider output and evidence references; label inferred claims as LLM_INFERRED; keep provider use explicitly opt-in with a deterministic offline/failure fallback; and add local fake-provider regressions without paid/remote test calls. Continue fixing and rerunning checks until the full required matrix and real backend/API paths pass. Record exact code/report commits, commands, evidence, and cleanup in docs/verification/M6.md; update PROCESS_TRACKER.md and the audit to match; remove only M6-created files proven unused while preserving project data and historical evidence. Commit non-empty phase changes after all gates pass, then stop and report Ready for review. Do not begin M7.</span>
