# CodeStruct Frontend Architecture & Design Brief (Lovable Specification)

**Document Version:** 1.2.0 (Milestone 1 Deliverable)  
**Target Milestone:** Milestone 3 (Frontend Visual Redesign & Experience Overhaul)  
**Author:** Antigravity (AI Engineering Lead)  
**Audience:** Lovable Design & Engineering Team, Codex Reviewers  

---

## 1. Product Purpose & The Evidence Principle

### 1.1 Product Purpose
CodeStruct is a local-first Python code structure, architecture, and dependency analysis workbench. It empowers software developers and architects to:
1. Visualize module, class, and function hierarchies and call structures within Python codebases.
2. Inspect structural complexity, coupling metrics, and architectural layers.
3. Cross-navigate directly between the interactive browser graph and their active IDE (e.g., Thonny or VS Code) with sub-second cursor alignment.

### 1.2 The Core Evidence Principle
CodeStruct adheres to a strict architectural rule: **Truth in Representation**.
- Every edge, node, and call relationship shown in the graph is backed by verifiable AST analysis or deterministic dynamic trace evidence.
- Hypothetical, ambiguous, or dynamic-runtime calls must never be hallucinated or depicted as definitive static dependencies.
- Nodes or edges with partial resolution must display appropriate provenance badges and indicators. The user must always be able to click an element and view the exact evidence span (source file, line number, column range, and extraction method).

---

## 2. Architecture, Security Boundaries & Deployment Modes

### 2.1 Local Proxy & Loopback Invariants
CodeStruct operates strictly in local environments. Production architectures and prototype setups run on local loopback:
- **Backend API:** Bound to `http://127.0.0.1:8000` (or configured loopback port).
- **Frontend Viewer:** Served via Vite at `http://127.0.0.1:5173` (or built static SPA mounted at `/app`).
- **Proxy Configuration:** The frontend dev server proxies all `/api/v1` requests directly to `http://127.0.0.1:8000`.
- **Loopback Enforcement:** All editor capability registration and navigation endpoints reject requests from non-loopback addresses (HTTP 403 `EDITOR_ACCESS_DENIED`) and validate loopback `Origin`/`Referer` headers (HTTP 403 `UNTRUSTED_ORIGIN`).
- **Session Credentials:** When launched from an IDE adapter, the frontend receives `session_token` and `analysis_id` as URL query parameters (e.g. `http://127.0.0.1:5173/?analysis_id=ana_...&session_token=cap_...`). The frontend securely captures this token for editor navigation dispatches and scrubs credentials from the browser address bar immediately on mount. When switching projects or submitting a new analysis, previous session tokens are discarded.
- **Local Roots Only:** No arbitrary file upload mechanism exists; analyses are dispatched exclusively against authorized local directory roots identified by `root_id` or `capability_id`.

### 2.2 Local Dev vs. Hosted Preview Modes
- **Local Dev Mode:** Requests proxy through Vite to `http://127.0.0.1:8000`. Full real-time analysis, polling, and IDE navigation are enabled against authorized local project directories.
- **Hosted / Storybook / Mock Preview Mode:** Loads canonical fixtures directly from `docs/frontend-contract/*.json` or `src/features/architecture/fixtures/graphFixtures.js` with simulated latency and deterministic mock data. No live backend or arbitrary filesystem access is attempted. In hosted preview, no local loopback promises are made, no source files are uploaded, and no external or paid provider API calls are performed.

---

## 3. Application Lifecycle & Job States

The backend analysis job lifecycle is governed by the authoritative `JobState` state machine in `backend/src/codestruct/jobs/models.py`:

```
submitted ──► validating ──► queued ──► scanning ──► parsing ──► resolving ──► building_graph ──► computing_metrics ──► completed
    │              │                                                                                                    ▲
    │              └────────► cache_hit ────────────────────────────────────────────────────────────────────────────────┘
    │
    ├────────► partially_completed (completed with non-fatal diagnostics)
    ├────────► cancellation_requested ──► cancelled
    └────────► failed
```

### 3.1 Supported Job States
| JobState | UI Presentation & Behavior |
| :--- | :--- |
| `submitted` | Initial job receipt; displays loading skeleton. |
| `validating` | Pre-flight validation of authorized root and analysis options. |
| `queued` | Queued in worker executor pool waiting for worker slot. |
| `scanning` | Discovering source files and computing directory manifest. |
| `parsing` | AST parsing of modules, classes, and function signatures. |
| `resolving` | Symbol resolution and import graph construction. |
| `building_graph` | Constructing unified graph representation. |
| `computing_metrics` | Calculating coupling and cohesion metrics. |
| `cache_hit` | Reused prior deterministic analysis result from SQLite/WAL cache; transitions to `completed`. |
| `completed` | Full success; graph canvas and details panel fully populated. |
| `partially_completed` | Analysis completed with non-fatal diagnostics (e.g. unresolvable imports); displays amber status banner and diagnostics tray. |
| `cancellation_requested` | User initiated cancellation (`DELETE /api/v1/analyses/{id}`); inputs disabled while worker completes safe cleanup. |
| `cancelled` | Analysis was cancelled before completion; offers "Restart Analysis" button. |
| `failed` | Analysis encountered a fatal error (e.g. `ANALYSIS_TIMEOUT`, `PROJECT_UNAUTHORIZED`); displays structured error details and retry button. |

*(Note: Timeouts transition the job to `failed` with error code `ANALYSIS_TIMEOUT` in the job record, not a distinct `timed_out` state).*

---

## 4. Current vs. Planned Capabilities

| Capability | Current Status (Milestone 1) | Planned Milestone 3+ Target |
| :--- | :--- | :--- |
| **Graph Renderer** | React Flow (`@xyflow/react`) with custom React card nodes (`ClassCardNode`, `FunctionCardNode`, `DefaultCardNode`). | Enhanced interactive React Flow visual styling and layout presets. |
| **Graph Layout Engine** | Deterministic topological DAG layer positioning (`graphLayout.js`). | Optional `@dagrejs/dagre` or `elkjs` layout adapter plugins. |
| **Pagination & Slicing** | Backend slicing via `limit` (max `max_graph_page_size=1000`) and opaque SHA256 integrity-checked cursor. | Virtualized progressive viewport loading. |
| **Accessibility** | Dual representation: interactive canvas + full synchronized `AccessibleGraphTable` with ARIA roles and keyboard navigation. | Enhanced screen-reader announcement modes and high-contrast theme toggle. |
| **Analysis Scope** | Static Python AST parsing and import resolution. | Dynamic runtime call traces and LLM-assisted role explanations. |

---

## 5. Copy-Pastable API Contracts & Endpoints

All canonical reference payloads reside in `docs/frontend-contract/`:

### 5.1 Project Listing (`GET /api/v1/projects`)
```json
{
  "api_version": "v1",
  "request_id": "req_canonical_projects_01",
  "projects": [
    {
      "id": "sample_service",
      "display_name": "Sample Service",
      "description": "Core backend service workspace",
      "available": true
    }
  ]
}
```

### 5.2 Create Analysis (`POST /api/v1/analyses`)
**Request Body:**
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

> **Note on Analysis Options:** The backend supports base AST analysis and optional structural metrics computation via `options.metrics: bool` (default `false`). When `metrics: true` is requested, the backend calculates coupling (fan-in, fan-out), instability, centrality, cycle membership, component IDs, community IDs, and module architecture metrics, setting `metadata.metrics_computed: true`. Custom grammar (`source_grammar`) and pattern filters (`include_patterns`, `exclude_patterns`) remain unsupported and return HTTP 400 `OPTION_UNSUPPORTED`.

**Response (`202 Accepted`):**
```json
{
  "api_version": "v1",
  "request_id": "req_canonical_job_01",
  "analysis_id": "ana_canonical_12345",
  "state": "submitted",
  "terminal": false,
  "revision": 1,
  "progress": {
    "phase": "submitted",
    "completed": 0,
    "total": 100,
    "unit": "milestone",
    "percent": 0,
    "message_code": "JOB_SUBMITTED",
    "updated_at": "2026-09-26T14:00:00.000000Z"
  },
  "created_at": "2026-09-26T14:00:00.000000Z",
  "started_at": null,
  "updated_at": "2026-09-26T14:00:00.000000Z",
  "completed_at": null,
  "partial": false,
  "cache_hit": false,
  "diagnostics_summary": {
    "info": 0,
    "warning": 0,
    "error": 0
  },
  "result": null,
  "links": {
    "self": "/api/v1/analyses/ana_canonical_12345",
    "graph": null,
    "diagnostics": "/api/v1/analyses/ana_canonical_12345/diagnostics"
  },
  "duplicate_disposition": "new"
}
```

> **Nonterminal Link Invariant & Deterministic Fixtures:** While an analysis is in a nonterminal state (`submitted`, `validating`, `queued`, `scanning`, `parsing`, `resolving`, `building_graph`, `computing_metrics`), `links.graph` is strictly `null` because no usable graph artifact exists yet. `links.graph` is populated only once the analysis reaches `completed` or `partially_completed`. Identifiers (`req_canonical_job_01`, `ana_canonical_12345`) and timestamps are illustrative deterministic fixtures.

### 5.3 Poll Job Status (`GET /api/v1/analyses/{analysis_id}`)
When completed (`state: "completed"`, `terminal: true`):
```json
{
  "api_version": "v1",
  "request_id": "req_canonical_job_02",
  "analysis_id": "ana_canonical_12345",
  "state": "completed",
  "terminal": true,
  "revision": 8,
  "progress": {
    "phase": "completed",
    "completed": 100,
    "total": 100,
    "unit": "milestone",
    "percent": 100,
    "message_code": "ANALYSIS_COMPLETE",
    "updated_at": "2026-09-26T14:00:05.123456Z"
  },
  "created_at": "2026-09-26T14:00:00.000000Z",
  "started_at": "2026-09-26T14:00:01.000000Z",
  "updated_at": "2026-09-26T14:00:05.123456Z",
  "completed_at": "2026-09-26T14:00:05.123456Z",
  "partial": false,
  "cache_hit": false,
  "diagnostics_summary": {
    "info": 0,
    "warning": 0,
    "error": 0
  },
  "result": {
    "result_id": "res_canonical_01",
    "graph_id": "graph_canonical_01",
    "schema_version": "1.0.0",
    "partial": false,
    "cache_hit": false,
    "summary": {
      "source_units_total": 1,
      "nodes_total": 3,
      "edges_total": 2,
      "evidence_total": 2,
      "diagnostics_total": 0,
      "nodes_by_kind": {
        "module": 1,
        "class": 1,
        "function": 1
      },
      "edges_by_kind": {
        "defines": 2
      },
      "edges_by_resolution": {
        "resolved": 2
      },
      "edges_by_confidence": {
        "high": 2
      },
      "diagnostics_by_severity": {},
      "diagnostics_by_code": {},
      "excluded_entries": 0,
      "failed_files": 0,
      "skipped_files": 0,
      "describes_full_result": true
    }
  },
  "links": {
    "self": "/api/v1/analyses/ana_canonical_12345",
    "graph": "/api/v1/analyses/ana_canonical_12345/graph",
    "diagnostics": "/api/v1/analyses/ana_canonical_12345/diagnostics"
  },
  "duplicate_disposition": null
}
```

### 5.4 Cancel Analysis (`DELETE /api/v1/analyses/{analysis_id}`)
- **Active Job Cancellation:** Cancelling an active or queued analysis transitions it to `state: "cancellation_requested"` (HTTP 202) or `state: "cancelled"` (HTTP 200).
- **Idempotent Cancellation:** Cancelling an already-`cancelled` job is idempotent: it returns HTTP 200 with the existing cancelled `JobResponse`.
- **Terminal State Conflict:** Attempting to cancel an analysis that has already reached another terminal state (`completed`, `partially_completed`, or `failed`) returns HTTP 409 `JOB_TERMINAL` (`recoverable: false`).

### 5.5 Structured API Errors
All API errors return a standard JSON envelope with `api_version`, `request_id`, and structured `error`:
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

Validation error example (`422 Unprocessable Entity`):
```json
{
  "api_version": "v1",
  "request_id": "req_canonical_val_err_01",
  "error": {
    "code": "REQUEST_INVALID",
    "message": "The request did not match the API contract.",
    "recoverable": true,
    "field_errors": [],
    "safe_context": {},
    "retry_after_seconds": null
  }
}
```

Common error codes:
- `JOB_NOT_FOUND` (404): Analysis ID not found in registry or has expired.
- `RESULT_EXPIRED` (410): Analysis retained result has expired.
- `OPTION_UNSUPPORTED` (400): Custom options (e.g. custom `source_grammar`, pattern inclusion/exclusion filters) that are not supported in this API version.
- `PROJECT_SELECTION_REQUIRED` (400): Neither root_id nor capability_id provided in creation request.
- `REQUEST_INVALID` (422): Request schema validation error (malformed JSON or invalid parameter types).
- `PROJECT_UNAUTHORIZED` (403): Target path is outside authorized roots or uses symlinks/reparse points.
- `PROJECT_NOT_FOUND` (404): Target project root or file not found on disk.
- `QUEUE_FULL` (429): Max queued job capacity reached (`retry_after_seconds: 1`).
- `JOB_TERMINAL` (409): Analysis is already completed, partially completed, or failed.
- `RESULT_NOT_READY` (409): Graph result requested before analysis completes.
- `RESULT_UNAVAILABLE` (409): Terminal job produced no usable graph result.
- `GRAPH_TOO_LARGE` (413): Complete unpaged graph exceeds `max_full_graph_bytes` (default 4194304 bytes / 4 MiB, configurable via `CODESTRUCT_MAX_FULL_GRAPH_BYTES`); request a bounded page.
- `PAGE_LIMIT_EXCEEDED` (413): Explicit `limit` exceeds server `max_graph_page_size` (1000).
- `CURSOR_INVALID` (400): Graph cursor is invalid, tampered with, or belongs to another result.
- `NODE_NOT_FOUND` (404): Specified node identifier does not exist in graph.
- `EDITOR_ACCESS_DENIED` (403): Editor integration accessed from non-loopback address.
- `UNTRUSTED_ORIGIN` (403): Non-loopback Origin or Referer header.

### 5.6 Graph Slicing & Pagination (`GET /api/v1/analyses/{id}/graph`)
- **Query Parameters:** `limit` (int, optional), `cursor` (opaque string, optional), `node_kind`, `edge_kind`, `resolution_status`.
- **Full Result vs. Paged Slicing:**
  - **Omitted `limit` (Full Graph):** When `limit` is omitted, the server returns the complete unpaged graph. This request is governed by `max_full_graph_bytes` (default 4194304 bytes / 4 MiB, configurable via `CODESTRUCT_MAX_FULL_GRAPH_BYTES`), NOT by `max_graph_page_size`. If the full graph exceeds `max_full_graph_bytes`, the server returns HTTP 413 `GRAPH_TOO_LARGE`, instructing the client to paginate.
  - **Explicit `limit` (Bounded Page):** When `limit` is specified, it must be between 1 and `max_graph_page_size` (1000). If `limit > max_graph_page_size`, the server returns HTTP 413 `PAGE_LIMIT_EXCEEDED`.
- **Cursor Semantics:** Cursors are opaque base64-encoded JSON payloads encoding offset and active filter parameters, validated with a SHA256 integrity hash of `codestruct-v1-local-cursor` plus payload body.
- **Client Recommendation:** Request an explicit bounded page (e.g. `?limit=1000`) on initial load for predictable rendering latency.

**Fixture vs. Paged Slicing Example:**
- **Complete Toy Graph Fixture (`docs/frontend-contract/graph_slice.json`):** The checked-in file `graph_slice.json` represents the complete unpaged toy result (3 total nodes, 2 total edges, `next_cursor: null`, `partial_load: false`).
- **Generated Paged Response (`limit=1`):** The inline JSON example below is generated directly by `slice_graph` from this toy fixture using graph ID `graph_canonical_01` and filters `{node_kind: null, edge_kind: null, resolution_status: null, limit: 1}`. Notice that although `limit=1` applies to the sliced node window, `slice_graph` automatically includes the endpoint nodes for all returned relationships (here `node_pkg_service_class` is the target of `edge_01`), resulting in `returned_nodes: 2`. The opaque `next_cursor` encodes offset `1` with SHA256 integrity protection and can be supplied to subsequent requests to continue paging.

```json
{
  "api_version": "v1",
  "request_id": "req_canonical_graph_01",
  "schema_version": "1.0.0",
  "metadata": {
    "analysis_id": "ana_canonical_01",
    "result_id": "res_canonical_01",
    "graph_id": "graph_canonical_01",
    "schema_version": "1.0.0",
    "api_version": "v1",
    "analyzer_version": "0.1.0",
    "python_runtime": "3.12.0",
    "source_language": "python",
    "source_grammar": "3.12",
    "policy_fingerprint": null,
    "project_fingerprint": null,
    "started_at": "2026-09-26T14:00:00.000000Z",
    "finished_at": "2026-09-26T14:00:05.000000Z",
    "duration_ms": 5000,
    "cache": {},
    "partial": false,
    "partial_reasons": [],
    "exclusions": {},
    "limits": {}
  },
  "summary": {
    "source_units_total": 1,
    "nodes_total": 3,
    "edges_total": 2,
    "evidence_total": 2,
    "diagnostics_total": 0,
    "nodes_by_kind": {
      "module": 1,
      "class": 1,
      "function": 1
    },
    "edges_by_kind": {
      "defines": 2
    },
    "edges_by_resolution": {
      "resolved": 2
    },
    "edges_by_confidence": {
      "high": 2
    },
    "diagnostics_by_severity": {},
    "diagnostics_by_code": {},
    "excluded_entries": 0,
    "failed_files": 0,
    "skipped_files": 0,
    "describes_full_result": true
  },
  "nodes": [
    {
      "id": "node_pkg_module",
      "kind": "module",
      "name": "module",
      "qualified_name": "pkg.module",
      "parent_id": null,
      "module_id": null,
      "file_id": null,
      "location": {
        "source_unit_id": "src_pkg_module",
        "path": "pkg/module.py",
        "start_line": 1,
        "start_column": 1,
        "end_line": 35,
        "end_column": 1
      },
      "modifiers": [],
      "attributes": {
        "docstring": "Service module implementation."
      }
    },
    {
      "id": "node_pkg_service_class",
      "kind": "class",
      "name": "ServiceHandler",
      "qualified_name": "pkg.module.ServiceHandler",
      "parent_id": "node_pkg_module",
      "module_id": "node_pkg_module",
      "file_id": null,
      "location": {
        "source_unit_id": "src_pkg_module",
        "path": "pkg/module.py",
        "start_line": 10,
        "start_column": 1,
        "end_line": 30,
        "end_column": 1
      },
      "modifiers": [],
      "attributes": {
        "methods_count": "2"
      }
    }
  ],
  "edges": [
    {
      "id": "edge_01",
      "kind": "defines",
      "source_id": "node_pkg_module",
      "target_id": "node_pkg_service_class",
      "target_reference": null,
      "resolution_status": "resolved",
      "confidence": "high",
      "confidence_reason": null,
      "candidate_ids": [],
      "evidence_ids": [
        "ev_01"
      ],
      "occurrence_count": 1,
      "diagnostic_ids": [],
      "attributes": {}
    }
  ],
  "evidence": [
    {
      "evidence_id": "ev_01",
      "origin": "source_ast",
      "observation_kind": "class_definition",
      "location": {
        "source_unit_id": "src_pkg_module",
        "path": "pkg/module.py",
        "start_line": 10,
        "start_column": 1,
        "end_line": 10,
        "end_column": 22
      },
      "observed_text_hash": null,
      "excerpt": "class ServiceHandler:",
      "explanation": "AST class definition node at line 10",
      "expression": null
    }
  ],
  "diagnostics": [],
  "page": {
    "returned_nodes": 2,
    "total_nodes": 3,
    "returned_edges": 1,
    "total_edges": 2,
    "next_cursor": "eyJmIjp7ImVkZ2Vfa2luZCI6bnVsbCwibGltaXQiOjEsIm5vZGVfa2luZCI6bnVsbCwicmVzb2x1dGlvbl9zdGF0dXMiOm51bGx9LCJnIjoiZ3JhcGhfY2Fub25pY2FsXzAxIiwibyI6MX0uMjY1NzVmMTc5NjY5ODMwZmY1Nzk5YzA0",
    "partial_load": true
  }
}
```

### 5.7 Analysis Diagnostics (`GET /api/v1/analyses/{analysis_id}/diagnostics`)
Returns structured static parser and symbol resolution diagnostics (`docs/frontend-contract/diagnostics.json`):
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

> **Diagnostic Field Guarantees & Nullability:**
> - **Canonical Fields:** Each diagnostic item includes canonical `id`, `code`, `severity` (`info` | `warning` | `error`), `phase` (`scanning` | `parsing` | `resolving` | `building_graph` | `computing_metrics`), `message`, `recoverable`, `consequence`, `suggested_action`, and `details`.
> - **Nullable Location & References:** `location` is nullable. Whole-file encoding failures, scanning exclusions, or structural graph-level cycles have `location: null`. Likewise, `entity_id` and `edge_id` are nullable and populated only when a specific graph element is associated. Furthermore, span endpoints (`end_line`, `end_column`) within `location` are optional and may be null or 0.
> - **Navigation Degradation:** When `location` is `null` or lacks valid start line coordinates (`start_line`), editor source cross-navigation is disabled while diagnostic text, severity badges, and details are displayed in full. Clients must not fabricate fake file paths or line numbers when `location` is `null`.

### 5.8 Node Explanation (`GET /api/v1/analyses/{analysis_id}/nodes/{node_id}/explain`)
```json
{
  "api_version": "v1",
  "request_id": "req_canonical_expl_01",
  "node_id": "node_pkg_service_process_fn",
  "name": "process_request",
  "kind": "function",
  "role": "Entrypoint Handler",
  "summary": "Handles incoming request processing and coordinates business logic execution.",
  "dependencies_summary": "Depends on ServiceHandler instance and incoming request payload.",
  "metrics_summary": "Coupling: In-degree 1, Out-degree 0.",
  "recommendations": [
    "Ensure input validation on payload before business processing."
  ],
  "prompt": null,
  "provider": "rule-based"
}
```

### 5.9 Export DOT (`GET /api/v1/analyses/{analysis_id}/export/dot`)
Returns `text/vnd.graphviz` with `Content-Disposition: attachment; filename="codestruct-{analysis_id}.dot"`.

### 5.10 Editor Cross-Navigation Loop
1. **Selection (`POST /api/v1/editor/selection`):** IDE registers active file, returns `capability_id` (used as `session_token`).
2. **Navigate (`POST /api/v1/editor/navigate`):** Frontend dispatches navigation with `{ session_token, relative_path, line, column }`.
3. **Pending (`GET /api/v1/editor/navigate/pending`):** IDE adapter polls loopback endpoint for queued navigation command.
4. **Acknowledge (`POST /api/v1/editor/navigate/acknowledge`):** IDE reports `{ session_token, command_id, status: "delivered"|"failed", reason }`.

---

## 6. Frontend Accessibility & UX Requirements

1. **Full Keyboard Navigation:** Tab navigation, Enter to inspect, Escape to close panels, arrow keys for table navigation.
2. **Accessible Table View:** Full DOM parity through `AccessibleGraphTable` with column sorting, filtering, and ARIA labels.
3. **`prefers-reduced-motion`:** Disables all canvas transitions, zoom animations, and pulsing loaders when requested by user OS.
4. **ARIA Live Regions:** Dynamic job progress updates and navigation alerts rendered with `role="status"` and `role="alert"`.
