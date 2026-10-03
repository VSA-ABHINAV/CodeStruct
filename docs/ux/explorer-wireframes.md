# CodeStruct explorer wireframes

## Purpose and constraints

These text wireframes describe information hierarchy, states, and interaction
outcomes for the requirements in [product-requirements.md](../product-requirements.md).
They are implementation-neutral: boxes are regions, not prescribed components,
and labels do not select a frontend framework or graph technology.

The current prototype has one Analyze button and a React Flow canvas. Everything
else below is required or proposed UX, not implemented behavior.

## Global information architecture

```text
+--------------------------------------------------------------------------------+
| CodeStruct                                      [Project] [Status] [Help]       |
+----------------------+--------------------------------------+------------------+
| Project and scope    | Search and filters                   | Analysis summary |
| - selected project   | [Search________________] [Results 0] | state, age, scope|
| - exclusions         | Entities [..] Relationships [..]    | counts, warnings |
| - analyze/refresh    | Resolution [..] Confidence [..]      | diagnostics link |
+----------------------+--------------------------------------+------------------+
| View: [Graph] [Table]          [Zoom -/+] [Fit] [Reset] [Reduced motion]       |
|                                                                                |
|                         GRAPH OR TEXT/TABLE VIEW                               |
|                                                                                |
+------------------------------------------------------+-------------------------+
| Diagnostics summary and selected warnings           | Details and evidence    |
| [Open diagnostics]                                  | identity, connections   |
|                                                      | source, confidence      |
+------------------------------------------------------+-------------------------+
| Live status / accessible announcements                                          |
+--------------------------------------------------------------------------------+
```

The Graph and Table controls switch equivalent exploration representations. The
table is not a secondary export; it is a first-class path for keyboard, screen-
reader, low-vision, and dense-result workflows.

## Project-selection region

### Initial

```text
+-- Analyze a Python project -----------------------------------------------------+
| No project selected.                                                           |
|                                                                                |
| [Choose from authorized locations]                                             |
|                                                                                |
| CodeStruct reads Python source as data and does not execute it.                 |
| Default exclusions: secrets, environments, dependencies, generated files, VCS |
+--------------------------------------------------------------------------------+
```

### Project selected

```text
+-- Project ---------------------------------------------------------------------+
| Selected: workspace/my-project                     [Choose another]             |
| Authorization: Valid                                                        ✓  |
| Estimated eligible files: 84              Excluded: 1,942 [Review exclusions]   |
| Policy: 10,000 files · 2 MiB/file · depth 40 · time/memory limits configured   |
|                                                                                |
| [Analyze project]     [Open compatible cache: 2 hours old]                      |
+--------------------------------------------------------------------------------+
```

### Validation failed

```text
+-- Project selection needs attention -------------------------------------------+
| The location is outside the authorized project roots.                          |
| No files were read. Protected filesystem details are hidden.                   |
|                                                                                |
| [Choose another project]                                      [Policy help]     |
+--------------------------------------------------------------------------------+
```

The message states the safe reason category and whether any data was read. It
must not echo an unauthorized canonical path, link target, username, or secret
directory name.

## Progress and cancellation region

```text
+-- Analyzing workspace/my-project ----------------------------------------------+
| Phase 3 of 4: Resolving relationships                                           |
| [=======================-----------] 6,430 / 8,120 items                        |
| 1 diagnostic · elapsed 00:18 · limits available in details                     |
|                                                                                |
| [Cancel analysis]                                                              |
|                                                                                |
| Live update: Resolving relationships, 79 percent complete.                     |
+--------------------------------------------------------------------------------+
```

If the total is unknown, use completed work and an indeterminate indicator rather
than a false percentage. After cancellation is requested, the action becomes
disabled and the copy changes to “Stopping safely…”. The final state must say
Cancelled and must not imply that provisional results are complete.

## Search and filter region

```text
+-- Find and narrow --------------------------------------------------------------+
| Search [UserService____________________________________] [Clear]                |
| 3 matches                        [Previous] [Next]                               |
|                                                                                |
| Entity types       Relationship types     Resolution       Confidence           |
| [x] Module         [x] Dependency         [x] Resolved     [x] High              |
| [x] File           [x] Inheritance        [x] Unresolved   [x] Medium            |
| [x] Class          [ ] Practical call     [x] Syntactic    [ ] Low               |
| [x] Function                                                                  |
| [x] Method         [Clear all filters]                                         |
|                                                                                |
| Showing 46 of 192 entities and 31 of 488 relationships.                        |
+--------------------------------------------------------------------------------+
```

Search does not silently apply a filter. Matches are emphasized while the
surrounding context remains visible unless the user explicitly chooses a narrowed
result view. Filter summaries state hidden and visible counts. Each relationship
type also has a text label and line/pattern cue; color is supplementary.

## Interactive graph region

```text
+-- Structure view ---------------------------------------------------------------+
| [Graph selected] [Table]       [Zoom out] [Zoom in] [Fit] [Reset view]          |
|                                                                                |
|        ┌ module: app.user ┐   imports / resolved / high   ┌ module: app.db ┐   |
|        │ UserService     │ ─────────────────────────────> │ Database       │   |
|        │ User            │                                └─────────────────┘   |
|        │ Admin           │                                                        |
|        └─────────────────┘                                                        |
|                 △ inherits / resolved / high                                    |
|                 │                                                               |
|            ┌ class: Admin ┐                                                     |
|            └──────────────┘                                                     |
|                                                                                |
| Selected: app.user.UserService · use arrow keys to move among connected items  |
+--------------------------------------------------------------------------------+
```

Required interaction outcomes:

- Pointer and keyboard users can pan, zoom, fit, reset, select, and move among
  connected items.
- Fit and reset are distinct: Fit frames the current visible result, while Reset
  restores the documented initial view for the active scope.
- Selection survives view controls and policy-permitted filter changes when the
  selected item remains visible.
- Relationship labels identify type, resolution state, and confidence without
  relying on animation or color.
- Reduced-motion preference disables nonessential animation.
- A status description explains current selection and visible counts outside the
  canvas.

## Text/table representation

```text
+-- Structure table --------------------------------------------------------------+
| Entity / relationship        Type         State       Confidence   Evidence     |
| app.user                     Module       —           —            user.py      |
| app.user.UserService         Class        —           —            user.py:4    |
| app.user -> app.database     Dependency   Resolved    High         user.py:1    |
| app.user.Admin -> app.User   Inheritance  Resolved    High         user.py:17   |
| app.user.get_user -> ...     Call         Syntactic   Low          user.py:8    |
|                                                                                |
| [Previous page] Page 1 of 8 [Next page]  [Open selected details]                |
+--------------------------------------------------------------------------------+
```

The exact paging or windowing mechanism is deferred. The representation must
preserve search, filters, selection, evidence access, and relationship semantics.

## Details and source-evidence region

### Entity selected

```text
+-- Details ---------------------------------------------------------------------+
| Class · app.user.UserService                                      [Close]       |
| Project path: app/user.py                                                       |
| Definition: lines 4–10                                                         |
|                                                                                |
| Contains: get_user()                                                           |
| Incoming: 2 relationships             Outgoing: 3 relationships                |
| Related diagnostics: None                                                      |
|                                                                                |
| [Show connected items] [Open source evidence]                                  |
+--------------------------------------------------------------------------------+
```

### Relationship selected

```text
+-- Relationship evidence --------------------------------------------------------+
| app.user → app.database                                                        |
| Type: Dependency     State: Resolved     Confidence: High                       |
| Origin: Static source observation                                               |
|                                                                                |
| Evidence 1 of 1                                                                |
| app/user.py:1:1–1:16                                                           |
| 1  import database                                                             |
|                                                                                |
| Why this confidence: the imported module resolved to one included module.       |
| [Previous evidence] [Next evidence] [Show endpoint details]                     |
+--------------------------------------------------------------------------------+
```

If source evidence is unavailable, the same location contains a reason such as
“No source position was produced by this analysis,” not an empty panel. Excerpts
are bounded, text-selectable, and labeled by language; full absolute paths remain
hidden from ordinary UI output.

## Diagnostics region

```text
+-- Diagnostics (3) --------------------------------------------------------------+
| Filter: [All severities] [All phases] [All files]                               |
|                                                                                |
| Error   PARSE_SYNTAX       src/legacy.py:42:8      [Open details]               |
| Warning IMPORT_UNRESOLVED  src/service.py:7:1      [Show evidence]              |
| Info    FILE_EXCLUDED      .venv/...               [Show safe reason]           |
|                                                                                |
| Result: Partially completed · 81 of 82 eligible files analyzed                 |
| [Retry analysis] [Change scope]                                                 |
+--------------------------------------------------------------------------------+
```

Diagnostics use stable user-facing categories, severity text, phase, safe path,
location when available, consequence, and a recovery action. Stack traces and
unauthorized paths are not shown in the default user view. Selecting a diagnostic
synchronizes the details and graph/table selection when the referenced item
exists.

## Large-result warning and aggregation controls

```text
+-- This result is too complex for a useful full graph ---------------------------+
| 28,400 entities · 91,200 relationships · exceeds current display policy         |
| The analysis result is retained; only the initial presentation is bounded.      |
|                                                                                |
| Start with                                                                     |
| (•) Package/directory overview                                                  |
| ( ) Selected directories [Choose]                                               |
| ( ) Relationship type [Dependency v]                                            |
| ( ) Text/table result                                                           |
|                                                                                |
| Maximum visible entities [500 v]     Maximum visible relationships [1,500 v]   |
| [Open bounded view] [Cancel]                                                     |
+--------------------------------------------------------------------------------+
```

Numeric defaults in this example are illustrative placeholders, not approved
requirements. Phase 5 must use the benchmark and product policy to choose actual
limits. The UI always states whether a control changes analysis scope, result
scope, or presentation only.

## Completion-state summaries

### Completed

```text
Completed · 82 files · 418 entities · 705 relationships · 0 blocking diagnostics
[Explore result] [Analyze again] [Refresh]
```

### Partially completed

```text
Partially completed · 81 of 82 files analyzed · 1 error · usable results retained
[Explore available result] [Open diagnostics] [Retry]
```

### Failed

```text
Analysis failed · no usable result was produced
Reason: the configured file-count policy was exceeded before analysis could start.
[Change scope] [Retry] [Return to project selection]
```

### Cancelled

```text
Cancelled by user · incomplete provisional data is not labeled as a completed result
[Start again] [Return to project selection]
```

### Cached result loaded

```text
Cached result · analyzed 2 hours ago · scope and configuration unchanged
[Explore cached result] [Refresh now] [Review cache details]
```

## State model and transition coverage

The required product-state vocabulary maps to the detailed lifecycle states below.
This mapping keeps transport and result conditions explicit while allowing the
progress display to show finer-grained analysis phases.

| Required product state | Detailed state or presentation |
| --- | --- |
| No project selected | Initial |
| Ready | Project selected and authorized |
| Analyzing | Queued, Scanning, Parsing, Resolving, or Graph building |
| Success | Completed with one or more included results |
| Empty result | Completed with zero included results and an explanatory empty-state panel |
| Partial result | Partially completed |
| Invalid path | Validation failed because the path is missing, malformed, or outside an allowed project type |
| Permission denied | Validation failed or Failed with a safe authorization/read diagnostic |
| Malformed request | Validation failed before job creation, with field-level correction guidance |
| Malformed response | Failed integration state that preserves the current view and reports an incompatible or invalid payload |
| Backend unavailable | Failed connection state with Retry and configuration guidance |
| Cancelled | Cancelled |
| Oversized or slow analysis | Analyzing warning or bounded-result warning with Cancel, scope, aggregation, and text-view actions |

| State | Entry condition | Required presentation | Primary next actions |
| --- | --- | --- | --- |
| Initial | No accepted project | Product purpose, static-analysis safety statement, Choose action | Choose project |
| Project selected | Selection authorized and policy summary available | Safe project-relative label, scope estimate, exclusions, limits, cache choice | Analyze, choose another, open cache |
| Validation failed | Selection rejected before scan | Safe reason, confirmation no unauthorized read occurred, correction focus | Choose another, view policy help |
| Queued | Analysis accepted but not started | Queue state, job identity in accessible status, Cancel | Cancel, wait |
| Scanning | Filesystem discovery active | Phase, completed count, known total if available, exclusions and limits | Cancel, inspect progress details |
| Parsing | Eligible source parsing active | Phase, counts, accumulated diagnostics without premature completion | Cancel, inspect diagnostics |
| Resolving | Entity/relationship resolution active | Phase, counts, unresolved count when known | Cancel, inspect progress |
| Graph building | Presentation/result relationships being prepared | Phase and scope; do not imply canvas is ready | Cancel, inspect progress |
| Completed | All in-scope work completed within policy | Counts, duration, exclusions, diagnostics, cache status | Explore, refresh, analyze again |
| Partially completed | Useful results plus one or more file/limit failures | Clear partial label, affected scope, retained result, diagnostics | Explore available, retry, change scope |
| Failed | No usable result | Safe reason and recovery choices | Retry, change scope, select project |
| Cancelled | Cancellation reaches safe terminal boundary | Explicit incomplete label and cache consequence | Start again, select project |
| Cached result loaded | Authorized compatible cache opened | Age, scope, configuration, version, staleness, Refresh | Explore, refresh |

Allowed high-level transitions:

```text
Initial -> Project selected | Validation failed
Validation failed -> Project selected | Initial
Project selected -> Queued | Cached result loaded | Initial
Queued -> Scanning | Cancelled | Failed
Scanning -> Parsing | Partially completed | Cancelled | Failed
Parsing -> Resolving | Partially completed | Cancelled | Failed
Resolving -> Graph building | Partially completed | Cancelled | Failed
Graph building -> Completed | Partially completed | Cancelled | Failed
Completed -> Queued | Project selected | Cached result loaded
Partially completed -> Queued | Project selected
Failed -> Queued | Project selected
Cancelled -> Queued | Project selected
Cached result loaded -> Queued | Project selected
```

An implementation may add internal substates, but user-visible transitions must
not skip the distinction among complete, partial, failed, cancelled, and cached.

## Accessibility behavior

1. Every action and region has an accessible name and predictable keyboard order.
2. Visible focus meets contrast requirements and is not obscured by the graph.
3. Graph nodes and edges have equivalent table rows and detail access.
4. Relationship type, state, direction, and confidence use text and shape/pattern
   cues; color alone never carries meaning.
5. Default and interactive content meets WCAG 2.2 AA contrast.
6. System and user reduced-motion preferences remove animated edges, nonessential
   transitions, and motion-heavy focus behavior.
7. Progress updates use a polite live region; validation failures, terminal
   states, and blocking errors receive assertive announcements without repetition.
8. Search result counts, filter changes, selection, and hidden-item counts are
   announced without moving focus unexpectedly.
9. Canvas-only gestures have button and keyboard alternatives.
10. Source evidence remains selectable text with line numbers available to
    assistive technology without being read redundantly on every navigation step.

## Responsive and large-content behavior

At narrower widths, Project/Scope, Explorer, Details, and Diagnostics become
ordered regions or views rather than squeezed sidebars. Selection persists when a
region is opened or closed. The graph is never the only route to details. Long
qualified names wrap or truncate with an accessible full value, and zooming the
browser does not hide primary actions or create two-dimensional page scrolling
for ordinary workflows.

## Open UX decisions

- Authorized project-selection mechanism and administrator-policy visibility.
- Default Graph versus Table view by persona and result size.
- In-root link disclosure and representation.
- Confidence labels and explanations validated by user research.
- Large-result complexity metric and approved default bounds.
- Source excerpt length, redaction, and external-editor handoff.
- Cache entry discovery, retention controls, and stale-change detection language.
- Whether education help is contextual or a distinct post-MVP mode.
- Supported screen-reader/browser combinations and graph keyboard navigation
  pattern.
