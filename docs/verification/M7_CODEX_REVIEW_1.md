# Milestone 7 Codex Review 1

**Date:** 2026-10-13
**Decision:** Changes required
**Reviewed implementation:** `921f930` (`feat(m7): implement CS-015 incremental parse caching and CS-017 graphviz exports`)
**Current checkout:** `590a208`; later commits contain documentation and launcher changes, not M7 implementation changes.
**Scope:** CS-015 persistent per-file parse cache and CS-017 Graphviz exports.

## Findings

### R1 — The Graphviz output limit is checked only after unbounded buffering (CS-017, P1)

`backend/src/codestruct/graph/export_dot.py` calls `Popen.communicate()` with stdout and stderr pipes, then checks `len(stdout_bytes)` against `max_bytes`. `communicate()` buffers both streams until the process exits or times out, so the 10 MiB check does not bound peak memory and stderr has no cap. The `dot` format returns the complete serialized graph directly without applying `max_bytes`; `graph_to_dot()` also constructs the whole string before any rendered-output check. Node and edge count limits do not bound label byte lengths.

**Required:** Enforce byte limits while consuming subprocess output, terminate the process tree as soon as a stream exceeds its limit, bound or safely discard stderr, and apply an output bound to DOT serialization before returning it. Add regressions that emit substantially more than the configured limit on stdout and stderr, plus an oversized DOT-label case. Verify the process stops and the API returns the documented output-limit error without retaining the complete output in memory.

### R2 — Persistent parse-cache byte capacity is not enforced (CS-015, P2)

`PersistentFileParseCache._evict_if_needed()` deletes at most one batch of `max(1, current_count // 10)` LRU entries and does not recalculate whether enough bytes were freed. It also permits an incoming entry larger than the configured budget. A direct probe with ten existing 10-byte rows, a 100-byte limit, and an 80-byte incoming entry evicted one row (90 bytes remained); after insertion the cache would contain 170 bytes, exceeding the configured limit by 70 bytes. Existing eviction tests exercise only the entry-count limit, not byte-cap enforcement.

**Required:** Evict repeatedly until both the post-insert entry count and stored-byte total fit, or skip caching an entry that cannot fit by itself. Add tests for byte-only pressure, combined count and byte pressure, and a single entry larger than the byte budget; assert the configured bounds after each insertion.

### R3 — The claimed slice-versus-complete export distinction is absent from the active frontend (CS-017, P2)

The M7 frontend change is in `frontend/src/features/architecture/TopToolbar.jsx`, but `prototype-launcher/prototype-config.json` launches `frontend.lovable`. The active `frontend.lovable/src/features/workbench.tsx` exposes one generically named “Export DOT graph” action which calls the complete-graph API. It does not explain that the export is complete when the visible graph is a loaded page, nor does it offer a loaded-slice export. The M7 report's frontend parity claim therefore does not describe the user-facing application.

**Required:** Put the distinction in the active application: either expose both loaded-slice and complete-graph exports with unambiguous labels, or explicitly label the existing action as a complete-graph export and explain the behavior when only a slice is loaded. Add a frontend regression for partial-load state. The upcoming standalone panel can satisfy this requirement if it replaces the current frontend as planned; do not delete either frontend directory until the replacement is integrated and verified.

## Verification notes

- Source review confirmed that cache-key composition, worker integration, DOT escaping, deterministic ordering, node/edge count checks, format signatures, and missing-Graphviz API diagnostics are present.
- `node_id()` uses a stable digest, so `_sanitize_id()` collisions for arbitrary hand-built identifiers are not a demonstrated collision in canonical application graph IDs.
- The M7 report records 298 backend tests at 84.81% coverage, 53 Thonny tests, 104 frontend tests, Ruff, Mypy, build, and eight isolated API scenarios. Those full gates were not independently rerun for this review.
- The focused command `.venv\Scripts\python.exe -m pytest tests\test_file_cache.py tests\test_export_dot.py -q` executed 27 tests successfully but exited nonzero because repository-wide `--cov-fail-under=84` was applied to the focused subset (35.75% measured coverage). A retry with coverage disabled was impeded by sandbox access restrictions on pytest temporary/database paths, so it is not counted as a clean focused-gate pass.
- `git diff --check 361795d..921f930` reports trailing whitespace at `docs/verification/M6_REPORT_ACCEPTED.md:3`; the M7 report's clean working-tree check did not verify the tested commit's full diff.

## Review outcome

M7 is **not accepted**. Resolve R1 and R2, and bring the active UI's export semantics into line with the CS-017 claim (or complete this in the replacement standalone panel). Re-run the affected tests and the required quality gates, record fresh evidence, and stop for Codex review. Do not start M8.
