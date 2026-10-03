# Phase 11 automated test results

## Environment and installation

- Windows, Python 3.14.6, Node.js 24.18.0, npm 11.11.0.
- Repository-local environment: `python -m venv .venv`, repaired with
  `.venv\Scripts\python -m ensurepip`, then
  `.venv\Scripts\python -m pip install -e ".[dev]"`.
- Installed quality tools: pytest 9.1.1, pytest-cov 7.1.0, coverage 7.16.0,
  Ruff 0.16.7, and mypy 1.20.2.
- Frontend tooling was installed with npm (not globally), and npm generated the
  lockfile update: Vitest 5.0.0, Testing Library, user-event, jsdom,
  `@vitest/coverage-v8`, and `vitest-axe`. npm reported zero known vulnerabilities.
- The declared `httpx2>=0.1,<1.0` range had no valid distribution. It was corrected
  to `>=2,<3`, matching the installed Starlette test-client requirement.

## Pre-change baseline

With normal Windows ACLs, the original backend suite collected 61 tests: 60
passed, one link test skipped for unavailable account privileges, and coverage
was 84.64%. The sandboxed run produced temporary-directory permission errors,
confirmed environmental by the successful normal-ACL rerun. The original 18
frontend logic tests passed. Ruff formatting and linting failed on pre-existing
format/import debt (69 lint findings under the expanded rules), and mypy reported
48 errors across 11 files.

## Final automated results

The final values in this section are populated from the closing validation run:

- Backend: **73 passed, 1 skipped** (Windows link privilege unavailable), with
  no failures in 6.60 seconds.
- Backend coverage: **85.57% combined** with branch measurement; the 84% gate
  passed.
- Ruff format check and lint (including import, bugbear, and security families):
  **passed** across backend, tests, and sample project.
- mypy: **passed, 40 source files checked**.
- Frontend logic/component/accessibility: **42 passed in four files**; the focused
  accessibility selection passed one test containing two axe scans, with 41
  non-accessibility tests explicitly skipped by the name filter.
- Frontend coverage baseline: **73.86% statements, 63.39% branches, 70.27%
  functions, and 76.99% lines** across the consolidated logic/component suite;
  initial gates are 70/60/65/75 respectively.
- ESLint: **passed**; no-write Vite build: **passed**, 195 modules transformed.
- Process/cache/restart/platform selection: **6 passed, 1 privilege-dependent
  skip, 67 deselected**; cache/restart/pagination remain covered by the full run.
- Controlled benchmark: **passed and cleaned its generated output**. The 303-file
  median was 94.949 ms scan, 1551.754 ms parse, 1748.138 ms resolve/build,
  187.993 ms validate, 898.975 ms serialize, 316.122 ms SQLite write, and
  229.572 ms read; the 1,515-file informational run used 80.915 MiB peak memory.

The component suite mocks React Flow only at `ArchitectureGraph`, its renderer
boundary. Two representative explorer states run axe. jsdom does not implement
canvas color measurement, so these scans are not contrast evidence and complete
WCAG 2.2 AA certification remains explicitly manual.

Known tool warnings are retained rather than suppressed: Starlette emits an
upstream AnyIO alias deprecation, and jsdom reports that canvas `getContext` is
unimplemented during axe's contrast probe. An intermittent SQLite ResourceWarning
in the combined run did not reproduce when the API and lock tests were each run
with `ResourceWarning` promoted to an error; it remains a watch item.

## Confirmed defects and scoped corrections

1. The invalid `httpx2` range prevented a reproducible development install; the
   version constraint was corrected without adding a new dependency category.
2. The cancel route relied on `assert updated is not None`, which can disappear
   under optimized Python; it now returns the existing safe not-found envelope.
3. The AST keyword-only argument/default pairing now uses `zip(..., strict=True)`
   so an internal shape violation cannot silently truncate metadata.
4. Narrow type annotations exposed and clarified JSON, multiprocessing, repository
   protocol, and optional-module boundaries without changing graph semantics.

No architectural feature was added. Ruff's automatic edits were reviewed as
format/import-only changes; intentional malformed parser fixtures remain excluded.

## Limitations deferred to Phase 12

- Manual keyboard and real React Flow pointer/viewport behavior.
- Screen-reader announcements and focus restoration in a real browser.
- Light/dark contrast, non-color cues, reduced motion, narrow-screen and large
  graph visual inspection.
- macOS smoke coverage and privileged Windows junction behavior.
- Direct fault injection for every worker-start/crash/malformed-output and
  cancellation-during-persistence race; principal terminal paths are covered,
  but exhaustive concurrency certification is not complete.
- Real React Flow component geometry and the `useAnalysisJob` hook remain outside
  measured component coverage; their adapters/poller and App integration are
  covered separately.
- Offline network observation, five-plus-run p95 performance baselines, and
  controlled policy-limit memory measurement.

Suggested future commits are: `test: expand backend quality and fault coverage`,
`test: add frontend component and accessibility coverage`,
`chore: enforce Python static quality gates`, `ci: add cross-platform test jobs`,
and `docs: document Phase 11 strategy and results`.
