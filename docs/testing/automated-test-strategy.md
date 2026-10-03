# Automated test strategy

## Purpose and quality gates

The suite protects CodeStruct's deterministic, non-executing analysis boundary,
versioned contracts, persistent job lifecycle, and accessible explorer. Tests use
repository fixtures or verified temporary directories and databases; no test may
mutate the development database, execute analyzed source, depend on test order,
or leave a worker or server running.

The initial backend gate is 84% combined statement/branch-aware coverage. This
was raised from 80% only after the pre-Phase-11 suite measured 84.64%. Security
path validation, cache keys, migrations, state transitions, graph validation,
and pagination receive direct branch assertions even when the aggregate metric
cannot express per-file thresholds. The frontend baseline and threshold are
recorded in [phase-11-results.md](phase-11-results.md); axe is partial evidence,
not WCAG certification.

## Layers and ownership

| Layer | Primary scope | Current files |
| --- | --- | --- |
| Unit | scanner, parser, resolver, graph invariants, job states, settings | `tests/test_scanner.py`, `test_python_parser.py`, `test_graph_model.py`, `test_phase11_quality.py` |
| Contract | legacy shape, v1 schemas, serialized graph, OpenAPI | `test_analyzer_characterization.py`, `test_api_characterization.py`, `test_graph_model.py`, `test_phase11_quality.py` |
| Integration/storage | SQLite, cache invalidation, API/service composition | `test_storage.py`, `test_cache_integration.py`, `test_v1_api.py` |
| Process | spawned worker, cancellation, restart/cache reuse | `test_cache_integration.py`, `test_v1_api.py` |
| Frontend logic | contract, adapters, selectors, layout, client, polling | `frontend/src/**/*.test.js` |
| Component/accessibility | workflow states, keyboard controls, details, diagnostics, axe | `frontend/src/**/*.component.test.jsx` |
| Performance | deterministic generators and phase timings | `tests/performance/benchmark.py`; manual CI dispatch |
| Manual | visual contrast, screen reader, usability, full OS workflow | Phase 12; no automated-pass claim |

`backend/test_analyzer.py` is a historical print-only script: pytest does not
collect it and it has no meaningful failure assertions. Compatibility is instead
protected by the characterization tests. Overlap between legacy tests in the
analyzer, parser, and graph suites is intentional layered contract protection,
not redundant implementation testing.

## Markers and commands

Markers are registered in `pyproject.toml`: `unit`, `contract`, `integration`,
`process`, `performance`, `slow`, and `platform`. Historical files are classified
centrally in `tests/conftest.py` to preserve useful tests without churn.

```powershell
python -m pytest -m "unit or contract" --no-cov
python -m pytest -m "not performance and not slow"
python -m pytest -m "integration or process" --no-cov
python -m pytest -m "process or platform" --no-cov
python -m pytest --cov=backend --cov-branch --cov-report=term-missing --cov-report=html
python -m ruff format --check backend tests sample_project
python -m ruff check backend tests sample_project
python -m mypy
npm --prefix frontend test
npm --prefix frontend run test:coverage
npm --prefix frontend run test:a11y
npm --prefix frontend run lint
npm --prefix frontend run build
python tests/performance/benchmark.py
```

## Fixture and failure policy

- Parser fixtures are source text only; the side-effect sentinel proves they are
  not imported or executed. Invalid syntax and encoding are intentional and are
  excluded from Ruff, not silently repaired.
- Destructive SQLite, migration, lock, corruption, rollback, expiry, and eviction
  checks use pytest temporary directories or `tests/test-output` only.
- Spawn/process tests have bounded application deadlines and always call service
  shutdown. CI also applies a job timeout.
- A failed test is triaged as product defect, test defect, environment/platform
  limitation, or flaky timing. Assertions are not weakened to change categories.
- Shared-machine performance gates use the documented 1.5x median/2x worst
  investigation tolerances, never fragile millisecond assertions.

## Must-requirement traceability

“Partial/manual” means the automated evidence is useful but cannot close the
requirement without Phase 12 or release-environment validation.

| Requirement | Automated evidence | Status / remaining evidence |
| --- | --- | --- |
| FR-SCAN-001 | `test_scanner`, `test_v1_api`, `test_phase11_quality` | Automated path authorization and traversal |
| FR-SCAN-002 | `test_scanner`, `test_python_parser` | Automated recursion and stable identity |
| FR-SCAN-003 | `test_scanner` exclusions/limits | Partial: UI exclusion summary workflow in Phase 12 |
| FR-ANALYZE-001 | `test_python_parser`, `test_graph_model` | Automated metadata and containment |
| FR-ANALYZE-002 | `test_graph_model` | Automated conservative relationships |
| FR-ANALYZE-003 | `test_graph_model`, frontend logic/component tests | Automated evidence/status presentation |
| FR-JOB-001 | `test_v1_api`, App component states | Automated API progress and UI announcements |
| FR-JOB-002 | `test_v1_api`, App component cancellation | Automated cancellation; manual perceived response in Phase 12 |
| FR-ERROR-001 | parser/graph partial-result tests | Automated partial preservation |
| FR-ERROR-002 | scanner/parser/API and diagnostics component tests | Automated safe diagnostics |
| FR-GRAPH-001 | explorer component controls, renderer adapter logic | Partial: real React Flow keyboard/pointer workflow in Phase 12 |
| FR-SEARCH-001 | selector logic and explorer keyboard tests | Automated loaded-slice search; usability in Phase 12 |
| FR-FILTER-001 | selector logic and explorer component tests | Automated filtering/reset |
| FR-DETAIL-001 | selector and details component tests | Automated identity/evidence details |
| FR-STATE-001 | parameterized GraphStatus and App tests | Automated all documented states |
| FR-SCALE-001 | selector, pagination, large-state component tests | Automated bounds; real large-canvas usability in Phase 12 |
| FR-REFRESH-001 | API/client logic and App refresh tests | Automated forced refresh/cache-hit behavior |
| FR-COMPAT-001 | analyzer/API characterization and legacy adapter tests | Automated legacy contract |
| NFR-SEC-001 | scanner and service path tests | Automated canonical/unauthorized paths; OS variants in CI |
| NFR-SEC-002 | scanner link test marked `platform` | Partial: junction coverage depends on Windows privileges |
| NFR-SEC-003 | sentinel tests and forbidden-call AST audit | Automated non-execution protection |
| NFR-SEC-004 | scanner limit/exclusion tests | Partial: elapsed-time tested; formal peak-memory enforcement deferred |
| NFR-PRIV-001 | path-leak/cache tests and no executable serialization audit | Partial: offline egress observation in Phase 12 |
| NFR-PERF-001 | Phase 10 benchmark generator/baseline | Partial: controlled p95 and policy-limit repetition remain release work |
| NFR-RESP-001 | job progress tests and Phase 10 timings | Partial: perceived UI/navigation timing in Phase 12 |
| NFR-REL-001 | registry, process, cancellation, restart, partial tests | Automated principal terminal paths; exhaustive crash injection remains limited |
| NFR-A11Y-001 | RTL keyboard/roles/live regions plus representative axe scans | Partial: screen reader, contrast, and complete WCAG review in Phase 12 |
| NFR-PLAT-001 | Python matrix plus Windows process and macOS smoke CI jobs | Partial until those CI jobs and Phase 12 workflows execute |
| NFR-DETER-001 | ten-run graph equality plus adapter/layout tests | Automated deterministic identities and output |
| NFR-TEST-001 | this 32-row matrix and CI gates | Partial until all manual rows close |
| NFR-BACK-001 | legacy analyzer/API/adapter characterization | Automated compatibility |
| NFR-PACK-001 | editable install and different-working-directory import test | Automated package import; manual startup smoke in Phase 12 |

## Platform and maintenance rules

Linux runs the supported Python matrix and frontend suite; Windows repeats
spawn/link/path semantics; macOS runs the fast package/security selection. Any
new Must requirement must update this matrix in the same change. A test that is
skipped by capability detection is reported as skipped and never counted as a
pass. HTML coverage, databases, WAL/SHM files, generated benchmarks, `.venv`,
`node_modules`, and builds remain ignored local artifacts.
