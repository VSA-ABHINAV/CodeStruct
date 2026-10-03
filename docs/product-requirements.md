# CodeStruct product requirements

## Document purpose

This Phase 4 document converts the verified current architecture into product
requirements for a safe, useful Python architecture explorer. It defines desired
outcomes without selecting libraries, process topology, storage engines, or a
detailed technical architecture.

Source baselines:

- [Current architecture](architecture/current-architecture.md)
- [Current data contract](architecture/current-data-contract.md)
- [User journeys](ux/user-journeys.md)
- [UX wireframes](ux/explorer-wireframes.md)
- [Acceptance criteria](ux/acceptance-criteria.md)

## Status vocabulary

- **Implemented:** verified in the current source and characterized contract.
- **MVP required:** a Must requirement in this document. It is not implemented
  merely because it is documented.
- **Post-MVP:** a Should or Could outcome that is excluded from MVP acceptance.
- **Research:** a possible future direction with no product commitment.
- **Assumption:** a premise requiring confirmation before detailed design.

Phase 2 pytest, Ruff, and mypy execution remains pending because their local
development dependencies are unavailable. This is an open delivery prerequisite
and not evidence that the configured checks pass.

## Existing implemented behavior

The current implementation analyzes the fixed `sample_project` directory when
`GET /analyze` is called. It scans top-level `.py` files, uses Python `ast` to
collect short names and limited syntactic relationships, derives same-directory
import edges, and returns unvalidated dictionaries. The React application invokes
a hard-coded API address and renders basename-identified nodes and import edges
with React Flow. It has a button loading state and a generic alert on thrown
request errors.

The implementation does not provide user project selection, recursive scanning,
package or symbol resolution, source evidence, partial results, progress,
cancellation, search, filters, details, caching, diagnostics, contract versioning,
or a complete state model. These absences are baseline limitations, not implied
requirements that already work.

## Users and goals

| User | Primary goals | Required evidence of success |
| --- | --- | --- |
| Developer entering an unfamiliar Python project | Find important modules and symbols, understand relationships, and reach relevant source quickly | Can locate a known symbol and explain a supported relationship using source evidence |
| Maintainer investigating dependencies and change impact | Inspect inbound and outbound dependencies and identify affected areas without overclaiming certainty | Can follow dependency paths and distinguish resolved, unresolved, and syntactic relationships |
| Reviewer examining implementation structure | Review classes, functions, methods, imports, inheritance, and practical calls | Can filter relationship types and inspect locations and diagnostics |
| Student or educator learning project structure | Connect Python syntax to a navigable structural model | Can use plain terminology and a non-graph representation to explain a small project |
| Future Thonny user | Access the same analysis concepts from an editor workflow | Requirements remain portable, but no Thonny interaction or integration is designed in Phase 4 |

## Product principles

1. Never present a syntactic observation as a resolved fact.
2. Analyze source without executing it.
3. Make the filesystem trust boundary visible and enforceable.
4. Preserve useful results when individual files fail.
5. Keep every relationship traceable to evidence or an explicit unresolved reason.
6. Provide a complete text-based path through information represented visually.
7. Prefer deterministic, testable behavior over hidden heuristics.
8. Maintain compatibility deliberately while the current contract is replaced.

## MVP functional requirements

All requirements in this section are **Must** and collectively define the MVP.

| ID | Requirement |
| --- | --- |
| `FR-SCAN-001` | The user shall select a Python project only from locations authorized by configured project roots, and the product shall validate the selection before analysis. |
| `FR-SCAN-002` | The product shall scan Python files recursively within the authorized project boundary and assign an unambiguous project-relative identity to every included file and module. |
| `FR-SCAN-003` | The product shall apply documented default exclusions and project ignore rules, show an exclusion summary, and allow only policy-permitted session overrides. |
| `FR-ANALYZE-001` | The product shall report modules, files, classes, functions, async functions, methods, and imports while preserving containment and qualified identity. |
| `FR-ANALYZE-002` | The product shall report dependency, inheritance, and practical call relationships, distinguishing resolved relationships from unresolved or purely syntactic observations. |
| `FR-ANALYZE-003` | Every reported relationship shall provide relationship type, origin, confidence category, and available project-relative source evidence; absence of evidence shall be explicit. |
| `FR-JOB-001` | Analysis shall expose queued, scanning, parsing, resolving, and graph-building progress with completed work, known total when available, and current phase. |
| `FR-JOB-002` | A user shall be able to request cancellation while analysis is active and receive a terminal cancelled state without presenting incomplete output as complete. |
| `FR-ERROR-001` | Failure to read or parse an individual file shall not discard successful results from other files; the outcome shall be marked partially completed when useful results remain. |
| `FR-ERROR-002` | The product shall provide actionable diagnostics for syntax errors, unreadable or unsupported files, missing dependencies, policy limits, and failed analysis, without exposing sensitive absolute paths. |
| `FR-GRAPH-001` | The explorer shall support keyboard- and pointer-operable pan, zoom, fit view, and reset view while preserving the user's current selection when possible. |
| `FR-SEARCH-001` | The user shall search files, modules, classes, functions, and methods by displayed or qualified name and highlight matching results in both visual and text representations. |
| `FR-FILTER-001` | The user shall filter by entity type, relationship type, resolution state, and confidence without starting a new analysis. |
| `FR-DETAIL-001` | Selecting an entity or relationship shall open details containing identity, type, connected items, project-relative source path, source location when available, evidence, confidence, and related diagnostics. |
| `FR-STATE-001` | The interface shall distinguish initial, project selected, validation failed, queued, scanning, parsing, resolving, graph building, completed, partially completed, failed, cancelled, and cached-result-loaded states. |
| `FR-SCALE-001` | Before rendering a result above a configurable complexity limit, the product shall warn the user and offer bounded aggregation or scope controls plus a complete text alternative. |
| `FR-REFRESH-001` | The user shall be able to repeat analysis, deliberately refresh stale cached data, or reopen an authorized compatible cached result with its age, scope, and configuration visible. |
| `FR-COMPAT-001` | During migration, the product shall either continue serving and consuming the characterized `files` and `dependencies` contract or present a clear compatibility failure; silent reinterpretation is prohibited. |

## Non-functional requirements

| ID | Priority | Requirement and measurable verification |
| --- | --- | --- |
| `NFR-SEC-001` | Must | Canonicalize every selected path and verify it is contained by an authorized configured root before any scan; test valid, traversal, case-variant, alternate-separator, nonexistent, and unauthorized paths. |
| `NFR-SEC-002` | Must | Define one default-deny policy for symbolic links, junctions, and other reparse points that escape the authorized root; verify containment against link targets before reading. |
| `NFR-SEC-003` | Must | Static analysis shall never import, execute, compile for execution, or invoke analyzed source; security tests shall use files with observable side effects and confirm zero effects. |
| `NFR-SEC-004` | Must | Enforce configurable file-count, per-file size, recursion-depth, elapsed-time, and memory policies; exclude secrets, environments, generated output, dependencies, and VCS internals by default; expose only project-relative or redacted paths in user-visible rejection details. |
| `NFR-PRIV-001` | Must | Source content, paths, results, and cache data shall remain on the user's machine by default; network tests shall observe zero analysis-data egress during an offline analysis. |
| `NFR-PERF-001` | Must | **Benchmark required:** before MVP release, record median and 95th-percentile phase and total durations, peak memory, and result size for representative small, medium, and policy-limit projects; product targets shall be approved from that baseline rather than invented here. |
| `NFR-RESP-001` | Must | **Benchmark required:** measure selection feedback, cancellation acknowledgement, search/filter feedback, and graph/text navigation latency on representative result sizes; approve thresholds before MVP release and expose progress whenever work exceeds the approved immediate-response threshold. |
| `NFR-REL-001` | Must | Every accepted job shall reach exactly one terminal state, preserve valid per-file results across recoverable failures, and never label cancelled or partial output as complete; fault-injection tests shall cover each phase. |
| `NFR-A11Y-001` | Must | Meet WCAG 2.2 AA for the MVP workflow, including full keyboard access, visible focus, accessible names, non-color relationship cues, contrast, reduced motion, text/table graph alternatives, and announced errors and progress; verify with automated checks and manual keyboard and screen-reader tests. |
| `NFR-PLAT-001` | Must | The supported local workflow shall pass its agreed smoke and security-path suite on current supported Windows, macOS, and Linux configurations; filesystem semantics that differ by platform shall have explicit tests. |
| `NFR-DETER-001` | Must | Ten repeated analyses of unchanged input, configuration, and analyzer version shall produce the same semantic identities, ordering, diagnostics, and relationships. |
| `NFR-TEST-001` | Must | Every Must requirement shall have an automated acceptance path where automation is feasible, with manual procedures recorded for accessibility and usability checks; pending Phase 2 checks must pass before release. |
| `NFR-BACK-001` | Must | Existing prototype consumers shall receive the characterized legacy shape until an announced migration condition is met; contract fixtures shall fail on removal, renamed fields, changed required types, or silent semantic changes. |
| `NFR-PACK-001` | Must | Installation and startup shall work from a documented application entry point without depending on the caller's working directory; verify from at least the repository root and a different directory. |
| `NFR-MAINT-001` | Should | Scanning, parsing, resolution, relationship construction, job orchestration, contract mapping, configuration, and UI state shall have independently testable ownership with no circular dependency between those responsibilities. |
| `NFR-OBS-001` | Should | Each analysis shall produce local structured operational events for job ID, phase, duration, counts, limits, terminal status, and diagnostic codes, excluding source content, secret values, and unauthorized absolute paths. |

## Filesystem security boundary

### Required boundary

The authorized root set is configuration controlled by the product owner or local
administrator. A user selection is accepted only after canonicalization and
containment validation. Authorization applies to the resolved target, not merely
the path string supplied by the interface.

The scan shall default to staying within the accepted root. A symlink, junction,
mount, or reparse point whose resolved target cannot be proven inside that root is
not traversed. Whether in-root links are followed is an open decision; the MVP
must choose and disclose one deterministic policy before implementation.

Static analysis reads source as data. It does not import project modules, run
project commands, evaluate annotations, invoke plugins discovered inside the
project, or execute build and configuration files. Parser behavior must be tested
against source containing import-time and top-level side effects.

### Default exclusions

The default deny set includes, at minimum:

- `.git`, `.hg`, `.svn`, and other VCS internals;
- `.env`, credentials, private keys, known secret files, and product-configured
  sensitive patterns;
- `.venv`, `venv`, `env`, `__pycache__`, test and tool caches;
- `node_modules`, vendored dependencies, generated build and distribution output;
- CodeStruct output and cache directories; and
- non-Python or unsupported files unless a later requirement explicitly includes
  them.

Project ignore rules may add exclusions. Session overrides cannot weaken
administrator-enforced roots, sensitive-file exclusions, filesystem-link policy,
or resource limits. The UI reports the rejected category and a safe
project-relative location where permitted, never an unauthorized canonical path.

### Resource policy

The policy model represents maximum included-file count, maximum bytes per file,
maximum traversal depth, maximum elapsed analysis time, and maximum memory. The
numeric defaults require benchmark and threat-model evidence. Reaching a limit
must produce a diagnostic and a terminal failed or partially completed state
according to whether valid results remain.

## MoSCoW scope

### Must

- All `FR-*` and Must `NFR-*` requirements listed above.
- Safe local Python project analysis with recursive discovery, explicit
  diagnostics, evidence-aware relationships, accessible exploration, and a
  deliberate legacy-contract migration path.

### Should

- `NFR-MAINT-001` and `NFR-OBS-001`.
- `FR-IMPACT-001`: show bounded inbound, outbound, and shortest dependency paths
  from a selected item as an aid to change-impact investigation, with the same
  evidence and confidence caveats as the source relationships.
- `FR-EDU-001`: provide concise explanations of entity and relationship terms for
  learning workflows without replacing source evidence.

### Could

- `FR-GRAPH-002`: collapse or expand user-chosen package and directory groups.
- `FR-DETAIL-002`: hand an evidence location to a user-configured external editor.
- `FR-EXPORT-001`: export a filtered, redacted analysis summary in a documented
  interoperable format.

### Won't in MVP

- Dynamic runtime tracing.
- LLM or retrieval-augmented generation features.
- Architecture clustering.
- Design-pattern detection.
- Git-history analysis.
- Advanced points-to analysis.
- Migration from React Flow to Cytoscape.js.
- Graph databases.
- Thonny integration.

These are research or later product ideas. Their appearance in prior research
artifacts does not make them requirements.

## Traceability matrix for MVP requirements

Acceptance criteria use matching IDs in
[acceptance-criteria.md](ux/acceptance-criteria.md). Journey IDs refer to
[user-journeys.md](ux/user-journeys.md). “Future boundary” is intentionally
high-level and does not prescribe a Phase 5 design.

| Requirement | Journey | Acceptance | Current limitation | Future boundary |
| --- | --- | --- | --- | --- |
| `FR-SCAN-001` | `J-01`, `J-10` | `AC-FR-SCAN-001` | Fixed path; no validation workflow | Project selection and policy |
| `FR-SCAN-002` | `J-01`, `J-03` | `AC-FR-SCAN-002` | Top-level scan; basename IDs | Scanner and identity ownership |
| `FR-SCAN-003` | `J-01`, `J-03` | `AC-FR-SCAN-003` | Only hard-coded `.py` suffix filter | Exclusion policy |
| `FR-ANALYZE-001` | `J-01`, `J-04` | `AC-FR-ANALYZE-001` | Flattened short-name AST output | Entity analysis |
| `FR-ANALYZE-002` | `J-01`, `J-05` | `AC-FR-ANALYZE-002` | Filename-matched imports and syntactic calls | Relationship analysis |
| `FR-ANALYZE-003` | `J-02`, `J-06` | `AC-FR-ANALYZE-003` | No evidence or confidence | Evidence model |
| `FR-JOB-001` | `J-01`, `J-03` | `AC-FR-JOB-001` | One synchronous request result | Job lifecycle |
| `FR-JOB-002` | `J-03`, `J-07` | `AC-FR-JOB-002` | No cancellation | Job lifecycle |
| `FR-ERROR-001` | `J-02`, `J-08` | `AC-FR-ERROR-001` | One file exception fails all output | Diagnostic and result policy |
| `FR-ERROR-002` | `J-02`, `J-08`, `J-10` | `AC-FR-ERROR-002` | Unstructured framework failure | Diagnostic presentation |
| `FR-GRAPH-001` | `J-01`, `J-06` | `AC-FR-GRAPH-001` | Pan/zoom/fit only; no reset workflow | Explorer interaction |
| `FR-SEARCH-001` | `J-04` | `AC-FR-SEARCH-001` | No search | Explorer query |
| `FR-FILTER-001` | `J-05` | `AC-FR-FILTER-001` | No filters | Explorer query |
| `FR-DETAIL-001` | `J-06` | `AC-FR-DETAIL-001` | Node labels only; no source location | Detail and evidence view |
| `FR-STATE-001` | `J-01`, `J-02`, `J-07`, `J-09`, `J-10` | `AC-FR-STATE-001` | Loading boolean and alert only | UI state model |
| `FR-SCALE-001` | `J-03` | `AC-FR-SCALE-001` | Fixed full graph; no thresholds | Scale and aggregation controls |
| `FR-REFRESH-001` | `J-08`, `J-09` | `AC-FR-REFRESH-001` | No cache or refresh semantics | Result lifecycle |
| `FR-COMPAT-001` | `J-01`, `J-09` | `AC-FR-COMPAT-001` | Implicit unversioned contract | Compatibility adapter |
| `NFR-SEC-001` | `J-01`, `J-10` | `AC-NFR-SEC-001` | No selectable path boundary | Filesystem policy |
| `NFR-SEC-002` | `J-10` | `AC-NFR-SEC-002` | Link behavior undefined | Filesystem policy |
| `NFR-SEC-003` | `J-01`, `J-02` | `AC-NFR-SEC-003` | AST is non-executing but not specified as invariant | Parser safety boundary |
| `NFR-SEC-004` | `J-03`, `J-10` | `AC-NFR-SEC-004` | No limits or sensitive default exclusions | Resource and exclusion policy |
| `NFR-PRIV-001` | `J-01`, `J-09` | `AC-NFR-PRIV-001` | Local behavior exists but is not a product guarantee | Privacy policy |
| `NFR-PERF-001` | `J-03` | `AC-NFR-PERF-001` | No benchmark or budget | Performance verification |
| `NFR-RESP-001` | `J-03`, `J-04`, `J-07` | `AC-NFR-RESP-001` | No measured responsiveness | Interaction verification |
| `NFR-REL-001` | `J-02`, `J-07`, `J-08` | `AC-NFR-REL-001` | No job state or partial result | Job and result lifecycle |
| `NFR-A11Y-001` | `J-01`, `J-04`, `J-05`, `J-06` | `AC-NFR-A11Y-001` | No complete keyboard/text graph workflow | Accessible explorer |
| `NFR-PLAT-001` | `J-01`, `J-10` | `AC-NFR-PLAT-001` | Working-directory and filesystem coupling | Platform verification |
| `NFR-DETER-001` | `J-01`, `J-09` | `AC-NFR-DETER-001` | Unsorted directory order and index edge IDs | Deterministic identity and ordering |
| `NFR-TEST-001` | `J-01`, `J-02`, `J-10` | `AC-NFR-TEST-001` | Phase 2 suite remains unrun | Quality verification |
| `NFR-BACK-001` | `J-01`, `J-09` | `AC-NFR-BACK-001` | No version or schema guard | Compatibility boundary |
| `NFR-PACK-001` | `J-01` | `AC-NFR-PACK-001` | Startup depends on backend CWD | Application entry point |

## Success measures for later usability evaluation

No numeric product targets are asserted without baseline evidence.

| Measure | Collection definition | Target status |
| --- | --- | --- |
| Task completion rate | Percentage completing each defined journey without facilitator intervention | Baseline required by persona and project size |
| Time to locate a symbol | Time from loaded result to correct entity selection and source evidence | Baseline required |
| Time to identify a dependency path | Time from task prompt to correct supported path with confidence/evidence interpretation | Baseline required |
| Navigation actions | Count of searches, filter changes, graph gestures, list navigation, and detail openings per task | Baseline required; lower is not automatically better |
| Error recovery rate | Percentage completing the intended task after a syntax error, invalid path, limit, or transient failure | Baseline required by failure class |
| User-reported comprehension | Post-task rating plus explanation accuracy against a scoring rubric | Rubric and baseline required |
| Accessibility task completion | Completion and time for keyboard-only and screen-reader participants | Baseline required; parity criterion requires user research |

## Assumptions requiring confirmation

1. MVP runs locally and analyzes local Python projects rather than remote
   repositories or uploaded archives.
2. A trusted administrator or installation policy can define authorized roots.
3. Project-relative paths are sufficient for ordinary UI disclosure.
4. Users accept a deterministic default exclusion policy with visible summaries.
5. Relationship confidence can use a small, understandable category set rather
   than an unexplained numeric score.
6. A text/table representation can provide functional parity for core graph tasks.
7. Cached results may be stored locally if their scope, retention, authorization,
   and invalidation rules are visible and controllable.
8. The legacy response can remain temporarily available while the new contract is
   introduced.

## Open decisions

1. Who configures authorized roots, and what local user roles exist?
2. Are in-root symbolic links and junctions followed, represented without
   traversal, or always excluded?
3. Which ignore sources are recognized, and what precedence applies among
   administrator policy, product defaults, project rules, and session choices?
4. What entity and relationship confidence vocabulary can users interpret
   reliably?
5. What qualifies as a “practical call relationship” for MVP without advanced
   points-to analysis?
6. What benchmark corpus represents small, medium, large, and limit-sized Python
   projects?
7. Which complexity measure triggers graph aggregation: entities, relationships,
   density, render cost, or a combination?
8. What cache retention, encryption, invalidation, and per-user authorization
   policy is acceptable?
9. How long must the legacy contract coexist, and what observable event permits
   its removal?
10. Which source viewer capabilities are in-product versus handed to an external
    editor?
11. Which browser, assistive technology, OS, and filesystem combinations define
    the supported matrix?
12. What authentication or process isolation is required if the API can bind
    beyond localhost?
13. Which Python versions, grammar features, typing constructs, and generated or
    extension-backed modules define the supported Python language subset?
14. Should dependency data be edge-centric, node-centric, or exposed through
    compatible projections of one canonical model?

## Decisions deferred beyond Phase 4

Phase 5 may decide component boundaries, APIs, data types, process and job model,
storage approach, packaging, and technology choices after resolving the product
questions above. Phase 4 does not approve a graph library, background queue,
database, parser framework, or deployment topology.
