# Milestone 1 — Codex Review 2 Correction Pass Evidence

**Date:** 2026-09-26  
**Status:** Milestone 1 Corrections Complete; Ready for Codex Review (Stopping before Milestone 2)  
**Reference Reviews:** [`docs/verification/M1_CODEX_REVIEW_2.md`](M1_CODEX_REVIEW_2.md), [`docs/verification/M1_CODEX_REVIEW.md`](M1_CODEX_REVIEW.md), [`docs/verification/M1_CORRECTIONS.md`](M1_CORRECTIONS.md)  

---

## 1. Executive Summary & Verification Matrix

All 5 blocker items identified in `M1_CODEX_REVIEW_2.md` have been fully resolved with comprehensive source corrections, automated regression tests, strict schema validations, CI configuration, and multi-layered verification:

| Review Finding | Primary Files Modified | Validation Status | Evidence |
| :--- | :--- | :--- | :--- |
| **R1/R2: Plugin Generation-Safe Switching & Path Identity** | `thonnycontrib/codestruct/__init__.py`<br>`thonny-plugin/tests/test_plugin.py` | **100% PASS** | `_nav_poll_generation` increments on session switch; in-flight poll callbacks & `after()` verify generation; pre-resolve reparse checks; `_nav_registered_file_resolved` identity match. 50 plugin tests (49 passed, 1 skipped). |
| **R4: Frontend Session Binding & Visible Feedback** | `frontend/src/App.jsx`<br>`frontend/src/App.component.test.jsx`<br>`frontend/src/features/architecture/Components.component.test.jsx` | **100% PASS** | URL query parameters (`session_token`, `analysis_id`) scrubbed immediately on mount; token stored in analysis-associated memory; token discarded on project change; visible ARIA live region (`role="status"`, `role="alert"`). 14 App component tests pass. |
| **R3: Frontend Brief & Permanent Contract Tests** | `LOVABLE_FRONTEND_BRIEF.md`<br>`tests/test_contract_fixtures.py`<br>`frontend/src/api/contractFixtures.test.js`<br>`docs/frontend-contract/editor_navigate.json` | **100% PASS** | Brief reflects React Flow as current renderer and Cytoscape as candidate; exact `GET /api/v1/analyses/{id}/nodes/{node_id}/explain` route; authoritative `JobState` enum values (no `timed_out`); bounded pagination specs. 6/6 fixtures validated in Python & Vitest. |
| **R5: Plugin Outcome Truthfulness & Privacy** | `thonnycontrib/codestruct/__init__.py`<br>`thonny-plugin/tests/test_plugin.py` | **100% PASS** | File-only open without cursor positioning acknowledges `status="failed", reason="cursor_unavailable"`. Exceptions report sanitized `reason="navigation_error"` without leaking raw exceptions or filesystem paths. |
| **R6: CI, Formatting, Coverage & Gate Parity** | `.github/workflows/ci.yml`<br>`CONTRIBUTING.md`<br>`README.md`<br>`docs/development/testing.md`<br>`tests/test_dynamic_tracer.py`<br>`tests/test_export_dot.py`<br>`tests/test_graph_metrics.py`<br>`tests/test_llm_summary.py`<br>`tests/test_python_parser.py`<br>`tests/test_type_stubs.py` | **100% PASS** | Format-only fixes on 6 named test files and plugin (87/87 files pass `ruff format --check`). Plugin test/lint added to CI & docs. Mypy 50/50 files pass. Backend 84.60% coverage (155 passed, 1 skipped). Frontend coverage passed (89 tests pass, lines 75.47%, stmts 72.84%, branch 65.15%, funcs 74.30%). |

---

## 2. Detailed Technical Corrections

### 2.1 R1 & R2: Thonny Plugin Generation-Safe Polling & Path Identity

**Root Cause:**
1. Stale poll callbacks could retain old capability tokens across session switches (A → B).
2. Path resolution occurred before verifying if ancestor paths were symlinks/reparse junctions.
3. `_execute_navigate` lacked verification against `_nav_registered_file_resolved`.

**Implementation in `thonnycontrib/codestruct/__init__.py`:**
- **Reparse Detection:** Implemented `_is_reparse_stat(stat_res)`, `_is_link_or_reparse(path)`, and `_has_link_component(path)` checking both directory components and parent directory chains before calling `.resolve()`.
- **Generation-Safe Polling:** Introduced `_nav_poll_generation: int = 0`. Whenever `_start_navigation_polling` is invoked with a new session token, `_nav_poll_generation += 1`.
- **In-flight & Timer Cancellation:** `_poll_navigate` captures `generation = _nav_poll_generation`. If the active generation changes during HTTP I/O or before `wb.after()` executes, the callback aborts immediately without dispatching stale commands or rescheduling timers.
- **Path Identity Verification:** Stored `_nav_registered_file_resolved: Optional[Path]`. In `_execute_navigate`, the target file is checked via `_has_link_component` and compared with `_nav_registered_file_resolved`. Any discrepancy triggers acknowledgment with `reason="path_identity_mismatch"`.

**Regression Tests in `thonny-plugin/tests/test_plugin.py`:**
- `test_generation_switch_discards_stale_poll`
- `test_stale_timer_callback_discarded`
- `test_pre_resolve_link_rejection`
- `test_path_identity_mismatch_rejected`
- `test_truthful_outcome_cursor_unavailable`
- `test_truthful_outcome_safe_error_reason`

**Suite Result:** 49 passed, 1 skipped (Windows symlink without privilege), 0 failed.

---

### 2.2 R4: Frontend Session Binding & Accessible Feedback

**Root Cause:**
1. `App.jsx` held a flat token that survived project switches.
2. Sensitive `session_token` and `analysis_id` query parameters remained in browser address bar.
3. Navigation failures logged only to console with no user-visible DOM alert.

**Implementation in `frontend/src/App.jsx`:**
- **URL Credential Scrubbing:** Implemented `removeAnalysisIdFromUrl()` called immediately on mount to strip `session_token` and `analysis_id` from `window.location` via `window.history.replaceState()`.
- **Analysis-Bound Session:** `editorSession` stored in state as `{ token, analysisId }`.
- **Token Discarding:** Changing project dropdown or submitting a new analysis sets `editorSession = null`.
- **Accessible Feedback:** Added `navigationFeedback` state. Dispatches render a visible banner with `role="status"` on success/pending or `role="alert"` on failure, with sanitized user-safe messaging.

**Tests in `frontend/src/App.component.test.jsx`:**
- URL credential scrubbing on mount
- Session binding and preservation during same analysis
- Immediate token clearing on project switch
- Accessible failure alert rendering with `role="alert"`

---

### 2.3 R3: LOVABLE_FRONTEND_BRIEF.md & Contract Fixture Validation

**Revisions to `LOVABLE_FRONTEND_BRIEF.md`:**
- Corrected engine evaluation: React Flow (`@xyflow/react`) is documented as the current engine; Cytoscape.js is evaluated as an alternative candidate.
- Corrected endpoints: `GET /api/v1/analyses/{analysis_id}/nodes/{node_id}/explain` (GET method).
- Corrected `JobState` enum: `submitted`, `validating`, `queued`, `scanning`, `parsing`, `resolving`, `building_graph`, `computing_metrics`, `completed`, `partially_completed`, `failed`, `cancellation_requested`, `cancelled`, `cache_hit` (removed nonexistent `timed_out`).
- Removed unsupported performance claims; specified bounded pagination (`limit`, `cursor`, `page.next_cursor`, `page.partial_load`).
- Full handoff specifications: `AccessibleGraphTable`, keyboard navigation shortcuts, `prefers-reduced-motion`, local loopback proxy vs hosted mock previews, authorized local roots security invariant.

**Contract Validation:**
- Python contract suite in `tests/test_contract_fixtures.py` validates all 6 fixtures (`projects.json`, `analysis_job.json`, `graph_slice.json`, `diagnostics.json`, `node_explanation.json`, `editor_navigate.json`) against Pydantic DTOs.
- Vitest contract suite in `frontend/src/api/contractFixtures.test.js` validates fixtures against frontend normalization schemas.
- Removed invalid extra `command_id` field from `acknowledge_response` in `docs/frontend-contract/editor_navigate.json`.

---

### 2.4 R5: Truthful Outcome Codes & Privacy Protection

**Implementation in `thonnycontrib/codestruct/__init__.py`:**
- When Thonny editor notebook opens a file but cursor positioning API is unavailable, acknowledges `status="failed", reason="cursor_unavailable"`.
- When an unexpected exception occurs during navigation, logs detailed error locally but acknowledges `status="failed", reason="navigation_error"` to prevent leaking local paths or stack traces over loopback HTTP.

---

### 2.5 R6: Quality Gates, Formatting & Coverage

1. **Ruff Formatting (Format-Only, Zero Semantic Changes):**
   - Reformatted 6 named test files: `tests/test_dynamic_tracer.py`, `tests/test_export_dot.py`, `tests/test_graph_metrics.py`, `tests/test_llm_summary.py`, `tests/test_python_parser.py`, `tests/test_type_stubs.py`.
   - `python -m ruff format --check backend tests sample_project thonny-plugin` -> **87 files already formatted**.

2. **Ruff Linting:**
   - `python -m ruff check backend tests sample_project thonny-plugin` -> **All checks passed!**

3. **Mypy Type Checking:**
   - `python -m mypy` -> **Success: no issues found in 50 source files**.

4. **Backend Test Suite & Coverage:**
   - `python -m pytest -m "not performance and not slow"` -> **155 passed, 1 skipped in 11.17s**.
   - Coverage: **84.60%** (threshold: >= 84.0%).

5. **Thonny Plugin Test Suite:**
   - `python -m pytest thonny-plugin/tests --no-cov` -> **49 passed, 1 skipped in 6.03s**.

6. **Frontend Test Suite & Coverage:**
   - `npm --prefix frontend run test:coverage` -> **89 passed across 9 test files**.
   - Statements: **72.84%** (threshold: >= 70%)
   - Branches: **65.15%** (threshold: >= 60%)
   - Functions: **74.30%** (threshold: >= 65%)
   - Lines: **75.47%** (threshold: >= 75%)

7. **Frontend Lint & Production Build:**
   - `npm --prefix frontend run lint` -> **0 errors, 0 warnings**.
   - `npm --prefix frontend run build` -> **Built in 456ms** (`dist/assets/index-*.js`, `dist/assets/index-*.css`).

8. **CI & Developer Documentation:**
   - Updated `.github/workflows/ci.yml`, `CONTRIBUTING.md`, `README.md`, and `docs/development/testing.md` with plugin test and lint commands.

---

## 3. Real GUI & Browser Gate Status

- **Automated Verification:** Fully green across all backend, plugin, frontend, accessibility (axe-core), contract, and build suites.
- **Headless / Simulated Probes:** Windows loopback probes confirm distinct registration tokens, 403 untrusted origin rejection, expired acknowledgement rejection, and retargeted junction post rejection.
- **Manual GUI Gate Status:** **PENDING MANUAL OPERATOR GATE** (Explicitly held open for manual visual review per project governance; not marked green without physical operator observation).

---

## 4. Conclusion & Hand-Off

Milestone 1 corrections are complete in strict adherence to `M1_CODEX_REVIEW_2.md` and `ANTIGRAVITY_TASK.md`.  
**Milestone 2 has NOT been started.**  
Stopping now for Codex review.
