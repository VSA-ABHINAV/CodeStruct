# Phase 12 manual test plan

## Purpose and evidence rules

This plan validates the complete local CodeStruct workflow without changing product semantics. A result is **Pass** only when it was observed in a real application/browser session during Phase 12. **Automated evidence** means a Phase 11 test supports the behavior but does not replace manual review. **Pending** means the required platform, browser, assistive technology, fault injector, or user participant was unavailable.

## Test environment and data

- Repository: unborn `main`, no commits or remotes.
- Host: Windows, Python 3.14.6, FastAPI 0.141.1, Uvicorn 0.52.4, Node 24.18.0, npm 11.16.0, React 19.2.8, React Flow 12.11.6, Vite 8.2.2.
- Browser: Codex in-app Chromium surface. Firefox, Safari, and installed Chrome/Edge were not available through the test surface.
- Viewports: 1440 x 900, 1024 x 768, 768 x 900, and 390 x 900.
- Data: `sample_project`; the committed parser fixture for partial/error behavior; deterministic ignored 100-, 303-, and 600-file projects generated beneath `.codestruct/test-output/phase12`.
- Safety: generated source contains no side effects; temporary databases and projects are confined to the ignored test-output directory; source execution remains covered by the automated suite.

## Workflow scripts

| ID | Workflow | Procedure | Required evidence |
|---|---|---|---|
| M-01 | Start and submit | Start API and Vite from documented commands, enter `.`, submit by pointer and keyboard | Initial, validating/queued, progress, completed, graph |
| M-02 | Explore | Use pan/zoom/fit/reset, search `get_user`, step matches, select result, inspect details | Stable selection, counts, relative source/evidence |
| M-03 | Filter | Filter class nodes, reset, filter relationship/status where practical | Visible/total counts and meaningful empty state |
| M-04 | Accessible alternative | Switch to Table and inspect node/relationship rows using keyboard | Complete equivalent text representation |
| M-05 | Partial result | Analyze parser fixture containing valid, syntax-error, and invalid-encoding files | Valid graph retained; partial state and safe diagnostics |
| M-06 | Cache/refresh | Re-submit unchanged input, then force refresh | Cache-hit indication; refreshed terminal result |
| M-07 | Cancellation | Cancel a deliberately slow queued/running job | Prompt acknowledgement and terminal cancelled state |
| M-08 | Invalid input | Submit traversal and missing relative paths | Actionable, redacted validation error |
| M-09 | Backend unavailable | Stop API, submit, restart API, retry | Accurate failure, preserved state if promised, successful recovery |
| M-10 | Large graph | Analyze deterministic 100-, 303-, and 600-file projects | Warning, bounded retrieval, truthful partial/full counts, responsive UI |
| M-11 | Responsive | Repeat key exploration at all target viewports and browser zoom levels | No lost controls, overlap, clipping, or horizontal page scroll |
| M-12 | Accessibility | Keyboard-only run, focus review, live announcements, table, dark/light/reduced motion, screen reader | WCAG 2.2 AA evidence and named assistive technology |
| M-13 | Reliability faults | Exercise expiry, corrupt cache, queue saturation, timeout, crash, restart recovery | Documented terminal state, safe recovery, no orphan process |
| M-14 | Platform | Repeat M-01, M-05, M-08, and process/path tests on supported Windows, macOS, Linux | Platform-specific evidence, especially links and spawn |

## State coverage

The browser run must explicitly observe initial, validating/project-selected, queued, scanning, parsing, resolving, graph building, completed, partial, failed, cancelled, cache hit, empty, unsupported-schema, and large-graph states. Automated component evidence is recorded separately when a state cannot be induced safely.

## Requirement and journey coverage

| Scope | Manual coverage |
|---|---|
| J-01 normal analysis | M-01, M-02 |
| J-02 partial/error analysis | M-05 |
| J-03 large project | M-07, M-10 |
| J-04 search | M-02 |
| J-05 filter | M-03 |
| J-06 details/evidence | M-02, M-04 |
| J-07 cancellation | M-07 |
| J-08 recovery | M-05, M-09, M-13 |
| J-09 cache/reopen | M-06, M-13 |
| J-10 unsafe selection | M-08, M-14 |

All 32 Must requirements retain the automated mapping in [automated-test-strategy.md](automated-test-strategy.md). Manual evidence particularly targets `FR-SCAN-001`, `FR-SCAN-003`, `FR-JOB-001`, `FR-JOB-002`, `FR-GRAPH-001`, `FR-SEARCH-001`, `FR-FILTER-001`, `FR-DETAIL-001`, `FR-STATE-001`, `FR-SCALE-001`, `FR-REFRESH-001`, `NFR-RESP-001`, `NFR-A11Y-001`, `NFR-PLAT-001`, and `NFR-PACK-001`.

## Exit criteria

Release sign-off requires no open Critical or High defect; real screen-reader and complete keyboard evidence; supported-platform smoke/security results; approved contrast and zoom results; truthful large-graph loading; and all pending automated gates passing. Phase 12 does not authorize closing these gates through documentation alone.
