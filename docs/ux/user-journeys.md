# CodeStruct user journeys

## Purpose

These journeys describe observable user workflows for the MVP requirements in
[product-requirements.md](../product-requirements.md). They do not prescribe UI
frameworks or backend implementation. Wireframe regions and state presentation
are defined in [explorer-wireframes.md](explorer-wireframes.md).

## Journey conventions

- A “project” is a local selection that has passed the configured authorization
  and filesystem policy.
- A “relationship” may be resolved, unresolved, or syntactic; the interface must
  not blur those states.
- A “source location” is project-relative and includes line/column information
  only when evidence exists.
- Every journey remains available through keyboard and text/table navigation, not
  only through direct graph manipulation.

## `J-01` Analyze a small authorized project

**Primary users:** unfamiliar-project developer, reviewer, student.

**Requirements:** `FR-SCAN-001`, `FR-SCAN-002`, `FR-SCAN-003`,
`FR-ANALYZE-001`, `FR-ANALYZE-002`, `FR-JOB-001`, `FR-GRAPH-001`,
`FR-STATE-001`, `FR-COMPAT-001`, `NFR-SEC-001`, `NFR-SEC-003`,
`NFR-PRIV-001`, `NFR-A11Y-001`, `NFR-PLAT-001`, `NFR-DETER-001`,
`NFR-TEST-001`, `NFR-BACK-001`, `NFR-PACK-001`.

**Precondition:** an authorized root contains a small Python project.

**Steps:**

1. The user opens the explorer in the initial state.
2. The user opens project selection and chooses a directory inside an authorized
   root.
3. The product validates and shows the project-relative selection plus default
   exclusions.
4. The user starts analysis.
5. The product announces queued and active phases with progress and a cancel
   action.
6. The product completes and summarizes included, excluded, and diagnosed files,
   entities, and relationships.
7. The user explores the result with graph or text/table navigation and uses fit
   or reset view.

**Outcome:** a completed result is visible with deterministic identities and no
source execution or network data egress.

## `J-02` Analyze a project containing syntax errors

**Primary users:** developer, maintainer, reviewer.

**Requirements:** `FR-ANALYZE-003`, `FR-ERROR-001`, `FR-ERROR-002`,
`FR-STATE-001`, `NFR-SEC-003`, `NFR-REL-001`, `NFR-TEST-001`.

**Precondition:** an authorized project contains valid files and at least one
Python file that cannot be parsed.

**Steps:**

1. The user selects and starts analysis.
2. The product scans the eligible files and encounters a syntax error during
   parsing.
3. The product records a diagnostic tied to a safe project-relative path and
   available source position.
4. Analysis continues for independent eligible files.
5. The terminal state becomes partially completed when valid results exist.
6. The user opens the diagnostics panel and then the affected file detail.

**Outcome:** valid results remain usable, the invalid file is not silently
omitted, and the interface never labels the result complete.

## `J-03` Analyze a large project

**Primary users:** unfamiliar-project developer, maintainer.

**Requirements:** `FR-SCAN-002`, `FR-SCAN-003`, `FR-JOB-001`, `FR-JOB-002`,
`FR-SCALE-001`, `NFR-SEC-004`, `NFR-PERF-001`, `NFR-RESP-001`.

**Precondition:** an authorized project is expected to approach a configured
resource or visualization complexity limit.

**Steps:**

1. The user selects the project and reviews estimated scope and exclusions.
2. The user starts analysis and observes phase, completed count, known total, and
   active policy limits.
3. If a scan limit is reached, the product records which policy category stopped
   further work without exposing unauthorized locations.
4. Before rendering an over-limit graph, the product presents a large-result
   warning, a text/table path, and bounded scope or aggregation choices.
5. The user narrows to selected directories or entity/relationship categories.
6. The product renders the bounded view without changing the underlying result's
   completion label.

**Outcome:** the user retains control and can understand scope, limits, and
partiality without an unresponsive full-graph attempt.

## `J-04` Search for a class or function

**Primary users:** developer, reviewer, student.

**Requirements:** `FR-ANALYZE-001`, `FR-SEARCH-001`, `NFR-RESP-001`,
`NFR-A11Y-001`.

**Precondition:** a completed, partial, or compatible cached result is open.

**Steps:**

1. The user focuses search by keyboard or pointer.
2. The user enters a short or qualified class/function name.
3. The interface reports the result count and highlights matches in the graph and
   text/table representation without hiding nonmatches unexpectedly.
4. The user moves through results with next/previous controls or a result list.
5. The user selects the intended qualified result.

**Outcome:** focus moves to the same selected entity in every representation and
its details are available.

## `J-05` Filter dependency types

**Primary users:** maintainer, reviewer.

**Requirements:** `FR-ANALYZE-002`, `FR-FILTER-001`, `NFR-A11Y-001`.

**Precondition:** an open result contains more than one relationship category or
resolution state.

**Steps:**

1. The user opens relationship filters.
2. The user selects dependency and inheritance while excluding practical calls.
3. The interface updates visual and text/table representations and announces the
   visible count.
4. The user includes only resolved relationships above a chosen confidence
   category.
5. The user clears filters to restore the prior complete result view.

**Outcome:** filters change presentation only and do not imply that hidden data
was absent from analysis.

## `J-06` Inspect an entity or relationship and its source evidence

**Primary users:** developer, maintainer, reviewer, student.

**Requirements:** `FR-ANALYZE-003`, `FR-GRAPH-001`, `FR-DETAIL-001`,
`NFR-A11Y-001`.

**Precondition:** an analyzed result contains a selectable entity or relationship.

**Steps:**

1. The user selects an item in the graph or text/table representation.
2. A details region identifies the item, its qualified name or endpoints, type,
   resolution state, confidence, and connected items.
3. The user opens an evidence entry.
4. The interface shows a project-relative path, line/column range when available,
   and a bounded source excerpt or an explicit reason evidence is unavailable.
5. The user moves to the next connected relationship without losing context.

**Outcome:** the user can explain what the product observed and what it inferred,
without being shown an unauthorized absolute path.

## `J-07` Cancel an analysis

**Primary users:** all users.

**Requirements:** `FR-JOB-002`, `FR-STATE-001`, `NFR-RESP-001`, `NFR-REL-001`.

**Precondition:** a job is queued or in an active analysis phase.

**Steps:**

1. The user invokes Cancel.
2. The interface acknowledges the request and prevents duplicate cancellation.
3. The product stops at a safe boundary and transitions to cancelled.
4. The summary states that the output is incomplete and distinguishes retained
   provisional information from a reusable completed result.
5. The user may return to project selection or start a fresh analysis.

**Outcome:** exactly one cancelled terminal state is announced, and incomplete
data is never presented as complete or cached as a completed analysis.

## `J-08` Retry after a recoverable failure

**Primary users:** developer, maintainer.

**Requirements:** `FR-ERROR-001`, `FR-ERROR-002`, `FR-REFRESH-001`,
`NFR-REL-001`.

**Precondition:** a job failed or partially completed for a condition described as
recoverable.

**Steps:**

1. The user reviews the diagnostic summary, affected scope, and suggested safe
   action.
2. The user corrects the external condition, adjusts a policy-permitted scope, or
   leaves the project unchanged.
3. The user invokes Retry.
4. The product validates authorization again and starts a distinct attempt.
5. The new attempt reaches its own terminal state while the prior diagnostic
   record remains distinguishable.

**Outcome:** retry is explicit, auditable to the user, and does not silently merge
incompatible attempts.

## `J-09` Return to a cached analysis

**Primary users:** developer, maintainer, reviewer.

**Requirements:** `FR-STATE-001`, `FR-REFRESH-001`, `FR-COMPAT-001`,
`NFR-PRIV-001`, `NFR-DETER-001`, `NFR-BACK-001`.

**Precondition:** an authorized compatible cache entry exists for the selected
project.

**Steps:**

1. The user returns to the project.
2. The product revalidates project authorization before offering cached data.
3. The interface shows cache age, analyzed scope, configuration, analyzer/contract
   compatibility, and known staleness.
4. The user opens the cached result or chooses fresh analysis.
5. If opened, the interface announces cached-result-loaded and retains a visible
   Refresh action.

**Outcome:** the user knows the result is cached and can deliberately refresh it;
an unauthorized or incompatible cache is not exposed.

## `J-10` Handle an unauthorized or invalid project path

**Primary users:** all users.

**Requirements:** `FR-SCAN-001`, `FR-ERROR-002`, `FR-STATE-001`,
`NFR-SEC-001`, `NFR-SEC-002`, `NFR-SEC-004`, `NFR-PLAT-001`,
`NFR-TEST-001`.

**Precondition:** the selection is nonexistent, not a directory, outside an
authorized root, or resolves outside through a link or junction.

**Steps:**

1. The user selects or submits the location.
2. The product canonicalizes and validates it before scanning any child.
3. The product rejects the selection and transitions to validation failed.
4. The interface explains the safe reason category, such as “outside authorized
   locations” or “link target not permitted,” without displaying a protected
   canonical path.
5. Focus moves to the correction action, and the user can select another project.

**Outcome:** no file inside the rejected location is read, no cached data for it
is revealed, and the user has a safe recovery path.

## Journey coverage

| Journey | Primary state path | Main observable result |
| --- | --- | --- |
| `J-01` | Initial → Project selected → Queued → Scanning → Parsing → Resolving → Graph building → Completed | Usable small-project result |
| `J-02` | Project selected → active phases → Partially completed | Valid results plus syntax diagnostic |
| `J-03` | Project selected → active phases → Completed or Partially completed | Bounded large-result exploration |
| `J-04` | Completed/Partial/Cached → search interaction | Matching entity selected |
| `J-05` | Completed/Partial/Cached → filter interaction | Relationship subset displayed |
| `J-06` | Completed/Partial/Cached → selection | Evidence and confidence understood |
| `J-07` | Queued/active phase → Cancelled | One explicit cancelled outcome |
| `J-08` | Failed/Partial → Project selected → new attempt | Recoverable retry outcome |
| `J-09` | Project selected → Cached result loaded | Clearly labeled reusable result |
| `J-10` | Initial/Project selected → Validation failed | Rejected before scan |

## Assumptions and open journey decisions

- The project selector can communicate authorization without asking users to type
  unrestricted server filesystem paths. The interaction mechanism is deferred.
- “Cancel” may be cooperative rather than immediate, but the acknowledgement and
  final state must remain clear. The technical cancellation boundary is deferred.
- Cached-result discovery must not reveal project names or paths before
  authorization. Cache presentation details are deferred.
- Source excerpts may need configurable redaction. The product owner must decide
  whether excerpts are enabled by default.
- User research must determine whether students need a separate learning mode or
  whether contextual explanations are sufficient.
- Future Thonny use should reuse these journeys where possible, but editor-specific
  commands, panels, and source navigation are outside Phase 4.
