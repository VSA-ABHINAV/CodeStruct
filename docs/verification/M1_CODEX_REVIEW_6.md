# Milestone 1: Codex review 6

Date: 2026-09-28. Decision: contract corrections accepted; M1 automated implementation review complete. Full M1 acceptance awaits the real Thonny workflow evidence required in `M1_original_task.md`.

## Independently verified

- Backend contract/navigation/editor suites: 50 passed, one dependency deprecation warning. Command: `.venv\Scripts\python.exe -m pytest tests/test_contract_fixtures.py tests/test_navigate_routes.py tests/test_editor_integration.py --no-cov -p no:cacheprovider -q`.
- Frontend contract + real-hook StrictMode tests: 11 passed, 2 files. Command: `npm.cmd test -- --reporter=dot src/api/contractFixtures.test.js src/App.strictReview.test.jsx` (outside sandbox).
- Existing `M1_review5_contract_probe.py`: 4194304-byte default, documented cursor decodes to offset 1, parser project generates five null-location diagnostics. Passed outside sandbox with isolated temporary static fixture; source is never executed.
- Ruff check: passed; Ruff format: 87 files already formatted; mypy: 50 source files passed. Checked backend/tests/sample_project/thonny-plugin targets using the documented commands.

The actual markdown pagination JSON now matches generated nodes, edges and page fields and its cursor can be followed against the matching toy graph/filter context. Nullable location guarantees are corrected and tested. Summary claims accurately distinguish schema shape from toy values. No further contract corrections requested.

Current full frontend suite (94 tests), build/lint and prior full backend/plugin coverage evidence are Antigravity-reported or from earlier Codex reviews; not repeated here. This review does not establish new live browser geometry or desktop cursor evidence.

## Only remaining M1 gate

Original M1 task explicitly required real backend/browser/Thonny selected-file analysis, Open in editor, observed path/cursor, duplicate filenames in two roots, safe navigation failure and cleanup. `M1.md` reports widget-call/index assertions and explicitly admits headless limitations. Later passes preserve a pending desktop gate. These are useful automated checks, but do not establish that the live editor opened the intended file and moved its actual cursor after the latest fixes.

Provide a short real application smoke record. Actual live editor `insert` index and active editor filename observations are acceptable evidence; a blinking-cursor recording or physical mouse click is not independently required. Use a running real Thonny workbench and real browser/API path, not a mocked editor object. Redact tokens. If GUI tools are unavailable, record the exact blocker and a concrete operator checklist. Do not fabricate success, rewrite working code or rerun full suites merely to repeat the same limitation.

CS-001/003/004 implementation and contract gates accepted; CS-002 retains a real-workflow Verification gap. CS-023/026 acceptance covers the M1 documentation/contract portion only; their later milestone work remains open. M2 remains Not started under the existing dependency gate. Lovable contract is now approved as design input, with static preview and planned capability labels preserved.
