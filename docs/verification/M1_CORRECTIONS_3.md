# Milestone 1 — Codex Review 3 Correction Pass Evidence

**Date:** 2026-09-27  
**Status:** Milestone 1 Corrections Complete; Ready for Codex Review (Stopping before Milestone 2)  
**Reference Reviews:** [`docs/verification/M1_CODEX_REVIEW_3.md`](M1_CODEX_REVIEW_3.md), [`docs/verification/M1_CODEX_REVIEW_2.md`](M1_CODEX_REVIEW_2.md), [`docs/verification/M1_CORRECTIONS_2.md`](M1_CORRECTIONS_2.md)  

---

## 1. Executive Summary & Verification Matrix

All 3 items identified in `M1_CODEX_REVIEW_3.md` have been fully resolved with source corrections, regression tests, exact contract documentation, and repeatable gate verification:

| Review Finding | Primary Files Modified | Validation Status | Evidence |
| :--- | :--- | :--- | :--- |
| **1. StrictMode IDE Startup Regression** | `frontend/src/App.jsx`<br>`frontend/src/App.strictReview.test.jsx` | **100% PASS** | Initial URL handoff (`analysis_id`, `session_token`) captured independently in state at initialization; effect safely triggers and replays `load()` across StrictMode double-mount while scrubbing URL. 4 focused tests in `App.strictReview.test.jsx` pass (both StrictMode=true and false; with and without token). |
| **2. Precise Contract Handoff & Strengthened Fixture Tests** | `LOVABLE_FRONTEND_BRIEF.md`<br>`tests/test_contract_fixtures.py` | **100% PASS** | Brief updated with server pagination cap (`max_graph_page_size=1000`), `ANALYSIS_TIMEOUT` code, SHA256 integrity cursor semantics, planned capabilities (virtualization/Dagre), and full copy-pastable payload examples. Fixture tests validate real round-trip serialization, nested result structures, pagination cursors, and TestClient routes. |
| **3. Repeatable Formatter Gate & Test Fixture Isolation** | `thonny-plugin/tests/test_plugin.py`<br>`thonny-plugin/tests/fixtures/project_a/*.py` | **100% PASS** | Plugin tests copy fixtures to `tempfile.TemporaryDirectory` in `setUp` and clean up in `tearDown`. `ruff format --check` passes before AND after running test suites (87/87 files formatted, 0 modified by tests). |

---

## 2. Detailed Technical Corrections

### 2.1 Item 1: React StrictMode IDE URL Startup Resolution

**Root Cause:**
In React StrictMode development mounts, `App.jsx`'s mount effect ran, triggered `load(id)`, and scrubbed the URL via `window.history.replaceState()`. StrictMode unmount cleanup stopped the poller. On effect replay, `App.jsx` reread the already-scrubbed URL (`window.location.search === ''`), found no `analysis_id`, and failed to restart polling, leaving the viewer in `waiting`.

**Implementation in `frontend/src/App.jsx`:**
- Introduced `getInitialUrlHandoff()` to capture `{ analysisId, sessionToken }` into immutable component state `const [initialHandoff] = useState(getInitialUrlHandoff)` on first evaluation.
- `editorSession` initialized lazily from `initialHandoff.sessionToken`.
- In `useEffect`, `load(initialHandoff.analysisId)` executes whenever `initialHandoff.analysisId` is present, reliably restarting the poller across StrictMode remounts, while `removeAnalysisIdFromUrl()` cleans the browser address bar.

**Targeted Tests in `frontend/src/App.strictReview.test.jsx`:**
1. `IDE URL loads a real analysis hook with StrictMode=false` (PASS)
2. `IDE URL loads a real analysis hook with StrictMode=true` (PASS)
3. `loads plain analysis_id without session token under StrictMode=false` (PASS)
4. `loads plain analysis_id without session token under StrictMode=true` (PASS)

---

### 2.2 Item 2: Precise Contract Brief & Comprehensive Fixture Tests

**Corrections in `LOVABLE_FRONTEND_BRIEF.md`:**
- **Pagination Limit:** Documented that omitting `limit` returns full graph up to server byte cap; server setting default is `max_graph_page_size = 1000`. Recommended client behavior is explicit bounded page request (e.g. `limit=1000`).
- **Timeout Code:** Exact error code is `ANALYSIS_TIMEOUT` in job executor failure transitions.
- **Cursor Integrity Semantics:** Documented as result- and filter-bound SHA256 integrity-checked opaque cursor (not HMAC).
- **Capability Distinctions:** Marked viewport virtualization and Dagre layout adapter as **Planned for Milestone 3+**; documented current React Flow DOM cards with deterministic DAG positioning (`graphLayout.js`).
- **Complete Contract Payload Catalog:** Added full copy-pastable JSON payloads for create request/response, job polling progress & terminal states (`completed`, `partially_completed`, `failed`, `cancelled`, `cache_hit`), cancellation (`DELETE`), structured API errors (`JOB_NOT_FOUND`, `RESULT_EXPIRED`, `REQUEST_INVALID`, `PROJECT_UNAUTHORIZED`, `QUEUE_FULL`, `ANALYSIS_TIMEOUT`), graph slice, diagnostics, node explanation, and editor cross-navigation loop.

**Strengthened Tests in `tests/test_contract_fixtures.py`:**
- Validated `graph_slice.json` against real serializer round-trip (`graph_from_dict` and `graph_to_dict`), verifying preservation of exact node coordinates, attributes, and evidence origins.
- Validated real `slice_graph` pagination and cursor decoding against `sample_project` AST graph.
- Validated nested dictionary contents of `JobResponse.result` (`result_id`, `graph_id`, `schema_version`, `summary`).
- Validated live FastAPI `TestClient` responses against schema models.

---

### 2.3 Item 3: Repeatable Formatter Gate & Fixture Isolation

**Root Cause:**
Plugin tests in `test_plugin.py` operated directly on files inside the checked-in `thonny-plugin/tests/fixtures/` directory, mutating source strings and causing subsequent `ruff format --check` runs to fail.

**Implementation in `thonny-plugin/tests/test_plugin.py`:**
- In `setUp()`: Created `self._temp_dir = tempfile.TemporaryDirectory()`, copied the source fixtures into `self.fixtures_dir = Path(self._temp_dir.name) / "fixtures"`, and pointed `self.root_a` / `self.root_b` to the isolated copy.
- In `tearDown()`: Cleaned up `self._temp_dir` and reset all global adapter state.
- Formatted checked-in fixtures with `ruff format`.

**Gate Verification:**
- `python -m ruff format --check backend tests sample_project thonny-plugin` -> **87 files already formatted** (PASS before tests).
- `python -m pytest thonny-plugin/tests --no-cov` -> **49 passed, 1 skipped** (PASS).
- `python -m ruff format --check backend tests sample_project thonny-plugin` -> **87 files already formatted** (PASS after tests; zero fixture files mutated).

---

## 3. Full Suite Results Summary

| Validation Suite | Command | Result |
| :--- | :--- | :--- |
| **Plugin Tests** | `python -m pytest thonny-plugin/tests --no-cov` | **49 passed, 1 skipped in 7.21s** |
| **Backend Tests & Coverage** | `python -m pytest -m "not performance and not slow"` | **155 passed, 1 skipped in 12.93s** (84.60% coverage, threshold >= 84.0%) |
| **Contract Fixtures Suite** | `python -m pytest tests/test_contract_fixtures.py --no-cov` | **6 passed in 0.91s** |
| **Ruff Format Check** | `python -m ruff format --check backend tests sample_project thonny-plugin` | **87 files formatted (0 issues)** |
| **Ruff Lint Check** | `python -m ruff check backend tests sample_project thonny-plugin` | **All checks passed! (0 issues)** |
| **Mypy Type Check** | `python -m mypy` | **Success: no issues found in 50 source files** |
| **Frontend Targeted Startup** | `npm --prefix frontend test src/App.strictReview.test.jsx` | **4 passed (100%)** |
| **Frontend Vitest Suite & Coverage** | `npm --prefix frontend run test:coverage` | **93 passed across 10 test files** (Lines: 75.47%, Stmts: 72.86%, Branch: 65.32%, Funcs: 74.43%) |
| **Frontend ESLint** | `npm --prefix frontend run lint` | **0 errors, 0 warnings** |
| **Frontend Production Build** | `npm --prefix frontend run build` | **Built in 1.24s** (`dist/assets/index-*.js`, `dist/assets/index-*.css`) |

---

## 4. Real GUI & Browser Gate Status

- **Automated Verification:** Fully green across backend, plugin, frontend, accessibility (axe-core), contract, and build suites.
- **Manual Desktop Cursor Observation:** **PENDING MANUAL OPERATOR GATE** (Explicitly held open for manual visual verification per project governance).

---

## 5. Conclusion & Hand-Off

Milestone 1 corrections are complete in strict adherence to `M1_CODEX_REVIEW_3.md` and `ANTIGRAVITY_TASK.md`.  
**Milestone 2 has NOT been started.**  
Stopping now for Codex review.
