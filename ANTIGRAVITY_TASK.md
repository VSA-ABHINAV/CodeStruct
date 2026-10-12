# Antigravity task: Milestone 7 — Effective cache and Graphviz exports

Date: 2026-10-12. Repository: `D:\REP\Codestruct\Codestruct`.

M6 is considered complete based on the user's instruction to rely on Antigravity's report; see `docs/verification/M6_REPORT_ACCEPTED.md` and `docs/verification/M6.md`. This is not an independent Codex implementation review. Read the primary technology summary at `D:\REP\# CodeStruct – Technology Summary.txt`, the M7 entries CS-015 and CS-017 in `docs/codestruct_audit.md`, `PROCESS_TRACKER.md`, and current cache/export docs and tests. Implement only **M7 / CS-015 and CS-017**. Do not begin M8. Do not redesign the frontend.

## Required outcomes

### CS-015: effective incremental parse caching

1. Trace the real production analysis worker/job path and integrate per-file parse caching where repeated project analyses actually execute. Preserve the existing content-verified whole-result cache.
2. Prevent stale or cross-project reuse. Cache identity/invalidation must account for canonical project/root identity, normalized relative path, content digest (not size/mtime alone), parser/cache schema or policy version, and any parse options that affect output.
3. Bound cache storage and define safe eviction, concurrency, persistence, and corruption behavior. Avoid trusting cache files or paths outside the project-owned application cache location. Cache failures must degrade to a correct uncached parse.
4. Prove cold parse, warm reuse in the actual worker path, exact invalidation after same-size edits or manipulated timestamps, isolation across roots with identical relative paths, parser-version/options invalidation, eviction/bounds, corrupt cache recovery, and parallel job safety.

### CS-017: bounded, deterministic Graphviz exports

1. Provide optional Graphviz DOT-to-SVG and DOT-to-PNG exports for the canonical complete graph. Handle Graphviz unavailable/unconfigured cleanly and report an actionable diagnostic; do not make Graphviz a required runtime dependency unless the project explicitly already does so.
2. Escape labels and attributes safely; bound graph size, subprocess runtime, output bytes, and resource use. Never allow user-controlled labels to inject DOT statements or command arguments. Use argument arrays, no shell invocation, and terminate timed-out render processes.
3. Make generated output deterministic for equivalent graph input and document layout/export options. Verify SVG/PNG signatures and content; test empty, dense, malformed, hostile-label, missing-executable, timeout, and output-limit cases.
4. Update frontend export behavior only as required: clearly distinguish exporting the complete graph from exporting the currently loaded/visible slice. Do not claim a partial slice is a complete export; add contract and UI tests for both cases.

## Run-to-completion, verification, and report

Keep working within M7 until both CS-015 and CS-017 outcomes and the verification matrix pass. Fix failures and rerun focused checks before affected and full gates. No paid or remote services are needed. Run focused cache/worker/job tests, Graphviz export tests (including real Graphviz when installed and explicit unavailable-path tests), backend full coverage at least 84%, Thonny plugin tests, frontend tests/lint/build if affected, Ruff check/format, mypy, compilation, and `git diff --check`.

Run the real backend/API workflow on an isolated temporary database and exercise repeated project analyses through the production job worker; record observable cold/warm parse behavior, invalidation, and cache isolation. Exercise DOT/SVG/PNG export through the real API/service path and verify exported artifact format and complete-vs-slice semantics. Record exact commands, outcomes, environment/Graphviz version or unavailable status, representative evidence, and limitations in `docs/verification/M7.md`.

Commit non-empty M7 implementation after all gates pass. Identify the exact tested code commit and report commit. If any implementation, test, dependency, or configuration file changes after the tested code commit, rerun every affected gate and reconcile the report. Update `PROCESS_TRACKER.md` and `docs/codestruct_audit.md` only to match evidence. Stop after M7 and report **Ready for review**. Do not begin M8.

## M7 file cleanup after verification

Inventory files created during M7 and search references before removal. Remove only M7-created scratch files, temporary databases/logs, or redundant artifacts proven unused and unnecessary for reproducibility. Preserve source, tests, fixtures, required scripts, `docs/verification/M7.md`, historical review/acceptance records, audit/tracker files, and pre-existing or user data. Avoid broad cleanup/reset commands. Record removals and verify final test state and `git status`.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md, docs/verification/M6_REPORT_ACCEPTED.md, docs/verification/M6.md, docs/codestruct_audit.md, PROCESS_TRACKER.md, and D:\REP\# CodeStruct – Technology Summary.txt. Implement only M7 / CS-015 and CS-017: integrate safe content-verified per-file caching into the real production job worker with bounded storage and proven invalidation/isolation; implement bounded optional deterministic Graphviz SVG/PNG export with safe escaping, actionable availability diagnostics, and accurate complete-graph versus loaded-slice behavior. Keep fixing and rerunning until all focused and full gates pass, including real isolated backend/API workflows for repeated analyses and exports. Record exact tested code/report commits, commands, outcomes, limitations, and safe cleanup in docs/verification/M7.md; update the tracker and audit to match actual evidence; remove only M7-created artifacts proven unused. Commit the completed M7 work, then stop and report Ready for review. Do not begin M8.</span>
