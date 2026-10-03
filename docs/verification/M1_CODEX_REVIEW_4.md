# Codex M1 review — correction pass 3

Date: 2026-09-27. **Implementation checks pass; contract handoff corrections still required. M1 is not fully Accepted.**

## Independently verified

- 155 backend tests passed, 1 platform skip, coverage 84.60% (84% gate met).
- 49 plugin tests passed, 1 platform skip.
- 93 frontend tests passed including all four real-hook StrictMode startup regressions. Coverage: 72.86% statements, 65.32% branches, 74.43% functions, 75.47% lines; all configured gates met.
- Ruff lint, mypy (50 files), and formatter check pass. Formatter check passes before AND after plugin tests; temporary fixture isolation works.
- Startup reads immutable initial handoff and survives effect replay while credentials are scrubbed. Previously implemented navigation security/session/poller fixes are not reopened.
- Initial sandbox runs encountered Windows SQLite/fixture permissions; approved outside-sandbox reruns produced the results above. Environmental errors are not reported as application failures.
- Real desktop cursor observation remains pending, not falsely verified. No new production code was changed during this review.

## Remaining contract mismatches — CS-004/023 only

1. **Create request is guaranteed to fail.** Brief section 5.2 sends `options.source_grammar="3.12"` and `metrics=true`. Current route rejects both with HTTP 400 `OPTION_UNSUPPORTED`. Use supported `{ "project": { "root_id": "sample_service", "relative_path": "." }, "refresh": false }`, or `options: { "metrics": false }` with optional grammar unset. Mark these advanced option controls unavailable until M2, instead of pretending supported. Do not implement M2 options during this pass.
2. **Job fixture still invents nested summary keys.** `analysis_job.json` contains total_files/total_nodes/total_edges; route embeds the canonical graph summary with source_units_total/nodes_total/edges_total and its other fields. Current strengthened test merely checks summary is a dictionary, so this mismatch passes. Generate an actual completed JobResponse or compare every nested summary key against serializer-generated graph, preserving harmless deterministic ID/time substitutions.
3. **Diagnostics fixture still uses wrong source keys.** `diagnostics.json` items use file_path/line rather than canonical GraphDiagnostic location and fields. DTO items are flexible dicts, so outer validation does not prove compatibility. Generate a real parse-warning/error diagnostic via safe static fixture and route retrieval, then validate location and node/edge association fields through the frontend normalization adapter.
4. **Error example is not the actual envelope.** Brief uses error.details; real errors include field_errors, safe_context and retry_after_seconds. Generate envelope from TestClient unknown ID/invalid request. Do not invent status codes or error details.
5. **Nonterminal example exposes a graph link before it exists.** `_job` sets links.graph=null until a usable completed/partial result. Brief submitted-response example returns a graph URL. Generate true submit/status response, label illustrative times/IDs, and verify link availability.
6. **Document exact cancellation/paging behavior.** Cancel already-cancelled job is idempotent, not universally 409 for every terminal state. Omitting graph limit uses the full-result byte cap, not max_graph_page_size; the latter caps an explicit page request. These must reflect route logic. Hosted preview continues to use labeled fixtures, not local-loopback promises.

## Required evidence

Finish only handoff documents/fixtures/contract tests. Test the actual create JSON from the brief returns 202 in isolated TestClient; invalid options return 400 and are labeled unavailable. Test real nested completed job/diagnostic/error/link/cancel shapes, not generic dict acceptance or hard-coded fixture-only assertions. No renderer, metrics, runtime or other product implementation changes required. Run affected backend/frontend fixture suites plus full checks justified by changes, then add M1_CORRECTIONS_4.md.

Remaining manual desktop gate is separately pending. These documents can be corrected without GUI access. Do not redo working startup or navigation implementation. Stop for review before M2.
