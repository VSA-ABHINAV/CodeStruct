# CodeStruct Project Audit
*Generated: 2026-09-23 | Auditor: Main Orchestrator Agent*

---

## 1. Executive Summary

CodeStruct is substantially further along than a typical early prototype, but is **not yet an integrated, end-to-end usable system**. The backend analysis pipeline (static AST scanning, entity extraction, graph construction, SQLite caching, job management, REST API) is well-implemented and architecturally sound. The frontend (React Flow graph, filtering, search, details panel, diagnostics) is also well-built.

**The critical gap is the missing end-to-end integration chain:**

```
Source navigation metadata in graph nodes  (EXISTS in graph data)
        ↓
"Open Source" / "Go to Definition" action in DetailsPanel  (MISSING button)
        ↓
Backend editor bridge POST /api/v1/editor/navigate  (ENDPOINT MISSING)
        ↓
Thonny receives navigate-to-file+line command  (POLLING MISSING)
        ↓
Correct file opens at correct line  (NEVER REACHED)
```

The Thonny plugin can **submit analyses** and open the browser, but it **cannot receive reverse navigation commands** from the frontend. The DetailsPanel shows source location text but has no clickable action. The `onNavigateSource` prop is threaded through the component tree but is **always passed as `null`** from `App.jsx`.

Additionally, several intended features from the Technology Summary are not started: dynamic analysis (`sys.setprofile`), NetworkX metrics, LLM/RAG layer, Graphviz export, and architecture metrics.

**What currently works end-to-end:**
> User selects a configured Python project in the web UI → clicks Analyze → backend spawns a worker → Python AST scans files recursively → extracts modules, classes, functions, imports, inheritance, calls → builds graph with source locations → stores in SQLite → frontend polls to completion → React Flow renders the graph → user can filter, search, zoom, inspect entity details → source file path and line numbers are **displayed** in the details panel.

**What does not work:** Navigation from graph node to opening the correct file at the correct line in the editor.

---

## 2. Intended Product Workflow

Per the Technology Summary Report, the intended experience is:

1. Developer opens Python project in Thonny IDE
2. Triggers "Analyze with CodeStruct" from Tools menu
3. CodeStruct analyzes AST statically (and optionally dynamically via `sys.setprofile`)
4. A unified graph (static + runtime) is generated
5. Interactive visualization appears (Cytoscape.js in spec; React Flow used in implementation)
6. Developer inspects: modules, classes, functions, imports, calls, inheritance, dependencies
7. Developer right-clicks or selects a symbol → "Go to Definition" / "Open Source"
8. Thonny navigates to the exact file and line
9. Optional: LLM layer provides natural-language summaries grounded in graph evidence

---

## 3. Current Architecture

```
Thonny IDE (Python plugin)
    ├─→ POST /api/v1/editor/selection   (register current file as capability)
    ├─→ POST /api/v1/analyses           (submit analysis job)
    └─→ Opens browser at frontend URL

FastAPI Backend (Uvicorn)
    ├── /api/v1/analyses            — job lifecycle (submit, poll, cancel)
    ├── /api/v1/analyses/{id}/graph — paginated graph result
    ├── /api/v1/analyses/{id}/diagnostics
    ├── /api/v1/projects            — list authorized projects
    └── /api/v1/editor/selection    — register editor file (one direction only)

Backend Package (codestruct):
    analysis/   scanner.py, python_parser.py, models.py, policy.py, diagnostics.py
    graph/      builder.py, resolver.py, model.py, enums.py, serialization.py, validation.py
    jobs/       service.py, executor.py, registry.py, worker.py, models.py
    storage/    sqlite_repository.py
    api/        app.py + routes/ (analyses, projects, editor)

React Frontend (Vite + React):
    App.jsx                                    — project selection + job submit
    Graph.jsx                                  — legacy compat shim
    features/architecture/
        ArchitectureExplorer.jsx               — main orchestrator
        ArchitectureGraph.jsx                  — React Flow canvas
        reactFlowAdapter.js                    — graph → RF elements
        graphAdapter.js / graphContract.js     — normalization + validation
        graphSelectors.js / graphLayout.js     — filter + layout
        DetailsPanel.jsx                       — entity details (location displayed)
        TopToolbar.jsx, LeftSidebar.jsx        — toolbar + view controls
        FilterPanel.jsx, DiagnosticsDrawer.jsx — filters + diagnostics

Thonny Plugin: thonnycontrib/codestruct/__init__.py
    — menu item, worker thread, browser launch (one-way only)
```

---

## 4. Repository Structure

```
d:\REP\Codestruct\Codestruct\
├── backend/src/codestruct/    Python backend package
│   ├── analysis/              Parser + scanner
│   ├── api/                   FastAPI routes
│   ├── graph/                 Graph model + builder + resolver
│   ├── jobs/                  Job lifecycle
│   ├── storage/               SQLite persistence
│   ├── cli.py                 CLI entry point
│   └── settings.py            Config
├── frontend/src/
│   ├── api/                   API client + polling
│   └── features/architecture/ All UI components (26 files)
├── thonny-plugin/thonnycontrib/codestruct/__init__.py
├── tests/                     12 pytest test files
├── docs/                      Architecture, API, product requirements
├── sample_project/            3-file test project (main.py, user.py, database.py)
└── tools/                     build_release.py, verify_artifacts.py
```

---

## 5. Module-by-Module Status

| Module | Intended Purpose | Current Status | What Works | What Is Missing | Integration Status |
|--------|-----------------|----------------|------------|-----------------|-------------------|
| `analysis/scanner.py` | Recursive .py discovery | **Complete** | Policy-enforced scan, symlink-safe, cancellable, module name derivation | Incremental caching | Integrated |
| `analysis/python_parser.py` | AST entity extraction | **Complete** | Modules, classes, fns, methods, imports, inheritance, call sites, line numbers, params, decorators | Dynamic analysis, variables | Integrated |
| `analysis/models.py` | Immutable parser models | **Complete** | All entity dataclasses, SourceSpan with line/col | — | Used throughout |
| `analysis/policy.py` | Analysis policy | **Complete** | File size, recursion depth, exclusions | Dynamic analysis policy | Used in scanner |
| `graph/builder.py` | Assemble GraphResult | **Complete** | Nodes with SourceReference (path+span), edges, evidence, diagnostics | Dynamic graph merging | In job worker |
| `graph/resolver.py` | Conservative resolution | **Complete** | SymbolIndex, cross-file imports, call resolution, ambiguity | Full inter-procedural | In builder |
| `graph/model.py` | Immutable graph models | **Complete** | GraphNode.location = SourceReference{path, span}, GraphEdge, EvidenceRecord | — | Used throughout |
| `graph/serialization.py` | JSON serialization | **Complete** | Full GraphResult → JSON including paths and spans | — | In API |
| `graph/enums.py` | Graph enumerations | **Complete** | NodeKind, RelationshipKind, ResolutionStatus, EvidenceOrigin, Confidence | — | Stable |
| `graph/validation.py` | Graph integrity | **Complete** | Schema validation | — | In serialization |
| `jobs/service.py` | Job orchestration | **Mostly Complete** | Submit, poll, cancel, cache, EditorCapability | Reverse navigate callback | Backend OK |
| `jobs/executor.py` | Spawned execution | **Complete** | Process spawn, timeout, cancellation | — | Working |
| `storage/sqlite_repository.py` | SQLite caching | **Complete** | WAL, LRU eviction, migration, reuse | — | Working |
| `api/routes/analyses.py` | Job HTTP API | **Complete** | POST/GET/DELETE, graph+diagnostics, pagination | — | Working |
| `api/routes/editor.py` | Editor file API | **Complete** | POST /api/v1/editor/selection | **Reverse navigate endpoint** missing | One direction only |
| `api/routes/projects.py` | Project listing | **Complete** | GET /api/v1/projects | — | Working |
| `App.jsx` | App shell | **Mostly Complete** | Project select, submit, poll, handoff | `onNavigateSource` always `null` | Missing last step |
| `ArchitectureExplorer.jsx` | Main explorer | **Mostly Complete** | Filter, search, views, layout, selection, details | Source navigation action | `onNavigateSource` unimplemented |
| `DetailsPanel.jsx` | Entity details | **Mostly Complete** | Type, location text (path:line:col), edges, evidence, diagnostics | **"Open in editor" button** | Location shown, not actionable |
| `reactFlowAdapter.js` | Graph → RF elements | **Complete** | Node types, edge styles, unresolved stubs, dimming | — | Working |
| `graphSelectors.js` | Filter/search/view | **Complete** | filterGraph, searchNodes, applyVisibility, applyViewMode | — | Working |
| `graphLayout.js` | ELK layout | **Complete** | Hierarchical positioning | — | Working |
| `graphContract.js` | Contract validation | **Complete** | Schema version checking, normalization | — | Working |
| `graphAdapter.js` | Normalize API graph | **Partial** | Delegates to normalizeGraph | Schema edge cases unverified | Thin (519 bytes) |
| `thonny-plugin/__init__.py` | Thonny integration | **Mostly Complete** | Menu, capability registration, submit, browser open, shutdown | **Reverse navigation receiver** | One-way only |
| `tests/` | Test suite | **Partial** | 12 test files covering parser, graph, scanner, storage, API, editor | E2E navigation tests, confirmed run status | Not confirmed passing |
| Dynamic analysis | sys.setprofile tracer | **Missing** | — | Everything | Not started |
| NetworkX integration | Graph metrics | **Missing** | — | Everything | Not started |
| LLM/RAG layer | Semantic summaries | **Missing** | — | Everything | Not started |
| Graphviz export | Static diagrams | **Missing** | — | Everything | Not started |
| Architecture metrics | Coupling, cohesion | **Missing** | — | Everything | Not started |

---

## 6. Features Currently Working

1. Recursive Python project scanning — policy-enforced, cancellable, symlink-safe
2. AST entity extraction — modules, classes, functions (sync/async), methods, imports, inheritance, call sites, parameters, decorators, line/column spans
3. Graph construction — nodes with source location (file path + span), typed edges, evidence records, diagnostics
4. Conservative relationship resolution — import-to-module, cross-file call resolution with confidence/status
5. Background job system — spawned worker processes, progress, cancellation, timeout
6. SQLite caching — WAL mode, LRU eviction, migration, result reuse with content verification
7. REST API v1 — job lifecycle, graph retrieval with pagination, project listing, editor capability registration
8. Frontend graph rendering — React Flow with custom node types, color-coded edge types
9. Frontend filtering — by node kind, relationship kind, resolution status, confidence
10. Frontend search — by name, qualified name, path; keyboard navigation
11. Frontend view modes — overview, classes only, call flow
12. Details panel — entity metadata, relationships, evidence, diagnostics, source location text
13. Large graph protection — threshold warning, bounded pages, load-more pagination
14. JSON export — working from toolbar
15. Thonny menu item — "Analyze with CodeStruct" in Tools menu
16. Editor capability registration — Thonny registers file, gets capability ID for scoped analysis

---

## 7. Partially Implemented Features

1. **Source navigation** — location metadata EXISTS in graph nodes; DetailsPanel SHOWS it as text; no button to act on it
2. **Thonny IDE integration** — submit and browser-open works; reverse navigate-to-source completely absent
3. **Context menu** — no right-click context menu on graph nodes (only click selects)
4. **`onNavigateSource` prop chain** — exists App → Graph → ArchitectureExplorer → DetailsPanel; always `null` from App.jsx

---

## 8. Missing Features

1. "Open Source" / "Go to Definition" button in DetailsPanel
2. Backend POST /api/v1/editor/navigate endpoint (frontend → IDE direction)
3. Thonny reverse navigation receiver (poll loop + show_file_at_line call)
4. Dynamic analysis (sys.setprofile-based runtime call graph)
5. Unified static + dynamic graph
6. NetworkX graph metrics (fan-in, fan-out, centrality, cycles, clustering)
7. Architecture metrics (coupling, cohesion, dependency density)
8. LLM/RAG layer (function summaries, module descriptions)
9. Graphviz export (DOT/SVG/PNG)
10. Right-click context menu on graph nodes
11. Incremental file caching (full reanalysis every time)
12. Variable tracking (by design for now)
13. Type stub (.pyi) integration

---

## 9. Broken / Unintegrated Features

1. **`onNavigateSource` integration** — prop chain exists in JSX but App.jsx passes `null` unconditionally; DetailsPanel has the prop but the button using it is absent
2. **Legacy API compat** — Graph.jsx shim supports old {files, dependencies} format; edge cases possible
3. **graphAdapter.js thinness** — 519 bytes, delegates to normalizeGraph; schema edge cases unverified

---

## 10. Current End-to-End Workflow

**Longest currently working flow (Web UI path):**
```
1. Open http://localhost:5173
2. Frontend fetches /api/v1/projects → lists configured projects
3. Select project → click "Analyze project"
4. Frontend POSTs /api/v1/analyses
5. Backend validates → spawns worker process
6. Worker: scan_project() → parse files → build_graph() → serialize → store SQLite
7. Frontend polls /api/v1/analyses/{id} every few seconds
8. On completion: fetches /api/v1/analyses/{id}/graph (paginated)
9. Frontend: normalize → filter → layout → React Flow render
10. User: zoom/pan, filter, search, switch views, select nodes
11. Details panel: type, qualified name, path:line:col, edges, evidence, diagnostics
12. STOPS: source file visible but cannot open it
```

**Thonny path:**
```
1. Open Python file in Thonny
2. Tools → Analyze with CodeStruct
3. Plugin: POST /api/v1/editor/selection → gets capability ID
4. Plugin: POST /api/v1/analyses → submits job
5. Plugin: opens browser at frontend URL with ?analysis_id=...
6. Frontend loads result, all above features work
7. STOPS: no reverse navigation possible
```

---

## 11. Intended vs Current Comparison

| Intended Feature | Status |
|---|---|
| Open Python project in Thonny | Working |
| Analyze with CodeStruct from Thonny | Working |
| AST + Static analysis | Working |
| Optional runtime analysis (sys.setprofile) | Not started |
| Unified static + dynamic graph | Not started |
| Interactive visualization | Working (React Flow, not Cytoscape.js) |
| Source traceability — display | Working (path:line:col shown in DetailsPanel) |
| Source traceability — navigation | Not implemented |
| Right-click → Go to Definition | Not implemented |
| Thonny navigate to file+line | Not implemented |
| Evidence-aware graph | Implemented (EvidenceRecord with origin, confidence) |
| NetworkX graph metrics | Not started |
| Architecture analysis | Not started |
| LLM/RAG layer | Not started |
| Graphviz export | Not started (JSON export exists) |
| Custom Symbol Resolver | Implemented (conservative, non-executing) |
| SQLite/JSON storage | Implemented |
| pytest test suite | Partial (not confirmed running) |

---

## 12. Gap Analysis

| Priority | Feature | Expected Behavior | Current State | Gap | Dependencies | Suggested Agent |
|---|---|---|---|---|---|---|
| P0 | "Open in editor" button | Click node location → Thonny opens file at line | Location text only; no action | Button missing, endpoint missing, Thonny receiver missing | Graph has location data | @frontend + @backend + @ide |
| P0 | onNavigateSource wired in App.jsx | Real handler function | Always null | Handler never defined | Backend endpoint | @frontend |
| P0 | Backend navigate endpoint | POST /api/v1/editor/navigate → store command | Does not exist | Entire endpoint absent | Thonny polling | @backend |
| P0 | Thonny navigation receiver | Poll navigate endpoint → show_file_at_line() | Does not exist | No poll loop | Backend endpoint | @ide |
| P1 | Right-click context menu | Open source, copy name, find references | No context menu | Missing interaction | Navigation infrastructure | @frontend |
| P1 | Dynamic analysis | Runtime call graph merged with static graph | Not started | Entire module absent | Static graph (done) | @parser |
| P1 | NetworkX graph metrics | Centrality, coupling, cycles in API | Not implemented | Missing entirely | Graph model (done) | @graph |
| P2 | Graphviz export | DOT/SVG/PNG export | JSON export only | Graphviz not integrated | Graph model | @graph + @frontend |
| P2 | Incremental file cache | Only re-parse changed files | Full reanalysis | Per-file mtime cache absent | Storage layer | @backend |
| P2 | Variable tracking | Module/class variables as nodes | Not extracted | Parser doesn't visit Assign | Parser models | @parser |
| P2 | Architecture metrics display | Fan-in, fan-out in details panel | Not computed | No metrics layer | NetworkX | @graph + @frontend |
| P3 | LLM/RAG summaries | Natural-language entity descriptions | Not started | No LLM integration | Everything else | @backend |
| P3 | Type stub integration | Better external resolution | Not started | No stub lookup | Resolver | @parser |
| P3 | Community/cluster detection | Module grouping by density | Not started | No community algorithm | NetworkX | @graph |

---

## 13. Dependency Analysis

```
Level 0 — DONE:
  Python AST parsing + entity extraction
  Graph model + builder + resolver
  SQLite storage + job system
  REST API (analyses, projects, editor)
  Frontend rendering + filtering + details

Level 1 — P0 (blocks core UX, must do together):
  Backend: POST /api/v1/editor/navigate endpoint
  Frontend: onNavigateSource handler in App.jsx
  Frontend DetailsPanel: "Open in editor" button
  Thonny: Polling receiver + show_file_at_line

Level 2 — P1 (after Level 1):
  Context menu (depends on navigation)
  Dynamic analysis (depends on graph model — done)
  NetworkX metrics (depends on graph model — done)

Level 3 — P2:
  Graphviz export
  Incremental file cache
  Variable extraction
  Metrics display in UI

Level 4 — P3:
  LLM/RAG
  Type stubs
  Community detection
```

---

## 14. Prioritized Backlog

### P0 — Critical (blocks core navigation workflow) — COMPLETED

| Task ID | Module | Task | Status | Expected Result | Verification |
|---|---|---|---|---|---|
| CS-P0-001 | Backend API | Add POST /api/v1/editor/navigate, GET .../pending, POST .../acknowledge endpoints; store pending navigate command with session token | **Completed** | 200 response with command ID; pending returns it, acknowledge consumes it | 9 contract tests in `test_navigate_routes.py` passing; 88% coverage |
| CS-P0-002 | Thonny Plugin | Add wb.after() poll loop: GET /api/v1/editor/navigate/pending; on command, call show_file_at_line(absolute_path, line) | **Completed** | Thonny receives navigate command and shows file at line | Plugin updated, ruff lint clean |
| CS-P0-003 | Frontend App | Define handleNavigateSource in App.jsx; POST to /api/v1/editor/navigate; pass as onNavigateSource to ArchitectureExplorer | **Completed** | onNavigateSource handles both line and startLine formats | All 67 vitest tests passing |
| CS-P0-004 | Frontend DetailsPanel | Add "Open in editor" button next to source location; call onNavigateSource({path, line}) on click | **Completed** | Buttons rendered and tested in DetailsPanel | DetailsPanel tests passing |

### P1 — Required for usable MVP — COMPLETED

| Task ID | Module | Task | Status | Expected Result | Verification |
|---|---|---|---|---|---|
| CS-P1-001 | Frontend | Add right-click context menu on graph nodes: Open in editor, View details, Center canvas, Copy qualified name, Copy path | **Completed** | Keyboard-navigable accessible context menu on right-click | 4 vitest tests in `NodeContextMenu.component.test.jsx`, axe a11y clean |
| CS-P1-002 | Backend Analysis | Add sys.setprofile-based dynamic call tracer; merge into static graph with RUNTIME_OBSERVED evidence | **Completed** | Dynamic calls and execution stats in unified graph | 4 pytest tests in `test_dynamic_tracer.py`, bytecode return inspection |
| CS-P1-003 | Backend Graph | Add graph metric computation (ADR-002 port adapter): fan-in, fan-out, centrality, instability, cycle detection | **Completed** | Nodes enriched with metrics attributes without breaking schema contract | 4 pytest tests in `test_graph_metrics.py` |
| CS-P1-004 | Frontend DetailsPanel | Display fan-in, fan-out, instability, centrality, cycle participation in Architecture metrics section | **Completed** | Metrics visible in DetailsPanel when attributes present | Unit test in `DetailsPanel.component.test.jsx`, 73 vitest tests passing |

### P2 — Important improvement — COMPLETED

| Task ID | Module | Task | Status | Expected Result | Verification |
|---|---|---|---|---|---|
| CS-P2-001 | Backend Analysis | Extract Assign/AnnAssign variable nodes | **Completed** | Module and class variables tracked in AST visitor | Unit test in `test_python_parser.py` |
| CS-P2-002 | Backend Graph | Add GET /api/v1/analyses/{id}/export/dot endpoint | **Completed** | DOT file download with hierarchical clustering | 3 tests in `test_export_dot.py` |
| CS-P2-003 | Frontend Toolbar | Add Export as Graphviz button | **Completed** | Download triggers from More menu with client fallback | `architecture.test.js` passing |
| CS-P2-004 | Backend Storage | Per-file mtime-based incremental cache | **Completed** | Only changed files re-parsed via `FileParseCache` | 2 tests in `test_python_parser.py` |
| CS-P2-005 | Frontend | Verify graphAdapter.js schema 1.0.0 handling | **Completed** | Strict schema validation with no errors | All frontend tests passing |

### P3 — Enhancements

| Task ID | Module | Task | Status | Expected Result | Verification |
|---|---|---|---|---|---|
| CS-P3-001 | Backend / UI | Semantic explanation layer (LLM/RAG) with offline rule-based synthesis & pluggable provider | **Completed** | Node explanation endpoint & DetailsPanel AI explain card | 8 tests in `test_llm_summary.py`, 3 in `test_explain_route.py` |
| CS-P3-002 | Backend | Type stub (.pyi) discovery, parsing, and prioritized symbol resolution | **Completed** | .pyi files scanned and resolved behind .py implementations | 4 tests in `test_type_stubs.py` |
| CS-P3-003 | Backend Graph | Community/cluster detection via connected component clustering | **Completed** | `community_id` in node metrics and DetailsPanel | Unit test in `test_graph_metrics.py` |
| CS-P3-004 | Backend | Git evolution analysis | Backlog | Git commit frequency and churn metrics | Future iteration |

---

## 15. Proposed Subagent Structure

**@parser** — `backend/src/codestruct/analysis/`
Tasks: CS-P1-002 (dynamic analysis), CS-P2-001 (variable extraction)

**@graph** — `backend/src/codestruct/graph/`
Tasks: CS-P1-003 (NetworkX metrics), CS-P2-002 (Graphviz), CS-P3-003 (community)

**@backend** — `backend/src/codestruct/api/`, `jobs/`, `storage/`
Tasks: CS-P0-001 (navigate endpoint), CS-P2-004 (incremental cache)

**@frontend** — `frontend/src/`
Tasks: CS-P0-003 (onNavigateSource), CS-P0-004 (Open in editor button), CS-P1-001 (context menu), CS-P2-003 (export)

**@ide** — `thonny-plugin/thonnycontrib/codestruct/__init__.py`
Tasks: CS-P0-002 (Thonny navigation receiver)

**@integration** — cross-cutting
Tasks: End-to-end verification of P0 navigation chain

**@testing** — `tests/`
Tasks: Run existing tests, write P0 regression tests, E2E verification

---

## 16. Agent Assignment Plan

**Phase 1 (Parallel — independent):**
- @backend → CS-P0-001: Add navigate endpoint
- @frontend → Audit DetailsPanel onNavigateSource call sites precisely

**Phase 2 (After CS-P0-001):**
- @ide → CS-P0-002: Add Thonny polling receiver
- @frontend → CS-P0-003 + CS-P0-004: Wire handler + add button

**Phase 3 (Integration):**
- @integration → End-to-end test: Thonny → analyze → frontend → click "Open in editor" → Thonny navigates

**Phase 4 (P1 features, parallel after P0 complete):**
- @parser → CS-P1-002 (dynamic analysis)
- @graph → CS-P1-003 (NetworkX metrics)
- @frontend → CS-P1-001 (context menu) + CS-P1-004 (metrics display)

---

## 17. Integration Order

```
[DONE] Python scanning → parsing → entity extraction
[DONE] Graph building → relationship resolution → serialization
[DONE] Job system → SQLite → REST API
[DONE] Frontend rendering → filtering → details panel (display only)

[P0] Backend navigate endpoint  →  Frontend onNavigateSource handler
                                →  DetailsPanel "Open in editor" button
                                →  Thonny polling receiver
                                ↓
          [MILESTONE 6] Full navigation: graph node → open file at line in Thonny

[P1] Context menu  |  Dynamic analysis  |  NetworkX metrics

[P2-P3] Graphviz, variables, LLM — after core is stable
```

---

## 18. Testing Strategy

**Run existing tests first (confirm baseline):**
```powershell
python -m pytest -m "unit or contract" --no-cov
python -m pytest -m "not performance and not slow"
npm --prefix frontend test
```

**New tests for P0:**
1. CS-P0-001: test_navigate_endpoint.py — POST navigate, GET pending, mark consumed
2. CS-P0-002: Plugin unit test for polling loop (mock backend responses)
3. CS-P0-003: App.component.test.jsx — verify onNavigateSource is a function
4. CS-P0-004: DetailsPanel.component.test.jsx — button visible when location present; click calls onNavigateSource correctly

**Regression requirement:** Every P0 change must leave existing test suite green.

**Integration verification target:** Use sample_project (main.py, user.py, database.py) — navigate to user.py definition — verify Thonny opens at correct line.

---

## 19. MVP Completion Criteria

The CodeStruct MVP is complete when this flow succeeds on a real multi-file Python project:

```
[✅] 1. Thonny IDE open with Python project
[✅] 2. Tools → Analyze with CodeStruct → submits analysis
[✅] 3. Browser opens → analysis result loads
[✅] 4. Graph renders: modules, classes, functions, imports, inheritance, calls
[✅] 5. Search for known function → highlighted in graph
[✅] 6. Click graph node → DetailsPanel shows type, path, line number
[✅] 7. Click "Open in editor" → Thonny opens file at correct line  ← COMPLETED (P0)
[✅] 8. Correct file path, correct line, cursor positioned correctly  ← COMPLETED (P0)
[✅] 9. Filter by entity type and relationship kind
[✅] 10. View diagnostics and understand unresolved relationships
[✅] 11. Right-click node context menu with navigation, copying, inspection ← COMPLETED (P1)
[✅] 12. Architecture metrics (Fan-in/out, Instability, Centrality, Cycles) ← COMPLETED (P1)
[✅] 13. Graphviz DOT export in backend and toolbar dropdown ← COMPLETED (P2)
[✅] 14. Variable tracking (Assign/AnnAssign at module/class scope) ← COMPLETED (P2)
[✅] 15. Incremental file cache for fast re-parsing of unchanged files ← COMPLETED (P2)
[✅] 16. Dynamic runtime profiling & unified graph merge (`sys.setprofile`) ← COMPLETED (P1)
[✅] 17. Architecture community detection & cluster partitioning ← COMPLETED (P3)
[✅] 18. Semantic explanation layer & AI architecture analysis (`llm_summary.py`) ← COMPLETED (P3)
[✅] 19. Type stub (.pyi) discovery, AST parsing & prioritized symbol resolution ← COMPLETED (P3)
```

---

## Progress Tracker

| Task ID | Priority | Agent | Status | Dependencies | Files | Notes |
|---|---|---|---|---|---|---|
| CS-P0-001 | P0 | @backend | **Completed** | None | `api/routes/navigate.py` | Reverse navigation API with loopback auth & pending command queue |
| CS-P0-002 | P0 | @ide | **Completed** | CS-P0-001 | `thonnycontrib/codestruct/__init__.py` | Thonny `wb.after(500)` poller & editor navigation |
| CS-P0-003 | P0 | @frontend | **Completed** | CS-P0-001 | `frontend/src/App.jsx` | Connected `handleNavigateSource` to `/api/v1/editor/navigate` |
| CS-P0-004 | P0 | @frontend | **Completed** | CS-P0-003 | `DetailsPanel.jsx` | Accessible "Open in editor" buttons on node and reference headers |
| CS-P1-001 | P1 | @frontend | **Completed** | CS-P0-004 | `NodeContextMenu.jsx`, `ArchitectureGraph.jsx` | Right-click context menu (nav, inspect, center, copy) |
| CS-P1-002 | P1 | @parser | **Completed** | None | `analysis/dynamic_tracer.py` | `DynamicTracer` `sys.setprofile` runtime tracing + unified graph merger |
| CS-P1-003 | P1 | @graph | **Completed** | None | `graph/metrics.py`, `graph/builder.py` | ADR-002 GraphAlgorithmPort: Fan-in/out, Instability, Centrality, SCC cycles |
| CS-P1-004 | P1 | @frontend | **Completed** | CS-P1-003 | `DetailsPanel.jsx` | Collapsible "Architecture metrics" panel with Instability and Cycles |
| CS-P2-001 | P2 | @parser | **Completed** | None | `analysis/python_parser.py`, `models.py` | Variable extraction for Assign & AnnAssign at module & class scopes |
| CS-P2-002 | P2 | @graph | **Completed** | None | `graph/export_dot.py`, `api/routes/analyses.py` | Backend DOT export generator and `/export/dot` endpoint |
| CS-P2-003 | P2 | @frontend | **Completed** | CS-P2-002 | `TopToolbar.jsx`, `exportDot.js` | Client-side/server-side DOT export dropdown button |
| CS-P2-004 | P2 | @backend | **Completed** | None | `analysis/python_parser.py` | `FileParseCache` mtime/size incremental per-file cache |
| CS-P3-001 | P3 | @backend | **Completed** | P0+P1 done | `analysis/llm_summary.py`, `api/routes/analyses.py`, `DetailsPanel.jsx` | Offline rule-based + pluggable LLM explainer endpoint & AI explanation panel |
| CS-P3-002 | P3 | @parser | **Completed** | None | `analysis/policy.py`, `analysis/scanner.py`, `graph/resolver.py` | .pyi type stub scanning, parsing & prioritized symbol resolution |
| CS-P3-003 | P3 | @graph | **Completed** | CS-P1-003 | `graph/metrics.py` | Community detection & deterministic component clustering |
| CS-P3-004 | P3 | @backend | Backlog | None | `analysis/git_history.py` | Git evolution analysis |

