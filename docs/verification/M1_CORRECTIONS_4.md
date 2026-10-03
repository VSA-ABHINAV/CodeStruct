# Milestone 1 — Codex Review 4 Correction Pass Evidence

**Date:** 2026-09-28  
**Status:** Milestone 1 Contract Handoff Corrections Complete; Ready for Codex Review (Stopping before Milestone 2)  
**Reference Reviews:** [`docs/verification/M1_CODEX_REVIEW_4.md`](M1_CODEX_REVIEW_4.md), [`docs/verification/M1_CODEX_REVIEW_3.md`](M1_CODEX_REVIEW_3.md), [`docs/verification/M1_CORRECTIONS_3.md`](M1_CORRECTIONS_3.md)  

---

## 1. Executive Summary & Verification Matrix

All 6 contract handoff mismatches identified in `M1_CODEX_REVIEW_4.md` (CS-004 / CS-023) have been fully resolved through updated contract fixtures, corrected documentation in `LOVABLE_FRONTEND_BRIEF.md`, and permanent regression tests in `tests/test_contract_fixtures.py` and `frontend/src/api/contractFixtures.test.js`:

| Review Finding | Primary Files Modified | Validation Status | Evidence |
| :--- | :--- | :--- | :--- |
| **1. Create Request Mismatch & Option Support** | `LOVABLE_FRONTEND_BRIEF.md`<br>`tests/test_contract_fixtures.py` | **100% PASS** | Section 5.2 create request updated to supported payload (`metrics: false`, default grammar). Unsupported options explicitly documented as returning HTTP 400 `OPTION_UNSUPPORTED` until M2. `test_brief_create_request_matches_route_and_unsupported_options_rejected` regex-extracts the actual JSON snippet from the brief, parses it, and executes against isolated `TestClient` returning 202; also verifies unsupported options (`source_grammar="3.12"`, `metrics=True`, `include_patterns`) return 400 `OPTION_UNSUPPORTED`. |
| **2. Canonical Job Fixture Nested Summary Keys** | `docs/frontend-contract/analysis_job.json`<br>`LOVABLE_FRONTEND_BRIEF.md`<br>`tests/test_contract_fixtures.py`<br>`frontend/src/api/contractFixtures.test.js` | **100% PASS** | Invented keys (`total_files`, `total_nodes`, `total_edges`) removed. Canonical graph summary (all 15 keys: `source_units_total`, `nodes_total`, `edges_total`, `evidence_total`, `diagnostics_total`, `nodes_by_kind`, `edges_by_kind`, etc.) embedded in `analysis_job.json` and Section 5.3. `test_analysis_job_fixture_matches_canonical_serializer_and_route_summary` asserts exact key set match against serializer and live completed job from `TestClient`. Frontend test asserts canonical keys present and invented keys absent. |
| **3. Canonical Diagnostics Fixture Shape & Location** | `docs/frontend-contract/diagnostics.json`<br>`LOVABLE_FRONTEND_BRIEF.md`<br>`tests/test_contract_fixtures.py`<br>`frontend/src/api/contractFixtures.test.js` | **100% PASS** | Invented `file_path`/`line` replaced with canonical `GraphDiagnostic` item containing flat `location` (`source_unit_id`, `path`, `start_line`, `start_column`, `end_line`, `end_column`), `id`, `code`, `severity`, `phase`, `message`, `entity_id`, `edge_id`, `recoverable`, `consequence`, `suggested_action`, and `details`. Added Section 5.7 to brief. Route retrieval tested on static syntax error fixture (`def broken(\n`). Normalization through frontend `normalizeGraphContract` adapter verified. |
| **4. Structured Error Envelope Conformance** | `LOVABLE_FRONTEND_BRIEF.md`<br>`tests/test_contract_fixtures.py` | **100% PASS** | Brief Section 5.5 updated to match real FastAPI `ApiError` envelope: `{"api_version": "v1", "request_id": "...", "error": {"code": "...", "message": "...", "recoverable": true, "field_errors": [], "safe_context": {}, "retry_after_seconds": null}}`. Invented `details` removed. Added validation error example (HTTP 422 `REQUEST_INVALID`). `test_api_error_envelopes_and_schema_validation` asserts exact envelope keys and absence of `details` across 404, 422, and 400 responses. |
| **5. Nonterminal Graph Link Invariant** | `LOVABLE_FRONTEND_BRIEF.md`<br>`tests/test_contract_fixtures.py` | **100% PASS** | Section 5.2 creation response updated to show `"links": {"self": "...", "graph": null, "diagnostics": "..."}`. Explicitly documented that `links.graph` is strictly `null` during nonterminal states and populated only on `completed` or `partially_completed`. Deterministic ID/time substitutions labeled. `test_nonterminal_and_terminal_graph_link_availability` validates `links.graph is None` at creation, 409 `RESULT_NOT_READY` if requested prematurely, and link availability + 200 graph retrieval upon job completion. |
| **6. Cancellation Idempotency & Paging Limit Semantics** | `LOVABLE_FRONTEND_BRIEF.md`<br>`tests/test_contract_fixtures.py` | **100% PASS** | Section 5.4 documents that cancelling already-`cancelled` job is idempotent (HTTP 200), while cancelling completed/failed jobs returns HTTP 409 `JOB_TERMINAL`. Section 5.6 documents that omitting `limit` returns full graph up to `max_full_graph_bytes` (10MB, returning 413 `GRAPH_TOO_LARGE` if exceeded), while explicit `limit` is capped by `max_graph_page_size = 1000` (returning 413 `PAGE_LIMIT_EXCEEDED` if exceeded). Section 2.2 explicitly confirms hosted preview uses labeled static fixtures without loopback promises, file uploads, or paid provider calls. `test_cancellation_idempotency_and_paging_caps` verifies all cases. |

---

## 2. Detailed Technical Corrections

### 2.1 Item 1: Supported Create Request & M2 Option Scoping

**Problem:**
`LOVABLE_FRONTEND_BRIEF.md` Section 5.2 previously specified a request body containing `options: { "source_grammar": "3.12", "metrics": true }`. The backend route `create_analysis` in `backend/src/codestruct/api/routes/analyses.py` explicitly rejects any truthy `metrics` or custom `source_grammar` with HTTP 400 `OPTION_UNSUPPORTED`.

**Resolution:**
1. Updated Section 5.2 of `LOVABLE_FRONTEND_BRIEF.md` to specify:
   ```json
   {
     "project": {
       "root_id": "sample_service",
       "relative_path": "."
     },
     "options": {
       "metrics": false
     },
     "refresh": false
   }
   ```
2. Added clear advisory documenting that custom grammars, pattern inclusion/exclusion, and metrics calculation are scheduled for Milestone 2 and return HTTP 400 `OPTION_UNSUPPORTED` in Milestone 1.
3. Added `test_brief_create_request_matches_route_and_unsupported_options_rejected` in `tests/test_contract_fixtures.py`, which parses the actual markdown code fence from `LOVABLE_FRONTEND_BRIEF.md` via regular expression, decodes it with `json.loads`, and posts it to a live `TestClient(app)`, verifying HTTP 202. The test also asserts HTTP 400 `OPTION_UNSUPPORTED` when sending `source_grammar`, `metrics: true`, or `include_patterns`.

---

### 2.2 Item 2: Canonical Job Fixture Nested Summary Keys

**Problem:**
`docs/frontend-contract/analysis_job.json` and Section 5.3 of the brief previously contained invented keys `total_files`, `total_nodes`, and `total_edges`. The backend serializer `graph_to_dict` and route `_job` embed the canonical graph summary containing 15 exact keys.

**Resolution:**
1. Updated `docs/frontend-contract/analysis_job.json` and Section 5.3 of `LOVABLE_FRONTEND_BRIEF.md` with the full canonical summary:
   ```json
   "summary": {
     "source_units_total": 1,
     "nodes_total": 3,
     "edges_total": 2,
     "evidence_total": 2,
     "diagnostics_total": 0,
     "nodes_by_kind": { "module": 1, "class": 1, "function": 1 },
     "edges_by_kind": { "defines": 2 },
     "edges_by_resolution": { "resolved": 2 },
     "edges_by_confidence": { "high": 2 },
     "diagnostics_by_severity": {},
     "diagnostics_by_code": {},
     "excluded_entries": 0,
     "failed_files": 0,
     "skipped_files": 0,
     "describes_full_result": true
   }
   ```
2. Updated `test_analysis_job_fixture_matches_canonical_serializer_and_route_summary` in `tests/test_contract_fixtures.py` to compare `set(fixture_summary.keys())` against `CANONICAL_SUMMARY_KEYS` and against a serializer-generated graph summary from `sample_project`, and against a live completed job from `TestClient`.
3. Updated `frontend/src/api/contractFixtures.test.js` to assert the presence of canonical summary keys and the explicit absence of `total_files`, `total_nodes`, and `total_edges`.

---

### 2.3 Item 3: Canonical Diagnostics Fixture Shape & Location

**Problem:**
`docs/frontend-contract/diagnostics.json` previously used invented keys `file_path` and `line`, and lacked the canonical `GraphDiagnostic` location and envelope fields.

**Resolution:**
1. Updated `docs/frontend-contract/diagnostics.json` and added Section 5.7 to `LOVABLE_FRONTEND_BRIEF.md`:
   ```json
   {
     "api_version": "v1",
     "request_id": "req_canonical_diag_01",
     "schema_version": "1.0.0",
     "analysis_id": "ana_canonical_12345",
     "provisional": false,
     "items": [
       {
         "id": "d_canonical_syntax_01",
         "code": "FILE_SYNTAX_ERROR",
         "severity": "error",
         "phase": "parsing",
         "message": "A Python file contains invalid or incomplete syntax.",
         "location": {
           "source_unit_id": "src_pkg_module",
           "path": "pkg/module.py",
           "start_line": 1,
           "start_column": 12,
           "end_line": 1,
           "end_column": 0
         },
         "entity_id": null,
         "edge_id": null,
         "recoverable": false,
         "consequence": "skipped_or_partial",
         "suggested_action": null,
         "details": {}
       }
     ],
     "totals": {
       "error": 1
     }
   }
   ```
2. In `tests/test_contract_fixtures.py`, `test_diagnostics_fixture_and_route_retrieval_and_canonical_shape` asserts all canonical keys (`id`, `code`, `severity`, `phase`, `message`, `location`, `entity_id`, `edge_id`, `recoverable`, `consequence`, `suggested_action`, `details`), verifies `location` contains flat `source_unit_id`, `path`, `start_line`, `start_column`, `end_line`, `end_column`, and tests live route retrieval against an isolated project containing a static syntax error (`def broken(\n`), confirming the exact shape is produced without executing analyzed code.
3. In `frontend/src/api/contractFixtures.test.js`, asserted that `normalizeGraphContract` processes the diagnostic item from `diagFixture.items`, verifying normalized `location.path === 'pkg/module.py'` and `location.startLine === 1`.

---

### 2.4 Item 4: Real FastAPI Error Envelope

**Problem:**
Section 5.5 of `LOVABLE_FRONTEND_BRIEF.md` documented an invented error envelope containing `error.details: {}` and omitted `field_errors`, `safe_context`, and `retry_after_seconds`.

**Resolution:**
1. Updated Section 5.5 of `LOVABLE_FRONTEND_BRIEF.md` to reflect the actual serialization of `ApiError` from `backend/src/codestruct/api/errors.py`:
   ```json
   {
     "api_version": "v1",
     "request_id": "req_canonical_err_01",
     "error": {
       "code": "JOB_NOT_FOUND",
       "message": "The requested analysis does not exist or has expired.",
       "recoverable": true,
       "field_errors": [],
       "safe_context": {},
       "retry_after_seconds": null
     }
   }
   ```
2. Added a validation error example (HTTP 422 `REQUEST_INVALID`).
3. Documented all authoritative error codes (`JOB_NOT_FOUND`, `RESULT_EXPIRED`, `OPTION_UNSUPPORTED`, `PROJECT_SELECTION_REQUIRED`, `REQUEST_INVALID`, `PROJECT_UNAUTHORIZED`, `PROJECT_NOT_FOUND`, `QUEUE_FULL`, `JOB_TERMINAL`, `RESULT_NOT_READY`, `RESULT_UNAVAILABLE`, `GRAPH_TOO_LARGE`, `PAGE_LIMIT_EXCEEDED`, `CURSOR_INVALID`, `NODE_NOT_FOUND`, `EDITOR_ACCESS_DENIED`, `UNTRUSTED_ORIGIN`).
4. Added `test_api_error_envelopes_and_schema_validation` in `tests/test_contract_fixtures.py`, verifying live 404, 422, and 400 responses against this exact envelope and asserting that `"details"` is absent.

---

### 2.5 Item 5: Nonterminal Graph Link Invariant

**Problem:**
Section 5.2 of `LOVABLE_FRONTEND_BRIEF.md` previously showed `"graph": "/api/v1/analyses/ana_canonical_12345/graph"` in the `202 Accepted` response. In `backend/src/codestruct/api/routes/analyses.py`, `_job` sets `links.graph = None` until the job reaches `completed` or `partially_completed`.

**Resolution:**
1. Updated Section 5.2 response in `LOVABLE_FRONTEND_BRIEF.md` to show `"graph": null`.
2. Added explicit documentation explaining the nonterminal link invariant: `links.graph` is strictly `null` during nonterminal phases and only populated once a usable result is produced.
3. Added `test_nonterminal_and_terminal_graph_link_availability` in `tests/test_contract_fixtures.py`, testing that:
   - Initial creation response has `links.graph is None`.
   - Calling `GET /api/v1/analyses/{id}/graph` while nonterminal returns HTTP 409 `RESULT_NOT_READY`.
   - Polling until `terminal: true` yields a populated `links.graph` URL, which responds with HTTP 200.

---

### 2.6 Item 6: Cancellation Idempotency & Paging Limit Semantics

**Problem:**
The brief previously stated cancellation returns 409 for any terminal state (ignoring that cancelling an already-cancelled job is idempotent), and conflated omitting `limit` with `max_graph_page_size`.

**Resolution:**
1. Updated Section 5.4 in `LOVABLE_FRONTEND_BRIEF.md`:
   - Active/queued job cancellation transitions to `cancellation_requested` (202) or `cancelled` (200).
   - Cancelling an already-`cancelled` job is idempotent: returns HTTP 200 with the existing cancelled `JobResponse`.
   - Attempting to cancel a job that is `completed`, `partially_completed`, or `failed` returns HTTP 409 `JOB_TERMINAL`.
2. Updated Section 5.6 in `LOVABLE_FRONTEND_BRIEF.md`:
   - Omitted `limit` requests the full unpaged graph subject to `max_full_graph_bytes` (10MB, returning 413 `GRAPH_TOO_LARGE` if exceeded). `max_graph_page_size` does NOT restrict unpaged full-graph requests.
   - Explicit `limit` requests a bounded slice and must satisfy `1 <= limit <= max_graph_page_size` (1000, returning 413 `PAGE_LIMIT_EXCEEDED` if exceeded).
3. Updated Section 2.2 in `LOVABLE_FRONTEND_BRIEF.md`:
   - Reconfirmed that hosted preview loads labeled canonical fixtures directly (`docs/frontend-contract/*.json`), making no local loopback promises, performing no file uploads, and calling no paid external APIs.
4. Added `test_cancellation_idempotency_and_paging_caps` in `tests/test_contract_fixtures.py`, validating:
   - Cancelling already-cancelled job returns HTTP 200 (not 409).
   - Cancelling completed job returns HTTP 409 `JOB_TERMINAL`.
   - Omitted `limit` returns full graph via HTTP 200.
   - Explicit `limit=1001` returns HTTP 413 `PAGE_LIMIT_EXCEEDED`.
   - Valid explicit `limit=2` returns bounded page via HTTP 200.

---

## 3. Full Suite Results Summary

| Validation Suite | Command | Result |
| :--- | :--- | :--- |
| **Contract Fixtures Suite** | `python -m pytest tests/test_contract_fixtures.py --no-cov` | **10 passed in 4.23s** |
| **Plugin Tests** | `python -m pytest thonny-plugin/tests --no-cov` | **49 passed, 1 skipped in 8.34s** |
| **Backend Tests & Coverage** | `python -m pytest -m "not performance and not slow"` | **159 passed, 1 skipped in 16.50s** (85.00% coverage, threshold >= 84.0%) |
| **Ruff Format Check** | `python -m ruff format --check backend tests sample_project thonny-plugin` | **87 files formatted (0 issues)** |
| **Ruff Lint Check** | `python -m ruff check backend tests sample_project thonny-plugin` | **All checks passed! (0 issues)** |
| **Mypy Type Check** | `python -m mypy` | **Success: no issues found in 50 source files** |
| **Frontend Contract Tests** | `npm --prefix frontend test src/api/contractFixtures.test.js` | **6 passed (100%)** |
| **Frontend Vitest Suite & Coverage** | `npm --prefix frontend run test:coverage` | **93 passed across 10 test files** (Lines: 75.47%, Stmts: 72.86%, Branch: 65.32%, Funcs: 74.43%) |
| **Frontend ESLint** | `npm --prefix frontend run lint` | **0 errors, 0 warnings** |
| **Frontend Production Build** | `npm --prefix frontend run build` | **Built in 469ms** (`dist/assets/index-*.js`, `dist/assets/index-*.css`) |

---

## 4. Real GUI & Browser Gate Status

- **Automated Verification:** 100% green across all backend (159 passed), plugin (49 passed), frontend (93 passed), contract (10 passed), linting, formatting, type checking, coverage, and build suites.
- **Manual Desktop Cursor Observation:** **PENDING MANUAL OPERATOR GATE** (Explicitly held open for manual visual verification per project governance; not falsely attested as complete).

---

## 5. Conclusion & Hand-Off

All 6 contract handoff mismatches from `M1_CODEX_REVIEW_4.md` are resolved. The contract handoff documents, fixtures, and tests are verified against authoritative backend routes and serializers.

Milestone 1 is now marked **Ready for Codex review**. Milestone 2 has not been started.
