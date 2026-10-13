# CodeStruct Project Status & Prototype Launch Shortcut Repair Report

**Date:** 2026-10-13
**Repository:** `D:\REP\Codestruct\Codestruct`
**Current Baseline Commit:** `5797d87`
**Status:** Ready for Review (M7 review pending; prototype start shortcut repaired and verified)

---

## 1. Current Checkout & Repository State

- **Repository Root:** `D:\REP\Codestruct\Codestruct`
- **Active Branch:** `main`
- **HEAD Commit:** `5797d87` (`docs(m7): record report commit d62aea7 in verification evidence report`)
- **Upstream Tracking:** `origin/main`
- **Ahead/Behind State:** `ahead 6` (`5797d87`, `d62aea7`, `921f930`, `361795d`, `e0232f2`, `649625b`)
- **Working-Tree Modifications in Current Task:**
  - `prototype-launcher/prototype-config.json` (repaired `backendPythonExecutable` path)
  - `prototype-launcher/Start-CodeStruct-Prototype.ps1` (resilient auto-discovery fallback)
  - `prototype-launcher/test-launcher-suite.ps1` (hardened test suite file writes to use exact UTF-8 without BOM or trailing newline inflation)
  - `docs/codestruct_audit.md` (reconciled CS-016 status to report-accepted; mirrored to external audit)
  - `PROCESS_TRACKER.md` (recorded shortcut diagnosis, repair, and verified status)
  - `ANTIGRAVITY_TASK.md` (task boundary specification)
  - `docs/verification/PROJECT_STATUS_AND_SHORTCUT.md` (this report)
- **Untracked / Staged Files:** None. Task-created config backup moved to scratch (`C:\Users\ABHINAV\.gemini\antigravity-ide\brain\4fda842f-5c51-411b-b338-e842886b640c\scratch\prototype-config.json.bak`). Desktop shortcut backups preserved outside repository at `C:\Users\ABHINAV\OneDrive\Desktop\*.bak`. Zero secrets or credentials are present or tracked.

---

## 2. Evidence-Based Milestone & Issue Status Matrix

Status designations follow strict project governance:
- **Accepted (Independent Review):** Independently inspected, tested, and accepted by Codex.
- **Complete (Report Reliance):** Marked complete solely per the user's explicit instruction to rely on Antigravity verification reports; no independent source inspection or testing was performed by Codex.
- **Ready for Review:** Implemented and reported by Antigravity with full verification evidence; pending Codex review.
- **User-Reported / Pending Visual Acceptance:** Implemented by Lovable and reported complete by the user; formal Codex visual review evidence pending.
- **Open / Verification Gap:** Requirements not fully verified, deferred portions, or milestones not yet started.
- **Deferred:** Explicitly out of core scope for future user evaluation.

| Milestone | Issues | Owner | Current Status | Primary Evidence Document | Tested / Accepted Commits |
|---|---|---|---|---|---|
| **M1** | CS-001–004, CS-023, contract CS-026 | Antigravity | **Accepted** (Independent Review) | `docs/verification/M1_CODEX_REVIEW_8_ACCEPTED.md`, `docs/verification/M1_REAL_WORKFLOW.md` | `d720b0b` |
| **M2** | CS-008–011, CS-018–019 | Antigravity | **Accepted** (Independent Review) | `docs/verification/M2_CODEX_REVIEW_4_ACCEPTED.md` | `b4e6d30` |
| **M3** | CS-005; design CS-007, CS-022, CS-026 | Lovable + User | **User-Reported Complete** (Visual Review Pending) | `LOVABLE_FRONTEND_BRIEF.md`, `docs/frontend-redesign-functional-map.md` | `frontend.lovable` export |
| **M4** | CS-006, CS-007, integration CS-021, automated CS-022 | Antigravity | **Accepted** (Independent Review) | `docs/verification/M4_CODEX_REVIEW_13_ACCEPTED.md`, `docs/verification/M4.md` | `61159b2` |
| **M5** | CS-012–014 | Antigravity | **Complete** (User Report Reliance Only) | `docs/verification/M5_REPORT_ACCEPTED.md`, `docs/verification/M5.md` | Code: `e72a909`, Reports: `a8f3d38`, `7ea0999`, `fc21580` |
| **M6** | CS-016 | Antigravity | **Complete** (User Report Reliance Only) | `docs/verification/M6_REPORT_ACCEPTED.md`, `docs/verification/M6.md` | Code: `649625b`, Report: `e0232f2`, `361795d` |
| **M7** | CS-015, CS-017 | Antigravity | **Ready for Review** (Antigravity-Submitted) | `docs/verification/M7.md` | Code: `921f930`, Reports: `d62aea7`, `5797d87` |
| **M8** | CS-020–024 | Antigravity + User | **Not Started** | `docs/codestruct_audit.md` | — |
| **Future** | CS-025 | User Decision | **Deferred** | `docs/codestruct_audit.md` | — |

### Detailed Issue Breakdown (CS-001 through CS-026)

| Issue ID | Priority | Status | Milestone | Description & Verified State |
|---|---|---|---|---|
| **CS-001** | P0 | Accepted | M1 | Navigation session security & origin checking (`navigate.py`). Capability tokens (`cap_...`), bounded storage, untrusted origin rejection. |
| **CS-002** | P0 | Accepted | M1 | Thonny plugin session & file isolation (`thonnycontrib.codestruct`). Generation-scoped STOP messages (`("STOP", generation)`), thread-safe dispatch, live Tk cursor index `4.4`. |
| **CS-003** | P1 | Accepted | M1 | Quality configuration consolidation. Pytest, Ruff format/check, Mypy, and plugin test configuration unified. |
| **CS-004** | P1 | Accepted | M1 | Frontend-backend API contract. Canonical schemas, 15-key summary, 4 MiB full-graph cap, paged slicing, nullable locations documented in `LOVABLE_FRONTEND_BRIEF.md`. |
| **CS-005** | P1 | User-Reported Complete | M3 | Visual redesign of Explorer in Lovable. User reports complete; formal Codex visual review pending. |
| **CS-006** | P1 | Accepted | M4 | Real Thonny workbench integration smoke harness. Automated live browser-to-editor dispatch and cursor placement at `4.4` verified without mocks. |
| **CS-007** | P1 | Accepted (M4 portion) | M4 | Pure graph layout algorithm (`layoutGraph()`) and layout benchmark (`measureGraphLayout()` < 500ms across 186 nodes) with graph/table identity parity. |
| **CS-008** | P1 | Accepted | M2 | Metrics option flag (`options.metrics`), cache key isolation, and `metadata.metrics_computed` serialization. |
| **CS-009** | P1 | Accepted | M2 | Transient NetworkX adapter, optional dependency handling, fallback, and canonical deterministic community partitioning verified across exhaustive 4/5-node parity. |
| **CS-010** | P1 | Accepted | M2 | Resolved dependency filtering, iterative SCC, graph components, and module cohesion/coupling metrics. |
| **CS-011** | P1 | Accepted | M2 | Canonical flat location fidelity (`file:line-endline`) and bounded safe evidence references in graph serialization. |
| **CS-012** | P1 | Complete (Report Reliance) | M5 | Explicit opt-in runtime analysis endpoints (`POST`/`GET /api/v1/analyses/{id}/runtime`), isolated child process target execution, Win32 Toolhelp process-tree termination preventing post-timeout side effects, output byte capping. |
| **CS-013** | P1 | Complete (Report Reliance) | M5 | Ambiguous candidate retention (`ResolutionStatus.AMBIGUOUS`, `candidate_ids`) without mutating candidate nodes; truthful microsecond overhead tracking and per-event duration timing; thread profiling; generator suspension handling. |
| **CS-014** | P1 | Complete (Report Reliance) | M5 | Repeat-run graph merge with cumulative call counts, node-level runtime stats, and fresh metric re-enrichment overwriting stale values. |
| **CS-015** | P2 | Ready for Review | M7 | Persistent per-file parse cache in SQLite WAL (`file_cache.py`); multi-factor cache key (root, path, SHA-256, parser v2, policy); LRU eviction (5000 items / 50MB); corruption recovery; cold parse vs warm worker reuse; same-size edit invalidation. |
| **CS-016** | P2 | Complete (Report Reliance) | M6 | Grounded semantic explanations (`retrieval.py`, `llm_summary.py`); bounded context assembly, path containment, secret exclusion; strict Pydantic schemas (`extra="forbid"`); canonical evidence grounding; `LLM_INFERRED` labeling; opt-in `provider="rule-based"` default with deterministic offline fallback. |
| **CS-017** | P2 | Ready for Review | M7 | Bounded deterministic Graphviz export (`export_dot.py`); character escaping; node/edge bounds (2000/5000); subprocess execution with 15s timeout and 10MB cap; process-tree cleanup; actionable 503 diagnostics when Graphviz is missing; frontend slice vs complete graph distinction. |
| **CS-018** | P2 | Accepted | M2 | Stub-only and external type-stub (`.pyi`) precedence and boundaries characterized and documented. |
| **CS-019** | P1 | Accepted | M2 | Lexical scopes, inheritance, multi-dot paths, aliases, constructors, and shadowing characterized with uncertainty preserved. |
| **CS-020** | P2 | Verification Gap | M8 | Ground-truth accuracy evaluation (precision, recall, F1 across entities, calls, imports, inheritance) and scale/overhead bounds. |
| **CS-021** | P1 | Accepted (M4 portion); M8 Pending | M4 + M8 | Cancellation acknowledgement and zero post-terminal polls verified. Storage fault injection remains open under M8. |
| **CS-022** | P1 | Accepted (M4 portion); Manual Review Pending | M4 + M8 | Computed reduced-motion durations, responsive reflow, ARIA regions, and keyboard controls verified. Manual physical screen-reader observation (NVDA) remains pending. |
| **CS-023** | P1 | Accepted (M1 portion); Ongoing | M1 + All | Historical docs reconciliation. PROCESS_TRACKER.md and audit maintained across milestones. |
| **CS-024** | P2 | Verification Gap | M8 | Packaging, platform portability, wheel asset bundling, clean install, license, and maintainer decisions. |
| **CS-025** | P3 | Deferred | Future | Design-pattern detection, change-impact analysis, Git evolution/churn, advanced points-to, ML recovery. Deferred by owner decision. |
| **CS-026** | P2 | Accepted (M1 portion) | M1 + M3 | Cytoscape.js vs React Flow evaluation. Contract supports React Flow; Lovable frontend implementation completed. |

---

## 3. Summary of Delivered vs Tested Capabilities

### What Historical & Milestone Reports Claim (Reported Evidence)

1. **M1 (Delivered & Independently Accepted):**
   - Secure editor reverse-navigation API (`POST /api/v1/navigate`) bound to capability tokens and trusted local origins.
   - Thonny plugin poller with generation-scoped message filtering and thread-safe Tk scheduling.
   - Consolidated test/lint/typecheck configurations and stable frontend-backend contract.
   - Live browser-to-Thonny cursor placement at `app.py:4.4` verified by Codex.

2. **M2 (Delivered & Independently Accepted):**
   - Optional metric computation (`metadata.metrics_computed`).
   - Unified deterministic community partition algorithm matching across NetworkX and Default fallback adapters.
   - Iterative strongly connected components (SCC), resolved dependency filtering, and module cohesion/coupling metrics.
   - Comprehensive characterization of Python stub (`.pyi`) precedence and symbol resolution.

3. **M4 (Delivered & Independently Accepted):**
   - Real Windows loopback integration harness exercising FastAPI backend, Vite frontend, and Thonny IDE workbench simultaneously.
   - Paging and graph/table identity parity (186/186 nodes and 247/247 edges).
   - In-app graph layout execution under 2ms (well within the 500ms bound).
   - Browser-initiated cancellation lifecycle with intermediate `cancellation_requested` acknowledgement and zero post-terminal polling.
   - Win32 Toolhelp process-tree management and Windows NTFS junction containment fail-closed checks.

4. **M5 (Delivered & Accepted via User Report Reliance):**
   - *Claimed in `docs/verification/M5.md` (Tested Code `e72a909`, Reports `a8f3d38`, `7ea0999`, `fc21580`):*
   - Explicit opt-in runtime execution endpoints with subprocess isolation via `runtime_worker.py`.
   - Win32 Toolhelp process-tree termination preventing side effects after timeout/cancellation.
   - Ambiguous call attribution preserved as `ResolutionStatus.AMBIGUOUS` with candidate lists instead of arbitrary assignment.
   - Microsecond tracer hook overhead tracking and per-event duration timing.
   - Repeat-session graph merging with cumulative call counts and metric re-enrichment.
   - *Governance note: Accepted per user instruction to rely on Antigravity's report without independent Codex inspection.*

5. **M6 (Delivered & Accepted via User Report Reliance):**
   - *Claimed in `docs/verification/M6.md` (Tested Code `649625b`, Report `e0232f2` / `361795d`):*
   - Bounded context retrieval (`retrieval.py`) enforcing path containment, secret pattern exclusion, and line/byte limits.
   - Strict Pydantic parsing (`extra="forbid"`) and canonical citation validation against retrieved evidence IDs.
   - Model-derived claims labeled `LLM_INFERRED` vs `RULE_SYNTHESIZED`.
   - Default `provider="rule-based"` with deterministic offline fallback when LLM is unavailable or invalid.
   - 5 isolated API scenarios verified in `scripts/verify_m6_semantic.py`.
   - *Governance note: Accepted per user instruction to rely on Antigravity's report without independent Codex inspection.*

6. **M7 (Delivered & Reported Ready for Review):**
   - *Claimed in `docs/verification/M7.md` (Tested Code `921f930`, Reports `d62aea7`, `5797d87`):*
   - Persistent per-file parse cache (`file_cache.py`) bound to canonical root, relative path, SHA-256 digest, parser version 2, and policy fingerprint.
   - SQLite WAL table `file_parse_cache` with LRU eviction and corruption recovery; integrated into `worker.py` and AST parser.
   - Bounded deterministic Graphviz DOT, SVG, and PNG exports (`export_dot.py`) with character escaping, bounds enforcement, and subprocess execution with process-tree cleanup.
   - Frontend TopToolbar distinction between visible slice export and complete graph export.
   - All quality gates pass (298 backend tests / 84.81% coverage, 53 plugin tests, 104 vitest tests, Ruff, Mypy, build clean).
   - 8 isolated API scenarios verified in `scripts/verify_m7_cache_export.py` (exit code 0 in 9.73s).
   - *Governance note: Reported Ready for Review by Antigravity; pending Codex review.*

---

### Checks Freshly Executed in Current Task (Fresh Evidence)

The following verification suites were freshly executed during this diagnosis and repair task:

1. **Focused Launcher Test Suite (`prototype-launcher/test-launcher-suite.ps1`):**
   - **Command:** `powershell -ExecutionPolicy Bypass -File prototype-launcher\test-launcher-suite.ps1`
   - **Exit Code:** 0
   - **Outcome:** **ALL 12 TESTS PASSED**
     - Test 1: Config Validation (exit 1 on missing file, catches errors) — PASS
     - Test 2: Working Directory Independence (runs Stop from `%TEMP%`) — PASS
     - Test 3: Port Conflict Safety on Backend Port 8000 — PASS
     - Test 4: Port Conflict Safety on Frontend Port 5173 Pre-Check — PASS
     - Test 5: Full Startup, Service Readiness & Frontend Proxy Verification — PASS
     - Test 6: Repeated Start (Reusing Verified Active Services, identical PIDs) — PASS
     - Test 7: Stop Owned Services & Port Release (ports freed, state removed) — PASS
     - Test 8: Repeated Stop Idempotency (exit code 0) — PASS
     - Test 9: Stale State and Dead PID Handling (stale state cleared safely) — PASS
     - Test 10: Alternate Ports End-to-End (8001 / 5174) — PASS
     - Test 11: Desktop Shortcuts Target Verification — PASS
     - Test 12: Thonny Plugin Preflight Failure Safe Abort — PASS

2. **Thonny Profile Encoding Test Suite (`prototype-launcher/test-profile-encoding.ps1`):**
   - **Command:** `powershell -ExecutionPolicy Bypass -File prototype-launcher\test-profile-encoding.ps1`
   - **Exit Code:** 0
   - **Outcome:** **ALL 5 TESTS PASSED**
     - Test 1: Fresh Profile Creation (UTF-8 without BOM) — PASS
     - Test 2: BOM-Prefixed Profile Repair with Backup — PASS
     - Test 3: Existing Valid Profile Left Unchanged — PASS
     - Test 4: Non-ASCII Unicode Settings Preservation — PASS
     - Test 5: Repeated Startup Idempotency — PASS

3. **Live Prototype Smoke Workflow (`Start-CodeStruct-Prototype.ps1` -> `run-e2e-demo.ps1` -> `Stop-CodeStruct-Prototype.ps1`):**
   - **Start:** Backend started on PID 10316 (`http://127.0.0.1:8000`), Frontend started on PID 14220 (`http://127.0.0.1:5173`), Thonny launched on PID 23700.
   - **Demo Run:** Real analysis `ana_XGyqKJBAVGHdtPRglDcQQeyb` completed with 11 nodes, 13 edges; frontend proxy verified serving `/api/v1/analyses/ana_XGyqKJBAVGHdtPRglDcQQeyb` with status `completed`.
   - **Stop:** Backend and frontend processes terminated cleanly; runtime state cleared; ports 8000 and 5173 freed; zero orphan processes remaining.

4. **Git Whitespace & Format Invariant:**
   - **Command:** `git diff --check`
   - **Exit Code:** 0 (clean, zero whitespace errors or conflict markers).

---

### Known Limitations & Unresolved Acceptance Items

1. **Independent Implementation Review Gap for M5 and M6:**
   - M5 and M6 were marked complete based on user instructions to rely on Antigravity's reports. Codex has not performed independent source inspection or verification for CS-012, CS-013, CS-014, or CS-016.
2. **Milestone 7 Pending Review:**
   - M7 is submitted Ready for Review on code commit `921f930`. Codex independent review has not yet taken place.
3. **Milestone 3 Visual Review:**
   - The Lovable explorer redesign is reported complete by the user. A formal Codex visual review report remains pending.
4. **Physical Screen-Reader Observation (CS-022):**
   - Automated accessibility tests (ARIA roles, keyboard shortcuts, reduced-motion) pass; manual physical observation with NVDA/Narrator is recorded as an open verification gap.
5. **Milestone 8 Scope Open:**
   - CS-020 (accuracy evaluation datasets and benchmarks), CS-021 (storage fault injection), and CS-024 (packaging format, license selection, maintainer metadata) have not been started.
6. **CS-025 Deferred:**
   - Advanced research capabilities (points-to analysis, git churn, design pattern extraction) remain deferred per project plan.

---

## 4. Prototype Start Shortcut Diagnosis, Root Cause & Repair

### 1. Shortcut Identification

The user interacts with two Windows shortcuts located on the desktop:
- **Start Shortcut:** `C:\Users\ABHINAV\OneDrive\Desktop\Start CodeStruct Prototype.lnk`
  - **Target:** `D:\REP\Codestruct\Codestruct\prototype-launcher\Start-CodeStruct-Prototype.cmd`
  - **Arguments:** None
  - **Working Directory:** `D:\REP\Codestruct\Codestruct\prototype-launcher`
  - **Icon:** `D:\REP\Codestruct\Codestruct\frontend.lovable\public\favicon.ico`
- **Stop Shortcut:** `C:\Users\ABHINAV\OneDrive\Desktop\Stop CodeStruct Prototype.lnk`
  - **Target:** `D:\REP\Codestruct\Codestruct\prototype-launcher\Stop-CodeStruct-Prototype.cmd`
  - **Arguments:** None
  - **Working Directory:** `D:\REP\Codestruct\Codestruct\prototype-launcher`
  - **Icon:** `%SystemRoot%\System32\shell32.dll,27` (standard stop icon)

### 2. Root Cause Analysis

1. **Machine Python Change:**
   - System Python was upgraded to Python 3.14.6 located at `C:\Python314\python.exe`.
   - The previous Python 3.13 installation at `C:\Users\ABHINAV\AppData\Local\Programs\Python\Python313\python.exe` was uninstalled/removed.
2. **Hardcoded Launcher Configuration:**
   - `prototype-launcher/prototype-config.json` contained:
     ```json
     "backendPythonExecutable": "C:\\Users\\ABHINAV\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"
     ```
3. **Startup Failure Trace:**
   - User invokes `Start CodeStruct Prototype.lnk` -> runs `Start-CodeStruct-Prototype.cmd` -> launches PowerShell script `Start-CodeStruct-Prototype.ps1`.
   - Line 115 of `Start-CodeStruct-Prototype.ps1` evaluated:
     `if (-not (Test-Path $config.backendPythonExecutable))`
   - Because the Python 3.13 path no longer existed on disk, it recorded:
     `"backendPythonExecutable does not exist: 'C:\Users\ABHINAV\AppData\Local\Programs\Python\Python313\python.exe'"`
   - The script aborted immediately with exit code 1 before launching backend or frontend services.
4. **Environment Nuance:**
   - While `C:\Python314\python.exe` is installed, the CodeStruct backend package and all its dependencies (`fastapi`, `uvicorn`, `networkx`, etc.) are installed in editable mode inside the repository virtual environment at `D:\REP\Codestruct\Codestruct\.venv\Scripts\python.exe` (which is also Python 3.14.6). Pointing to system Python would fail module imports, whereas pointing to `.venv` succeeds completely.

### 3. Exact Minimal Repair

1. **Config Update (`prototype-launcher/prototype-config.json`):**
   - Changed `"backendPythonExecutable"` to `"D:\\REP\\Codestruct\\Codestruct\\.venv\\Scripts\\python.exe"`.
2. **Resilient Auto-Discovery Fallback (`prototype-launcher/Start-CodeStruct-Prototype.ps1`):**
   - Added automatic discovery logic to line 115:
     ```powershell
     if (-not (Test-Path $config.backendPythonExecutable)) {
         $candidateVenv = Join-Path $config.codeStructDirectory ".venv\Scripts\python.exe"
         if (Test-Path $candidateVenv) {
             Write-Host "  [NOTICE] Configured backendPythonExecutable not found; auto-discovered virtualenv at '$candidateVenv'." -ForegroundColor Yellow
             $config.backendPythonExecutable = $candidateVenv
         } else {
             $validationErrors.Add("backendPythonExecutable does not exist: '$($config.backendPythonExecutable)'")
         }
     }
     ```
   - This ensures that even if a future system Python path shifts, the launcher gracefully discovers and uses the repository virtual environment rather than failing immediately.
3. **Preserved Shortcuts & Created Backups:**
   - Shortcut targets, arguments, icons, and working directories were preserved.
   - Backups created prior to modifications:
     - `C:\Users\ABHINAV\OneDrive\Desktop\Start CodeStruct Prototype.lnk.bak`
     - `C:\Users\ABHINAV\OneDrive\Desktop\Stop CodeStruct Prototype.lnk.bak`
     - `prototype-launcher/prototype-config.json.bak` (stored safely in scratch directory).

### 4. Reproducible Startup & Shutdown Instructions

#### To Start the Prototype:
- **Interactive:** Double-click `Start CodeStruct Prototype.lnk` on the desktop.
- **Command Line:** Run `D:\REP\Codestruct\Codestruct\prototype-launcher\Start-CodeStruct-Prototype.cmd`.
- **Expected Outcome:**
  - Backend starts on `http://127.0.0.1:8000`.
  - Frontend starts on `http://127.0.0.1:5173`.
  - Thonny IDE opens with CodeStruct plugin loaded.
  - Browser navigates to `http://127.0.0.1:5173`.

#### To Stop the Prototype:
- **Interactive:** Double-click `Stop CodeStruct Prototype.lnk` on the desktop.
- **Command Line:** Run `D:\REP\Codestruct\Codestruct\prototype-launcher\Stop-CodeStruct-Prototype.cmd`.
- **Expected Outcome:**
  - Backend and frontend processes terminated cleanly.
  - State file removed.
  - Ports 8000 and 5173 freed.
  - Thonny left running safely if active (or closed cleanly if owned). Zero orphan processes.

---

## 5. Priority-Ordered Next Steps

| Priority | Step | Owner | Prerequisites | Scope / Details |
|---|---|---|---|---|
| **1** | **Codex Independent Review of Milestone 7** | Codex | M7 report `docs/verification/M7.md` and code commit `921f930` | Review CS-015 (incremental parse caching) and CS-017 (bounded Graphviz export). Decide whether M7 is Accepted or requires changes. |
| **2** | **Milestone 3 Visual Review & Formal Acceptance** | User / Codex | Exported Lovable frontend in `frontend.lovable` | User previously reported frontend complete; formal visual review evidence to be recorded by Codex if required. |
| **3** | **Milestone 8 Scope & Owner Decisions** | Project Owner / User | M7 Acceptance | Decide open policy questions for M8: target license (e.g., MIT, Apache 2.0, or proprietary), package maintainer identity, whether manual NVDA screen-reader testing is required, and baseline evaluation dataset for CS-020. |
| **4** | **Milestone 8 Implementation (CS-020–024)** | Antigravity | M7 Accepted by Codex, M8 scope approved by Owner | Implement accuracy benchmarking (CS-020), storage fault resilience (CS-021), accessibility review closure (CS-022), doc reconciliation (CS-023), and packaging/wheel release gates (CS-024). |
| **5** | **Future Capabilities (CS-025)** | Project Owner | M8 Completion | Keep CS-025 (design-pattern detection, git churn, points-to, ML recovery) **Deferred** unless separately commissioned. |

---

## 6. Action Recommendations by Role

### For Antigravity
- **Current Action:** Stand by at review readiness.
- **Constraint:** Do not begin Milestone 8, modify application features, or edit unrelated code. Await Codex's review of Milestone 7 and user authorization for Milestone 8.

### For Codex
- **Current Action:** Conduct independent review of Milestone 7 (CS-015 and CS-017) against tested code commit `921f930` and verification evidence in `docs/verification/M7.md`.
- **Deliverable:** Produce `docs/verification/M7_CODEX_REVIEW_1.md` recording independent gate results and acceptance decision.

### For Project Owner / User
- **Current Action:**
  1. Test the repaired prototype launcher by double-clicking the desktop shortcut `Start CodeStruct Prototype.lnk` and confirming clean startup and shutdown via `Stop CodeStruct Prototype.lnk`.
  2. Review the milestone matrix above.
  3. Decide on M8 parameters: license type, maintainer contact, and evaluation dataset requirements before authorizing M8 work.
