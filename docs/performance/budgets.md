# Initial performance and capacity budgets

These budgets derive from the Phase 10 baseline and are guardrails, not claims
about every machine. Required security limits remain the configured scanner limits
(10,000 files, 2 MiB/file, depth 40), 120-second job timeout, bounded job queue,
32 MiB stored-result ceiling, 4 MiB unpaged response ceiling, 1,000-node maximum
page, 100 reusable results, 256 MiB cache budget, and 15-minute default retention.

## Required MVP limits

- Complete graph responses above 4 MiB return `GRAPH_TOO_LARGE`; clients request
  deterministic pages of at most 1,000 primary nodes. Endpoint-context nodes may
  increase the returned node count and are explicitly counted in page metadata.
- Only complete, schema-valid, checksum-valid, unexpired results are reusable.
  Partial, failed, cancelled, corrupt, changed-policy, changed-content, and forced
  refresh attempts are misses.
- Cold jobs must remain under the configured 120-second timeout and 10,000-file
  scanner ceiling. This is an admission/safety limit, not a usability promise.
- Cache retention is 900 seconds by default; LRU eviction enforces both 100 results
  and 256 MiB. Active jobs are stored separately and are not cache-eviction targets.
- Ordinary progress polling remains at least 250 ms (750 ms default); graph page
  requests are sequential and obsolete frontend poll generations are discarded.

## Regression budgets

On comparable Windows/Python hardware, benchmark medians should not exceed 1.5x
the recorded median and worst runs should not exceed 2x the recorded worst before
investigation. The large one-run result is informational until at least five runs
on controlled hardware exist. Correctness, cancellation, limits, and path security
must never be traded for a timing target.

## Aspirational usability targets

- Small projects: cold usable result within 2 seconds and warm cached retrieval
  within one polling interval.
- Approximately 300 files: cold result within 10 seconds; bounded graph page
  retrieval within 1 second on the reference machine.
- Frontend normalization plus deterministic layout below 100 ms for 5,000 loaded
  nodes, excluding React Flow paint; retain the canvas warning above the existing
  configured threshold.

The 1,500-file baseline (~45 seconds across parse, graph, validation, serialization,
and SQLite write) does not meet an interactive target, so incremental file parsing,
streamed serialization, and resolver profiling remain explicit future work. No
millisecond assertion is added to ordinary correctness tests on shared machines.
