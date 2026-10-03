# Codex review — M1 correction submission

2026-09-26. **Changes required; M1 not Accepted.** Source corrections are present, but several requested fixes were omitted. Do not start M2 or hand the brief to Lovable yet.

## Independently confirmed improvements

Isolated real Windows probes now show distinct same-file registration tokens, hostile Origin rejected (403), expired acknowledgement rejected (`command_expired`), and retargeted directory junction POST rejected (403), with no pending delivery. Current graph fixture normalization now preserves coordinates and evidence origin/location. These parts of R1/R2/R3/R5 improved; do not reimplement them.

81 navigation/editor/plugin tests pass. Bare mypy (50 files) and Ruff lint pass. Full formatter check still fails: 6 files would be reformatted, 69 already formatted. No fresh full backend/frontend/coverage/build rerun was needed to establish the remaining source-level blockers; original reported results are not newly independently verified here.

## Remaining blockers

1. **R1/R2 plugin behavior is not implemented.** `_nav_poll_generation` is declared only, never incremented or used. `_nav_registered_file_resolved` is stored but never checked in `_execute_navigate`. `_start_navigation_polling` still returns when active; recursive callback retains old token. Plugin still resolves before `resolved.is_symlink()`. Implement A->B generation-safe switching, stale callback rejection and real plugin-side original component/identity checks. Regression tests must exercise those paths; existing 44 plugin tests did not grow.
2. **R4 was omitted entirely.** `App.jsx` is unchanged: immutable captured token, no initial credential scrub, old token survives project change, console-only navigation failure. Implement analysis-associated token clearing/rebinding and safe visible feedback with regression tests and coverage.
3. **R3 brief corrections cannot be deferred to M3.** They were explicitly M1 deliverables in original and correction tasks. Brief remains unchanged: current renderer wrongly called Cytoscape, nonexistent POST explanation route, wrong JobState values and unsupported performance claims. Complete all original required contract/preview/accessibility/cancel/cache/export/error details. Graph fixture's page remains manually composed, not proof of actual paginated API shape. Validate all fixtures against actual API and frontend normalization through permanent tests.
4. **R5 plugin outcome/privacy remains unchanged.** File-open-only fallback claims delivered without cursor placement; raw `str(nav_exc)` is sent as failure reason. Fix truthful delivery/failure codes and browser outcome visibility. Backend probe improvements do not cover these client behaviors.
5. **R6 CI/format/coverage/evidence remains incomplete.** CI and docs still omit plugin test/lint commands. Full format failures: tests/test_dynamic_tracer.py, test_export_dot.py, test_graph_metrics.py, test_llm_summary.py, test_python_parser.py, test_type_stubs.py. Format-only remediation is already authorized by correction scope; no semantic changes or gate weakening. Add new regression/fixture tests, ensure mypy config parity/authority, report frontend coverage, and retain real GUI gate as explicitly pending until observed. Tracker's 'all gates green' conflicts with actual full required check.

## Required handoff

Finish remaining behaviors, not merely add globals, rename statuses or mark explicit M1 tasks out of scope. Preserve `M1_CORRECTIONS.md` as submitted evidence; append the next pass results to it or create `M1_CORRECTIONS_2.md`. Keep original reports immutable in meaning. Current task is narrowed to these remaining requirements. Stop for review without beginning M2.
