# Phase 12 manual test results

## Result summary

Phase 12 is **Partial**. A real Windows browser session passed the core sample, partial-result, search, filter, details, table, cache, validation, dark-theme, and responsive-width workflows. Cancellation under real sustained work, fault-injection workflows, browser zoom, light/reduced-motion modes, a real screen reader, other browsers, macOS, Linux, and participant usability sessions remain pending.

## Observed environment

Windows NT 10.0.26200.0 local processes used Python 3.14.6, FastAPI 0.141.1, Uvicorn 0.52.4, Node 24.18.0, npm 11.16.0, React 19.2.8, React Flow 12.11.6, and Vite 8.2.2. The tested browser was the Codex in-app Chromium surface; its exact product/version was not exposed. The OS preferred dark color scheme and did not prefer reduced motion.

## Executed workflows

| ID | Result | Actual observation |
|---|---|---|
| M-01 | Pass | Submission by pointer and by keyboard reached queued/progress and completed; the real React Flow canvas rendered 15 entities and 19 relationships for the sample. |
| M-02 | Pass with limitation | `get_user` found four results, Next selected `db.get_user`, centered it, and details truthfully showed unresolved status, unavailable path/span, one incoming relationship, and no source-navigation claim. |
| M-03 | Pass | Class filtering showed 4/15 entities and 1/19 relationships; retained search produced an explicit no-match state; Reset restored the graph. |
| M-04 | Pass | Table mode exposed all 15 node and 19 edge records with type, state, confidence, evidence/source, and inspect actions. |
| M-05 | Pass | The parser fixture completed partially with 96 entities, 119 relationships, and 32 diagnostics; encoding and syntax failures were safe and valid-file results remained available. |
| M-06 | Pass | Repeating an unchanged project displayed Cached result; forced refresh queued and completed, preserving an existing selection where applicable. |
| M-07 | Pending | The local fixtures completed before a usable running cancellation action could be exercised. Phase 11 process tests are supporting evidence, not a manual pass. |
| M-08 | Pass | `..` was rejected as unauthorized and `missing-project` as nonexistent; neither error exposed an absolute path. Empty input was normalized to the root and returned its cache. |
| M-09 | Fail | With the API stopped, submission displayed “The backend returned an invalid response” rather than a connection-specific recovery message (`P12-004`). |
| M-10 | Partial | A 100-file graph warned at 804/1002; a 600-file, 8.25 MB stored graph used 413-to-paged fallback and ultimately showed 4,819/6,017, but all pages were eagerly merged and an Empty graph state appeared during retrieval (`P12-002`, `P12-003`). |
| M-11 | Partial | 1440, 1024, 768, and 390 CSS-pixel widths retained controls with no document-level horizontal overflow. Browser zoom at 125% and 200% could not be set reliably in the in-app browser. |
| M-12 | Partial | Semantic labels, regions, statuses, visible controls, table alternative, non-color line patterns, `lang=en`, and dark-theme CSS contrast samples passed; page title, real screen reader, full focus traversal, light theme, and reduced motion remain incomplete. |
| M-13 | Pending | Automated tests cover principal faults; destructive manual injections and restart retrieval were not repeated in the live UI. |
| M-14 | Pending | Windows was exercised; macOS and Linux were not available. |

## State observations

| State | Evidence |
|---|---|
| Initial, validating/project selected, queued, completed | Observed in browser |
| Scanning, parsing, resolving, building graph | Fast jobs transitioned too quickly for every label to be captured; API/automated evidence only |
| Partially completed | Observed with parser fixture |
| Failed | Observed for traversal, missing directory, and unavailable backend |
| Cache hit | Observed |
| Large graph | Observed for 804 and 4,819 nodes |
| Cancel requested/cancelled | Automated only; manual pending |
| Empty graph, unsupported schema | Component tests only; controlled browser injection pending |

## Responsiveness and visual notes

- Search, filter, selection, and view switching felt immediate for the sample and 96-node fixture; no formal user-perceived timing instrumentation was available.
- The 96-node graph was already visually dense and labels were difficult to scan at 1440 x 900 (`P12-005`).
- For the 600-file project, transport pagination worked, but browser retrieval took roughly 20 seconds in an independent client run and the UI eagerly materialized the complete graph.
- At 390 CSS pixels, controls stacked and remained reachable; no horizontal page overflow was measured. Visual density, not basic responsiveness, is the main limitation.

## Privacy and safety observations

User-controlled strings appeared through text nodes; no `dangerouslySetInnerHTML`/raw-HTML sink was present in the rendered app. Graph and diagnostics displayed project-relative paths; traversal and missing-path errors were redacted. Browser/API traffic observed during the workflow was local. These observations do not constitute a full network-egress audit.

## Regression status

No production fix was made in Phase 12. The final backend run collected 74 tests: 73 passed and one Windows directory-link test was skipped because the test account cannot create the link. Statement/branch coverage was 85.69%, above the configured 84% gate. Ruff format and lint passed, and mypy reported no issues in 40 source files. Frontend coverage ran 42 passing tests across four files (73.86% statements, 63.39% branches, 70.27% functions, 76.99% lines); the focused accessibility command ran one passing test and skipped 41 nonmatching tests. ESLint and the no-write Vite build passed. jsdom reported its expected unimplemented canvas warning; renderer geometry remains a browser/manual concern. The ignored Phase 12 generated projects/databases were removed after path verification, both local servers were stopped, and ports 5173/8000 had no remaining listeners. Related automated detail remains in [phase-11-results.md](phase-11-results.md).

## Phase 13 remediation follow-up

Both High issues were reproduced before remediation. In a real Windows Chromium-derived browser, safe discovery displayed the configured aliases **Team** and **Large** without paths; selecting Team completed the 15-node sample through an initial `graph?limit=1000` request. A deterministic 300-file project returned an initial context-inclusive slice of 1,603/2,410 nodes and 1,400/3,008 edges. Keyboard activation of **Load more graph data** advanced to 2,406 nodes and then the complete 2,410/3,008 result; server logs contained no unbounded graph request. The title was `CodeStruct Architecture Explorer`, and at 390 CSS pixels the selector/actions remained visible with no document overflow. Empty-project discovery and unavailable-project presentation were component-tested because settings reject unavailable roots at startup.

Final Phase 13 automation collected 78 backend tests: 77 passed, one directory-link test skipped, and coverage rose to 86.46%. Five frontend files ran 49 passing tests at 79.04% statements, 66.29% branches, 76.11% functions, and 82.91% lines. Ruff format/lint, mypy (41 files), ESLint, focused axe, and no-write Vite build passed. The controlled benchmark completed and safely removed its generated files; its 303-file median was 1.256 seconds parsing and 1.566 seconds graph construction, while the single 1,515-file run used 80.915 MiB peak and produced 19.672 MiB JSON. Real screen-reader, light mode, zoom, macOS/Linux, and full manual fault injection remain pending.
