# CodeStruct MVP acceptance criteria

## Purpose and rules

These criteria cover every Must requirement in
[product-requirements.md](../product-requirements.md). Each criterion is phrased
as an observable Given/When/Then scenario and avoids prescribing internal
implementation. Passing these criteria does not waive the pending Phase 2 pytest,
Ruff, and mypy prerequisite.

## Functional acceptance criteria

### `AC-FR-SCAN-001` — authorized project selection

**Given** configured authorized roots and selections that are valid, nonexistent,
and outside those roots, **when** each selection is submitted, **then** only the
valid contained directory reaches Project selected, rejected selections reach
Validation failed, and no child of a rejected location is read.

### `AC-FR-SCAN-002` — recursive scanning and identity

**Given** an authorized project with Python files at multiple depths and repeated
basenames in different directories, **when** analysis completes, **then** every
included file appears once with a distinct project-relative identity and its
module containment is distinguishable.

### `AC-FR-SCAN-003` — exclusions

**Given** files matched by product defaults, project ignore rules, and permitted
session choices, **when** the project is scanned, **then** excluded files are not
parsed, the exclusion summary reports counts by reason, and a session choice
cannot weaken enforced security exclusions or limits.

### `AC-FR-ANALYZE-001` — entity coverage

**Given** source containing a module, file, class, function, async function,
method, nested function, and import, **when** analysis completes, **then** each
supported entity is listed with its type, qualified identity, and correct
containment without collapsing equal short names from different scopes.

### `AC-FR-ANALYZE-002` — relationship semantics

**Given** source examples containing resolvable and unresolvable dependencies,
inheritance, constructors, direct calls, and chained calls, **when** analysis
completes, **then** supported relationships are classified by type and resolution
state, unresolved or syntactic observations remain visibly qualified, and no
unsupported observation is presented as a resolved call.

### `AC-FR-ANALYZE-003` — evidence and confidence

**Given** relationships with direct source evidence, ambiguous evidence, and no
available location, **when** each relationship is inspected, **then** the product
shows type, origin, confidence category, safe project-relative evidence when
available, and an explicit reason when evidence or confidence cannot be supplied.

### `AC-FR-JOB-001` — progress

**Given** an analysis that lasts long enough for each phase to be observed,
**when** it proceeds, **then** the interface exposes queued, scanning, parsing,
resolving, and graph-building phases in order, reports completed work and known
total where available, and announces meaningful progress accessibly.

### `AC-FR-JOB-002` — cancellation

**Given** jobs cancelled while queued and during each active phase, **when** the
user requests cancellation, **then** the request is acknowledged once, each job
reaches Cancelled, incomplete data is not labeled complete, and no completed
cache entry is created from the cancelled attempt.

### `AC-FR-ERROR-001` — partial results

**Given** an authorized project with independently valid files and one unreadable
or syntactically invalid file, **when** analysis runs, **then** valid files remain
in the result, the affected file receives a diagnostic, and the terminal state is
Partially completed rather than Completed.

### `AC-FR-ERROR-002` — diagnostics

**Given** syntax, permission, unsupported-file, missing-dependency, policy-limit,
and unrecoverable analysis failures, **when** the user opens diagnostics, **then**
each condition has a stable category, consequence, safe location when permitted,
and relevant recovery action without exposing a protected canonical path.

### `AC-FR-GRAPH-001` — view navigation

**Given** a rendered result and a selected entity, **when** keyboard and pointer
users pan, zoom, fit, and reset the view, **then** every operation is available by
both input modes, has a visible focus state and accessible name, and retains the
selection whenever the selected entity remains in scope.

### `AC-FR-SEARCH-001` — search

**Given** entities with repeated short names and distinct qualified names, **when**
the user searches by a partial short name and then a qualified name, **then** the
result count and matches are consistent in graph and table, next/previous
navigation reaches each match, and selection resolves to the intended identity.

### `AC-FR-FILTER-001` — filtering

**Given** a result containing multiple entity types, relationship types,
resolution states, and confidence categories, **when** filters are applied and
cleared, **then** graph and table show the same subset and visible/hidden counts,
the underlying result is not reanalyzed, and hidden data is not described as
absent.

### `AC-FR-DETAIL-001` — details and evidence

**Given** a selectable entity and relationship, **when** each is selected from
graph and table, **then** the same details show identity, type, connections,
project-relative path, available source range, evidence, confidence, and related
diagnostics, with an explicit unavailable value for missing evidence.

### `AC-FR-STATE-001` — distinct UI states

**Given** controlled scenarios that lead to initial, project selected, validation
failed, queued, scanning, parsing, resolving, graph building, completed, partially
completed, failed, cancelled, and cached-result-loaded, **when** each scenario is
run, **then** the visible heading, available actions, summary, and accessible
announcement uniquely identify the current state.

### `AC-FR-SCALE-001` — large-project presentation

**Given** a completed or partial result above the configured visualization
complexity limit, **when** exploration begins, **then** the product does not
attempt an unbounded full graph, shows the measured reason and current limit,
offers bounded scope or aggregation controls and a complete text alternative,
and labels whether each control changes analysis or presentation.

### `AC-FR-REFRESH-001` — repeat, refresh, and cache

**Given** an authorized project with a compatible cache and then a detected stale
or incompatible condition, **when** the user returns, repeats, or refreshes,
**then** cache age, scope, configuration, and compatibility are visible, fresh
analysis is a deliberate action, and stale or incompatible data is never silently
presented as current.

### `AC-FR-COMPAT-001` — migration compatibility

**Given** the characterized legacy consumer and old and new supported response
variants, **when** migration compatibility tests run, **then** the legacy consumer
receives its required `files` and `dependencies` fields with characterized types
and meanings until the exit condition, while an unsupported variant produces an
explicit compatibility failure rather than reinterpreted data.

## Security, privacy, and quality acceptance criteria

### `AC-NFR-SEC-001` — path canonicalization and containment

**Given** valid contained paths plus traversal, separator, case, nonexistent,
file-not-directory, and outside-root variants on each supported platform, **when**
selection validation runs, **then** only canonical directories contained by an
authorized root are accepted and all rejected cases read zero children.

### `AC-NFR-SEC-002` — symlinks and junctions

**Given** symbolic links, junctions, and reparse points that resolve inside,
outside, ambiguously, or cyclically relative to an authorized root, **when** the
scanner encounters them, **then** the documented policy is applied
deterministically, no unproven or outside target is read, and a redacted
diagnostic explains each rejection.

### `AC-NFR-SEC-003` — no source execution

**Given** analyzed files whose top-level statements, imports, decorators,
annotations, and build hooks would create observable side effects if executed,
**when** static analysis completes or fails, **then** none of those effects occurs
and no analyzed module or project command is invoked.

### `AC-NFR-SEC-004` — resource limits and sensitive exclusions

**Given** projects that separately exceed configured file-count, file-size,
depth, elapsed-time, and memory limits and contain each default sensitive or
generated category, **when** analysis runs, **then** each limit stops work at the
defined boundary, protected categories are not read, valid retained results lead
to Partial rather than Complete, and user-visible details contain no unauthorized
canonical path or secret value.

### `AC-NFR-PRIV-001` — local data privacy

**Given** an offline-instrumented analysis containing unique source markers and
paths, **when** the complete select-analyze-explore-cache workflow runs with
default settings, **then** network observation finds no source, path, result, or
cache-data egress and only locally authorized users can reopen the cached result.

### `AC-NFR-PERF-001` — performance baseline

**Given** an approved representative corpus for small, medium, large, and
policy-limit projects, **when** the release benchmark is run in the documented
environment, **then** median and 95th-percentile phase and total duration, peak
memory, and result size are recorded, reproducible, and reviewed before numeric
MVP targets are approved.

### `AC-NFR-RESP-001` — responsiveness baseline

**Given** representative result sizes and the supported interaction matrix,
**when** selection feedback, cancellation acknowledgement, search, filtering,
graph controls, table navigation, and details opening are measured, **then** the
results and environment are recorded and reviewed before thresholds are approved,
and operations exceeding the approved immediate threshold expose progress.

### `AC-NFR-REL-001` — terminal-state reliability

**Given** success, per-file failure, policy-limit, cancellation, timeout, and
unrecoverable fault injection in every analysis phase, **when** each job settles,
**then** it reaches exactly one of Completed, Partially completed, Failed, or
Cancelled, preserves valid results where permitted, and never changes terminal
meaning without a new attempt.

### `AC-NFR-A11Y-001` — accessibility

**Given** the MVP journeys, **when** automated WCAG checks and manual keyboard,
screen-reader, zoom, contrast, and reduced-motion tests run against supported
combinations, **then** every journey is completable without pointer or graph-only
interaction, focus is visible, relationships have non-color labels, graph data
has a text/table equivalent, and errors and progress are announced correctly at
WCAG 2.2 AA.

### `AC-NFR-PLAT-001` — cross-platform behavior

**Given** the supported Windows, macOS, and Linux matrix with platform-specific
path, case, separator, symlink, junction where applicable, permission, and
encoding fixtures, **when** smoke and security-path suites run, **then** supported
workflows pass and intentional platform differences match documented policy.

### `AC-NFR-DETER-001` — deterministic output

**Given** unchanged source, configuration, authorization, and analyzer version,
**when** analysis is repeated ten times, **then** semantic identities, ordering,
relationships, diagnostics, and completion state are equal across all runs.

### `AC-NFR-TEST-001` — testability and release prerequisite

**Given** all Must requirements and the Phase 2 quality configuration, **when** an
MVP release candidate is evaluated, **then** each feasible criterion maps to an
automated test, manual accessibility/usability procedures are recorded, and
pytest, Ruff format, Ruff lint, and mypy have actually run and passed rather than
being inferred from configuration.

### `AC-NFR-BACK-001` — legacy contract preservation

**Given** frozen examples from the current `GET /analyze` contract, **when** each
supported migration release is tested, **then** required top-level, file,
inheritance, call-variant, and dependency fields retain their required types and
characterized meanings, or the release is rejected until the announced removal
condition is met.

### `AC-NFR-PACK-001` — installation and startup

**Given** a clean supported environment after following documented installation,
**when** the application is started from the repository root and from an unrelated
working directory using the documented entry point, **then** both starts expose
the same health and analysis behavior without manual `PYTHONPATH` or working-
directory changes.

## Coverage summary

| Category | Must requirement count | Acceptance criterion count | Coverage |
| --- | ---: | ---: | --- |
| Functional | 18 | 18 | Complete in this specification |
| Non-functional | 14 | 14 | Complete in this specification |
| Total MVP | 32 | 32 | Complete in this specification |

Specification coverage does not mean implementation or test execution coverage.
The Phase 5 design and later implementation must retain these IDs or provide an
explicit supersession map.

## Open acceptance decisions

- Approved representative benchmark corpus and test environment.
- Numeric performance, responsiveness, resource, and complexity limits after
  baseline measurement.
- Exact authorized-root administration and cache-authorization test identities.
- Default policy for links that resolve inside an authorized root.
- Supported browser, screen reader, operating system, and filesystem matrix.
- Legacy-contract exit condition and migration duration.
- Product-approved confidence vocabulary and practical-call support boundary.
