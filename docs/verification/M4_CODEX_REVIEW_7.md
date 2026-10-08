# Milestone 4 Codex Review 7 — Changes Required

Date: 2026-10-07  
Reviewed commit: `83d88ba` (`main`, aligned with `origin/main`)  
Working tree at review start: clean.

## Decision

**Changes required. M4 is not accepted. Do not begin M5.** The Review 6 corrections now pass the independent functional and quality checks, including the real Windows workflow. Two issues remain: production layout is computed twice to support measurement, and the credential scanner can silently skip unreadable files.

## Findings

1. **Avoid duplicate layout computation in the product.** `ArchitectureExplorer.jsx` calculates `layoutGraph(presentation.nodes, presentation.edges)` in `useMemo` for the actual render (`:92`), then calls `layoutGraph` again with the same inputs in `useEffect` solely to measure it (`:96–103`). This adds a second full layout to every graph/presentation update in ordinary app use, including large graph mode. The reported layout time only covers the second call. Keep measurement test-only or use a measurement approach that does not duplicate production layout work; then rerun lint, frontend tests/build, and the smoke benchmark.

2. **Make the secret scan fail closed.** `scan_for_secret_tokens()` catches `PermissionError`/`OSError` while reading profile/temp files and continues (`M4_real_workflow_smoke.py:113–129`). Thus it can report success without inspecting every file. The process cleanup also calls `kill()` after a wait timeout without waiting for termination before scanning (`:1742–1751`), so locked Chrome profile files may be skipped. Require every candidate file to be readable, fail with a non-disclosing filename/error if not, and verify the Chrome process/profile is quiescent before scanning. Do not report zero persisted tokens when any file was not inspected.

## Verification performed by Codex

- Backend coverage suite: **189 passed, 1 skipped, 85.49% coverage** (outside sandbox after prior SQLite cleanup lock).
- Plugin suite: **53 passed, 1 skipped**.
- Frontend tests: **103 passed**; lint and production build passed.
- Ruff check/format passed (204 files formatted); mypy passed (50 source files); smoke script compiled.
- Real Windows workflow smoke: **exit 0**. Independent output showed backend nonce `10f52ce6`, live Thonny cursor `4.4`, 186 nodes/247 edges, 64-node bounded overview, layout measurement 0.8 ms, node/edge parity, paging failure/retry and merge, exact `cancellation_requested` acknowledgement, terminal `cancelled`, 4 terminal polls and 4 after the wait, and reduced-motion computed durations `1e-05s`. Manual screen-reader observation remains pending.
- Submitted commit `83d88ba` is on `origin/main`; worktree was clean at review start.

## Stop condition

Fix the duplicate production computation and fail-open scan behavior, rerun required gates and the real workflow, update evidence, commit/push only after all gates pass, verify parity, and stop for Codex review. Do not begin M5.
