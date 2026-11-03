# CodeStruct — Agent Build Specification

**This is a specification to execute, not a document to read casually.** It is written for two roles: **Brain** (orchestrator — reads this spec, writes `prompt.md` per phase, reviews `report.md`) and **Implementer/Antigravity** (writes code, runs tests, writes `report.md`). Follow it literally. Exact paths, exact field names, exact JSON shapes, exact test commands, exact Success Criteria — nothing here should require guessing or paraphrasing.

**Version:** 1.2

## STATUS AT A GLANCE

| Phases | Status |
|---|---|
| 0–10 (MVP) | **DONE, verified** |
| 11 (multi-project support, approved addendum) | **DONE, verified** |
| 12–13 (Sprint 2, 10h budget, staff demo) | **DONE, substantively verified — 2 corrections outstanding:** (1) the Sprint 2 regression report's edge description names a nonexistent `run_simulation` function; correct it to the real edges (`main`→`build_zoo`, `build_zoo`→`Zoo.add_animal`); (2) the project folder tree is duplicated (a full `codestruct/` package copy plus a second copy of `tests/`/`sample_project/`/`docs/` at the root) — consolidate to one canonical layout |
| Sprint 2 corrections (edge-description fix, folder consolidation) | **DONE, verified** |
| 14 (caching) | **DONE, verified** — cache-invalidation on modify/delete confirmed with a real cross-file fixture and passing tests |
| 15 (change-impact analysis) | **DONE, verified** — backend oracle exact match, UI sync confirmed via live DOM state checks |
| 17 (UI/UX overhaul) | **DONE, verified** — fonts confirmed loading via `document.fonts.check()`, structural behaviors confirmed via CDP automation, toolbar deduplication verified (Follow-Up 1), and Inspector/Qwen persistent re-expand rails verified (Follow-Up 2). |
| 16 (dynamic/runtime execution) | **NOT STARTED — gated.** Needs a security/sandboxing design before any implementation. Do not touch without that design being written and reviewed first. |

`PROGRESS.md`, in the project root, is the authoritative current-phase tracker. If it disagrees with the table above, trust `PROGRESS.md` and update this table to match.

---

## 0. Rules (binding — read before acting)

1. Work phases **in order**. Never start phase *N+1* until phase *N*'s Success Criteria are all checked off with real evidence (actual command output, not a claim of success).
2. **One phase per `prompt.md`.** Never bundle two phases into one implementation pass.
3. A phase's **Guardrails are a hard stop**, not a suggestion — do not implement out-of-scope work even if it looks easy, related, or helpful. See the current Backlog in Section 9 for what is deliberately not being built right now.
4. If something a phase needs is not specified here, **stop and ask the human** rather than guessing or inventing a rule.
5. Full operating procedure (the `prompt.md`/`report.md` loop, verification rules, escalation rules) lives in `Brain_Orchestrator_Prompt.md` — read that alongside this spec, it governs *how* to work; this document governs *what* to build.

---

## 1. Project Overview

CodeStruct is a single-window desktop tool that statically analyzes a Python project's structure (modules, classes, functions, methods, and their relationships) using Python's built-in `ast` module, and renders it as an interactive graph. It includes a project explorer, a symbol inspector, a read-only source code viewer, and a local AI assistant (Qwen 2.5-coder:3b via Ollama) that can explain selected code using the same analysis data as context.

This is a ground-up rebuild. The previous implementation (tkinter + embedded Thonny via Win32 `SetParent`) failed because it tried to visually embed a separate IDE process inside a second, separately-built UI, causing freezing and unresponsive panels. This rebuild avoids that failure mode entirely by using **one process, one window, no embedded subprocess UI**.

## 2. Goals & Non-Goals

### In scope (build this)
- AST-based static analysis: modules, classes, functions, methods; relationships: `inherits`, `defines`, `constructs`, `calls`.
- One native window (FastAPI backend + `pywebview` frontend) — no second window, no embedded IDE.
- Interactive graph view (Cytoscape.js): pan, zoom, fit, kind filter.
- Left-dock Explorer: file/symbol tree, filterable.
- Inspector panel: symbol details, fan-in/fan-out, relationships, jump-to-source.
- Read-only, syntax-highlighted Code Viewer with jump-to-line (replaces the old embedded-Thonny idea).
- Qwen Assistant panel: chat via local Ollama, with selected-symbol context injected into prompts.
- Status/log area: node/edge counts, per-file parse errors/warnings.
- One-page quick-start doc for non-technical users.

### Explicitly out of scope for this build (do not implement; backlog only)
- Dynamic/runtime execution analysis of the target project.
- Change-impact analysis (transitive ripple-effect).
- Design-pattern detection.
- Persistent/incremental caching (SQLite or otherwise).
- Installer/packaging, desktop shortcuts, auto-update.
- Any embedded or subprocess-controlled external IDE (Thonny or otherwise) — **permanently dropped**, not deferred. Editing happens outside this app, via an OS "open file" call at most.
- Resolving polymorphic method calls to a specific subclass (see Section 7 for exactly what call resolution *is* required).
- Multi-project, multi-user, or networked operation.

## 3. Architecture

**Process model:** one Python process. FastAPI serves a local HTTP API and the frontend's static files; `pywebview` opens exactly one native window pointed at that local server. No subprocesses are spawned for UI purposes. (An "open in system editor" action, if implemented as a stretch item, is the only allowed subprocess launch, and it never shares a window with this app.)

**Tech stack (fixed — do not substitute without updating this document):**
| Layer | Choice |
|---|---|
| Backend framework | FastAPI + Uvicorn |
| Native window | `pywebview` |
| Graph rendering | Cytoscape.js (vendored local copy, not a CDN dependency, so the app works offline) |
| Syntax highlighting | Pygments (server-side, renders HTML) |
| AI backend | Ollama local HTTP API, model `qwen2.5-coder:3b`, endpoint `http://localhost:11434/api/chat` |
| Analysis | Python standard library `ast` module only — no third-party parsing libraries |
| Language/runtime | Python 3.10+ |

**Folder structure (create exactly this layout):**
```
codestruct/
  backend/
    __init__.py
    main.py            # FastAPI app creation, static file mount, pywebview launcher
    analyzer.py         # AST analysis engine (Phase 1)
    schemas.py           # Pydantic models: Node, Edge, Graph, SymbolDetail, ChatRequest, ChatResponse
    api.py                 # API route handlers (Phase 2)
    qwen_client.py          # Ollama HTTP client (Phase 8)
  frontend/
    index.html
    static/
      app.js
      app.css
      vendor/
        cytoscape.min.js
  sample_project/
    sample_project.py    # fixed test fixture — see Section 7, create verbatim
  tests/
    test_analyzer.py
    test_api.py
  docs/
    quick_start.md       # Phase 10
  run.py                   # top-level entry point: `python run.py` starts everything
  requirements.txt
  README.md
```

## 4. Data Contracts

These schemas are fixed for the whole project. Every phase that touches data must conform to them exactly — do not rename fields.

### 4.1 Graph JSON (the core analysis output)
```json
{
  "project_root": "string, absolute or relative path analyzed",
  "generated_at": "ISO-8601 timestamp string",
  "nodes": [
    {
      "id": "string, globally unique, e.g. 'sample_project.Animal.speak'",
      "name": "string, e.g. 'speak'",
      "kind": "module | class | function | method",
      "module": "string, dotted module path, e.g. 'sample_project'",
      "file_path": "string, relative to project_root",
      "lineno": "integer, 1-based start line",
      "end_lineno": "integer, 1-based end line",
      "parent_id": "string or null — containing class id for a method, containing module id for a top-level class/function, null for a module",
      "docstring": "string or null"
    }
  ],
  "edges": [
    {
      "source": "string, node id",
      "target": "string, node id",
      "type": "inherits | defines | constructs | calls"
    }
  ],
  "errors": [
    { "file_path": "string", "message": "string" }
  ],
  "summary": {
    "node_count": "integer",
    "edge_count": "integer",
    "module_count": "integer",
    "class_count": "integer",
    "function_count": "integer",
    "method_count": "integer"
  }
}
```

### 4.2 Symbol Detail (for the Inspector panel)
```json
{
  "id": "string",
  "name": "string",
  "kind": "module | class | function | method",
  "file_path": "string",
  "lineno": "integer",
  "end_lineno": "integer",
  "docstring": "string or null",
  "fan_in": "integer — count of incoming edges",
  "fan_out": "integer — count of outgoing edges",
  "incoming": [ { "id": "string", "name": "string", "type": "edge type" } ],
  "outgoing": [ { "id": "string", "name": "string", "type": "edge type" } ]
}
```

### 4.3 API Endpoints
| Method | Path | Request Body | Response |
|---|---|---|---|
| `POST` | `/api/analyze` | `{ "project_path": "string" }` | Graph JSON (4.1) |
| `GET` | `/api/symbol/{node_id}` | — | Symbol Detail (4.2) |
| `GET` | `/api/source?file_path=...&start=...&end=...` | — | `{ "html": "string (Pygments-highlighted HTML)", "start": int, "end": int }` |
| `POST` | `/api/qwen/chat` | `{ "message": "string", "context_symbol_id": "string or null" }` | `{ "reply": "string" }` |
| `GET` | `/api/qwen/status` | — | `{ "status": "connected" \| "disconnected", "model": "string" }` *(added during Phase 9 to support an immediate startup "Disconnected" badge, per that phase's own Task list)* |
| `GET` | `/api/config` | — | `{ "initial_project_path": "string or null" }` *(added in Phase 11 — see Section 5, Phase 11)* |

Backend must hold the most recent analysis result in memory (a module-level or app-state variable) so `/api/symbol/{id}` and `/api/source` can be served without re-analyzing.

## 5. Phases

Each phase below is independently buildable and independently testable. **Do not skip a phase's testing step.**

---

### Phase 0 — Environment & Scaffolding

**Objective:** A blank single window opens. No analysis, no data, no panels yet — just proof that the process model works.

**Preconditions:** Python 3.10+ installed; Ollama running with `qwen2.5-coder:3b` pulled (verify with `ollama list` before starting — this is outside the phase's build time).

**Tasks:**
1. Create the exact folder structure from Section 3.
2. `requirements.txt`: `fastapi`, `uvicorn`, `pywebview`, `pygments`, `requests`, `pytest`.
3. `backend/main.py`: create a FastAPI app, mount `frontend/static` as static files, serve `frontend/index.html` at `/`. Start Uvicorn in a background thread, then open a `pywebview` window pointed at `http://127.0.0.1:8000/`.
4. `frontend/index.html`: minimal placeholder — a heading that says "CodeStruct" and nothing else.
5. `run.py`: single entry point that imports and runs `backend/main.py`'s startup function.

**Files created:** all scaffold files above.

**Test Procedure:**
1. Run `python run.py`.
2. Confirm **exactly one** OS-level window opens.
3. Confirm the window shows "CodeStruct" with no errors in the terminal.
4. Close the window; confirm the process exits cleanly (no orphaned Uvicorn process left running — check with a process list).

**Success Criteria (all must pass):**
- [ ] One window opens, no second window, no console/terminal window left dangling after close.
- [ ] No unhandled exceptions in terminal output.
- [ ] Process fully exits when the window is closed.

**Guardrails:** Do not add any analysis, graph, or panel code in this phase. Do not use `tkinter` anywhere. Do not spawn Thonny or any other subprocess.

**Est. time:** 1.0h

---

### Phase 1 — Static Analysis Engine

**Objective:** `backend/analyzer.py` can parse a Python project directory and produce correct Graph JSON (Section 4.1), independent of any UI or API.

**Preconditions:** Phase 0 complete.

**Tasks:**
1. Implement `analyze_project(project_root: str) -> dict` in `analyzer.py`, returning the exact shape in Section 4.1.
2. Walk the project directory for `.py` files (use `pathlib`), parse each with `ast.parse`.
3. For each file, extract: the module itself (one node, `kind: "module"`), every top-level `class` (node, `kind: "class"`), every method inside a class (node, `kind: "method"`, `parent_id` = the class's id), every top-level `def` not inside a class (node, `kind: "function"`).
4. Node `id` format: `{module_dotted_path}.{ClassName}.{method_name}` for methods, `{module_dotted_path}.{Name}` for classes/functions, `{module_dotted_path}` for the module itself. Use this format consistently — the frontend and API depend on it.
5. Edges:
   - `defines`: module → each top-level class/function it contains; class → each of its methods.
   - `inherits`: subclass → base class, for each base in a class's bases list (only resolve bases defined within the analyzed project; skip/ignore bases from external libraries without erroring).
   - `constructs`: for each `ast.Call` where the called name matches a known class name in the project, an edge from the *enclosing* function/method to that class.
   - `calls`: for each `ast.Call` where the called name matches a known top-level function, or a known method accessed via `self.` or a locally-assignable variable whose type can be inferred from a direct constructor call in the same function (simple heuristic — see Section 7 for exactly what must resolve), an edge from the enclosing function/method to the called function/method.
6. A file that fails to parse (`SyntaxError` or similar) must not abort the whole analysis — catch the exception, append `{file_path, message}` to `errors`, and continue with the next file.
7. Populate `summary` with accurate counts.
8. `tests/test_analyzer.py`: write `pytest` tests asserting the exact counts defined in Section 7 against `sample_project/sample_project.py` (create that file verbatim from Section 7 first).

**Files created/modified:** `backend/analyzer.py`, `sample_project/sample_project.py`, `tests/test_analyzer.py`.

**Test Procedure:**
1. Run `pytest tests/test_analyzer.py -v`.
2. All assertions from Section 7's "Deterministic Test Oracle" must pass.
3. Manually create one additional `.py` file in a scratch directory with a deliberate syntax error alongside one valid file; run `analyze_project` on that directory; confirm it returns results for the valid file and lists the broken one in `errors` without raising.

**Success Criteria:**
- [ ] `pytest tests/test_analyzer.py` passes with 0 failures.
- [ ] Node count on the fixed sample project equals 16 (see Section 7).
- [ ] `inherits` edge count equals 2, `defines` edge count equals 15, `constructs` edge count equals 3 (see Section 7).
- [ ] A directory containing one broken `.py` file does not crash analysis; the broken file appears in `errors`.

**Guardrails:** Do not attempt to resolve polymorphic calls (e.g., `animal.speak()` where `animal`'s runtime type is ambiguous) beyond what Section 7 specifies — leave such calls unresolved rather than guessing. Do not add caching. Do not execute any code from the analyzed project — this is static analysis only, `ast.parse` and tree-walking, nothing is ever `exec`'d or imported from the target project.

**Est. time:** 3.0h

---

### Phase 2 — Backend API Layer

**Objective:** The three non-chat endpoints in Section 4.3 work against the analysis engine.

**Preconditions:** Phase 1 complete and tested.

**Tasks:**
1. `backend/schemas.py`: Pydantic models mirroring Section 4.1 and 4.2 exactly.
2. `backend/api.py`: implement `POST /api/analyze`, `GET /api/symbol/{node_id}`, `GET /api/source`. Store the last analysis result in app state (e.g., `app.state.last_graph`) so the other two endpoints can read from it without re-analyzing.
3. `/api/symbol/{node_id}`: compute `fan_in`/`fan_out` and `incoming`/`outgoing` lists by filtering the stored graph's edges by `source`/`target` matching `node_id`.
4. `/api/source`: read the given file (resolved relative to the last-analyzed `project_root`), slice lines `start`–`end`, render with Pygments `HtmlFormatter`, return the HTML fragment.
5. Wire these routes into the FastAPI app created in Phase 0.
6. `tests/test_api.py`: use FastAPI's `TestClient` to hit each endpoint against the sample project and assert response shape and key values.

**Files created/modified:** `backend/schemas.py`, `backend/api.py`, `backend/main.py` (route registration), `tests/test_api.py`.

**Test Procedure:**
1. Run `pytest tests/test_api.py -v` — all pass.
2. Start the app (`python run.py`), and from a separate terminal, `curl -X POST http://127.0.0.1:8000/api/analyze -d '{"project_path":"sample_project"}' -H "Content-Type: application/json"` — confirm valid Graph JSON with `node_count: 16`.
3. `curl http://127.0.0.1:8000/api/symbol/sample_project.Dog` — confirm it returns `inherits` under `outgoing` pointing at `sample_project.Animal`.

**Success Criteria:**
- [ ] All three endpoints return valid JSON matching Section 4.1/4.2 shapes.
- [ ] `/api/analyze` on the sample project returns `node_count: 16`.
- [ ] `/api/symbol/sample_project.Dog` includes an `inherits` edge to `sample_project.Animal`.
- [ ] `/api/source` returns non-empty HTML for a valid line range and a clean 4xx (not a crash) for an invalid file path.

**Guardrails:** Do not add authentication — this is a single-user localhost app. Do not add the `/api/qwen/chat` route yet (Phase 8).

**Est. time:** 1.5h

---

### Phase 3 — Frontend Shell Layout

**Objective:** The single-window UI visually matches the reference layout, with all panels present but empty (no live data yet).

**Preconditions:** Phase 0 complete (Phases 1–2 do not block this one; they can run in either order, but do not start Phase 3 before Phase 0).

**Tasks:**
1. Build `frontend/index.html` + `frontend/static/app.css` with this layout: top toolbar (app name, "Open Project" button, "Analyze" button), left dock (Explorer, empty tree placeholder), center area (Graph view placeholder — a labeled empty box), right dock stacked top-to-bottom (Inspector panel placeholder, Qwen Assistant panel placeholder with a chat input box), bottom strip (status/log text area), bottom status bar (node/edge counts, placeholder "0 nodes / 0 edges").
2. Use plain CSS flexbox/grid — no UI framework needed.
3. `frontend/static/app.js`: stub file, no logic yet beyond confirming the DOM loaded.

**Files created/modified:** `frontend/index.html`, `frontend/static/app.css`, `frontend/static/app.js`.

**Test Procedure:**
1. Run `python run.py`.
2. Visually confirm all five regions are present (toolbar, left dock, center graph area, right docks, bottom status/log).
3. Resize the window; confirm no region disappears or overlaps badly.

**Success Criteria:**
- [ ] All five UI regions are visible simultaneously in the one window.
- [ ] No layout overlap or clipped panels at the window's default size.
- [ ] No JavaScript console errors.

**Guardrails:** No live data wiring in this phase — static placeholders only. Do not fetch from the API yet.

**Est. time:** 2.0h

---

### Phase 4 — Graph Visualization

**Objective:** Clicking "Analyze" on a real project renders a navigable graph.

**Preconditions:** Phases 1, 2, and 3 complete and tested.

**Tasks:**
1. Vendor a local copy of `cytoscape.min.js` into `frontend/static/vendor/` (do not load it from a CDN — the app must work offline).
2. "Analyze" button calls `POST /api/analyze` with the current project path (hardcode `sample_project` as the default path for this phase's testing), receives Graph JSON, and renders it in Cytoscape: nodes colored by `kind` (module/class/function/method — four distinct colors), edges drawn with arrows, labeled by `type`.
3. Implement pan, zoom, fit-to-screen controls (Cytoscape built-ins are fine).
4. Implement kind filter checkboxes (module/class/function/method) that show/hide matching nodes.
5. Update the bottom status bar with real `node_count`/`edge_count` from the response.

**Files modified:** `frontend/static/app.js`, `frontend/static/app.css`, `frontend/index.html`.

**Test Procedure:**
1. Run the app, click "Analyze" against `sample_project`.
2. Confirm 16 nodes and the edges described in Section 7 render.
3. Pan and zoom; confirm the view responds.
4. Toggle each kind filter off/on; confirm matching nodes hide/show correctly.
5. Confirm the status bar shows "16 nodes".

**Success Criteria:**
- [ ] Graph renders with the correct node count from Section 7.
- [ ] Pan/zoom/fit all function.
- [ ] Each of the four kind filters correctly hides/shows only its kind.
- [ ] Status bar numbers match the API response.

**Guardrails:** Do not attempt automatic graph layout beyond Cytoscape's built-in layouts (e.g., `cose` or `breadthfirst`) — do not hand-roll a layout algorithm.

**Est. time:** 2.5h

---

### Phase 5 — Explorer Dock + Selection Sync

**Objective:** The left-dock Explorer lists the project's files/symbols and stays in sync with graph selection.

**Preconditions:** Phase 4 complete and tested.

**Tasks:**
1. Populate the Explorer tree from the last Graph JSON: group nodes by `file_path`, then show module → classes → methods / top-level functions, matching the `parent_id` hierarchy.
2. Add a text filter input above the tree that filters visible tree items by substring match on `name`.
3. Clicking a tree item selects the corresponding node in the Cytoscape graph (highlight it, center the view on it).
4. Clicking a node in the graph highlights the corresponding tree item (bidirectional sync).

**Files modified:** `frontend/static/app.js`, `frontend/index.html`.

**Test Procedure:**
1. Click three different items in the Explorer tree (one class, one method, one function); confirm the graph highlights and centers on each in turn.
2. Click three different nodes directly in the graph; confirm the Explorer tree highlights the matching item each time.
3. Type a partial name into the filter box; confirm only matching tree items remain visible.

**Success Criteria:**
- [ ] Explorer → Graph selection works for all three test clicks.
- [ ] Graph → Explorer selection works for all three test clicks.
- [ ] Filter correctly narrows the visible tree.

**Guardrails:** Do not implement file editing in the Explorer — it is a navigation/selection tool only.

**Est. time:** 2.0h

---

### Phase 6 — Inspector Panel

**Objective:** Selecting any symbol populates the Inspector with real data from `/api/symbol/{id}`.

**Preconditions:** Phase 5 complete and tested.

**Tasks:**
1. On any selection event (from Explorer or graph), call `GET /api/symbol/{node_id}` and render: name, kind, file path, line range, docstring (if present), fan-in count, fan-out count, and two lists (Incoming, Outgoing) each showing related symbol name + edge type.
2. Add a "Jump to Source" button in the Inspector (wired up fully in Phase 7).

**Files modified:** `frontend/static/app.js`, `frontend/index.html`.

**Test Procedure:**
1. Select the `Animal` class; confirm Inspector shows 3 methods under relevant lists and correct fan-in/fan-out.
2. Select `Dog`; confirm Inspector shows an `inherits` relationship to `Animal`.
3. Select `main`; confirm Inspector shows a `calls` relationship to `build_zoo`.

**Success Criteria:**
- [ ] All three selections above show correct, non-placeholder data matching Section 7's expected relationships.
- [ ] Inspector updates every time selection changes, with no stale data left from a previous selection.

**Guardrails:** Do not fabricate metrics beyond fan-in/fan-out — no instability/centrality scoring (that was original-project scope, now deferred).

**Est. time:** 2.0h

---

### Phase 7 — Code Viewer

**Objective:** "Jump to Source" shows the real, syntax-highlighted source and scrolls to the right line.

**Preconditions:** Phase 6 complete and tested.

**Tasks:**
1. Add a Code Viewer panel (can replace/overlay the center graph area via a tab or toggle — your call, but it must remain within the single window).
2. Wire "Jump to Source" to call `GET /api/source` with the selected symbol's `file_path`/`lineno`/`end_lineno` (pad a few lines of surrounding context, e.g., ±5 lines, but clearly mark the symbol's own line range, e.g., with a highlighted background).
3. Render the returned HTML; auto-scroll so the symbol's start line is visible.

**Files modified:** `frontend/static/app.js`, `frontend/static/app.css`, `backend/api.py` (if context-padding logic needs adjusting).

**Test Procedure:**
1. Jump to source for `Animal.speak`, `Dog.fetch`, and `build_zoo`; confirm the viewer scrolls to and highlights the correct line range for each of the three.

**Success Criteria:**
- [ ] All three jump-to-source tests land on the correct, correctly-highlighted line range.
- [ ] Viewer is read-only (no edits possible, no save button).

**Guardrails:** Do not implement any write/save capability — this is a read-only viewer, by design (editing happens in the user's own editor, outside this app).

**Est. time:** 1.5h

---

### Phase 8 — Qwen Assistant Integration

**Objective:** The chat panel sends messages to local Ollama, with the selected symbol injected as context, and displays replies.

**Preconditions:** Phase 6 complete (needs symbol selection to exist); Ollama running with `qwen2.5-coder:3b` pulled.

**Tasks:**
1. `backend/qwen_client.py`: a function that POSTs to `http://localhost:11434/api/chat` with the model name `qwen2.5-coder:3b`, a system-style context message built from the currently-selected symbol's detail (name, kind, docstring, source snippet, relationships), and the user's message. Handle connection errors gracefully (Ollama not running) by returning a clear error string rather than raising.
2. Add `POST /api/qwen/chat` to `backend/api.py` per the Section 4.3 contract, calling `qwen_client.py`.
3. Wire the frontend chat panel: input box + send button, message history displayed as a simple scrolling list, "Connected"/"Disconnected" indicator based on whether the last call succeeded.

**Files created/modified:** `backend/qwen_client.py`, `backend/api.py`, `frontend/static/app.js`, `frontend/index.html`.

**Test Procedure:**
1. Select the `Animal` class, type "explain this" in the chat, send; confirm the reply text references "Animal" by name.
2. Stop the Ollama server, send another message; confirm the UI shows a clear "disconnected"/error state rather than hanging or crashing.
3. Restart Ollama, send again; confirm the UI recovers without restarting the whole app.

**Success Criteria:**
- [ ] Context-aware reply correctly references the selected symbol.
- [ ] Ollama-down scenario fails gracefully with a visible error state, no crash.
- [ ] Recovery after Ollama comes back works without an app restart.

**Guardrails:** Do not hardcode the Ollama prompt to bypass context injection — the selected symbol's real data (from `/api/symbol/{id}`) must be in the prompt, not a generic placeholder.

**Est. time:** 2.0h

---

### Phase 9 — Error Handling, Logging, Status Bar, Resilience

**Objective:** The whole app survives bad input gracefully and reports it clearly.

**Preconditions:** Phases 1–8 complete.

**Tasks:**
1. Surface the `errors` array from Graph JSON in the bottom log panel as warnings (file path + message), not crashes.
2. Handle "Analyze" on a non-existent or empty project path with a clear UI error message (no stack trace shown to the user).
3. Handle `/api/symbol/{id}` for an unknown `id` with a clean 404 and a frontend message, not a blank/broken panel.
4. Add basic startup validation: if Ollama is unreachable at app start, the Qwen panel shows "Disconnected" immediately rather than only after a failed send.

**Files modified:** `backend/api.py`, `backend/main.py`, `frontend/static/app.js`.

**Test Procedure:**
1. Re-run the broken-file test from Phase 1 end-to-end through the UI (not just the engine test) — analyze a directory containing one bad `.py` file; confirm the log panel lists it as a warning and the rest of the graph still renders.
2. Attempt to analyze a non-existent path; confirm a clean error message appears.
3. With Ollama stopped, start the whole app fresh; confirm the Qwen panel shows "Disconnected" without you having to send a message first.

**Success Criteria:**
- [ ] All three resilience tests pass with no crash and no stack trace shown in the UI.

**Guardrails:** None of this phase's error handling should silently swallow errors without surfacing them somewhere the user can see (log panel or inline message).

**Est. time:** 1.5h

---

### Phase 10 — Documentation & Final Acceptance

**Objective:** A non-technical person (one of your two reviewers) can run the app and understand what it's showing them, using only the quick-start doc.

**Preconditions:** Phases 0–9 complete and all individually tested.

**Tasks:**
1. Write `docs/quick_start.md`: how to start the app (`python run.py`), how to analyze a project, what each panel shows, in plain non-technical language.
2. Write `README.md`: a short technical overview for your own future reference (stack, folder structure, how to run tests).
3. Run the **full regression pass**: repeat every Success Criteria checklist item from Phases 0–9 in one sitting, against the sample project, end to end.
4. Hand the running app + `quick_start.md` to one of your reviewers; observe whether they can open it and inspect `sample_project` unassisted.

**Files created:** `docs/quick_start.md`, `README.md`.

**Test Procedure:**
1. Full regression pass (all prior phases' checklists, re-verified together).
2. Live walkthrough with one non-technical reviewer, quick-start doc only, no verbal help from you.

**Success Criteria:**
- [ ] Every checklist item from Phases 0–9 still passes in the final build.
- [ ] The reviewer reaches a rendered, explorable graph unassisted using only the quick-start doc.

**Guardrails:** Do not use this phase to add new features "while you're in there" — if something's missing, it goes on the Section 9 backlog, not into a last-minute Phase 10 addition.

**Est. time:** 1.5h

---

### Phase 11 — Multi-Project Support (Approved Addendum)

**STATUS: DONE, verified.** Approved addendum, not original MVP scope. Purpose: analyze arbitrary project paths, not only the fixed `sample_project` fixture.

**Objective:** The user can point CodeStruct at any valid Python project directory (or a single `.py` file), not only the hardcoded `sample_project` fixture, and the app analyzes and renders it correctly.

**Preconditions:** Phases 0–10 complete and verified.

**Tasks:**
1. Add a project-path input to the toolbar's existing "Open Project" control (specified but left unwired in Phase 3) so the user can type or select an arbitrary path.
2. `POST /api/analyze` accepts any valid `project_path`, not only `sample_project`; empty input defaults back to `sample_project`.
3. Handle three edge cases explicitly: a nonexistent path (clean 4xx, no stack trace), a directory with zero `.py` files (200 OK, empty graph, a visible warning, no crash), and a single `.py` file passed directly instead of a directory.
4. After analyzing a new project, `/api/symbol/{id}` and `/api/source` must serve that project's data without re-analyzing on every call (same in-memory last-analysis pattern as Phases 1–2, just no longer locked to one fixed path).
5. Add `GET /api/config` returning `{ "initial_project_path": Optional[str] }`, so a project path can optionally be passed in at startup (e.g., for launching directly against a specific demo project).

**Files modified:** `backend/api.py`, `backend/analyzer.py` (path resolution), `frontend/static/app.js`, `frontend/index.html`.

**Interface contract addition (extends Section 4.3):**
`GET /api/config` → `{ "initial_project_path": Optional[str] }`.
This is the only addition to the fixed API contract in Section 4.3 of this document — everything else (`/api/analyze`, `/api/symbol/{id}`, `/api/source`, `/api/qwen/chat`, `/api/qwen/status`) is unchanged.

**Test Procedure:**
1. Analyze a real multi-module project (not the fixture); confirm node/edge counts render and are internally consistent (e.g., `edge_count` matches the sum of edge types).
2. Enter a nonexistent path; confirm a clean 4xx with no stack trace shown in the UI.
3. Analyze a directory with no `.py` files; confirm a 200 response with an empty graph and a visible "no symbols found" warning, not a crash.
4. Leave the path input empty and click "Analyze"; confirm it defaults to `sample_project` and produces the familiar 16-node graph.
5. After analyzing a custom project, inspect a symbol and view its source without re-triggering analysis; confirm the data is from the new project, not stale `sample_project` data.

**Success Criteria:**
- [ ] A real custom project analyzes correctly with internally-consistent counts.
- [ ] Nonexistent path → clean 4xx, no stack trace.
- [ ] Empty `.py`-file directory → 200 with empty graph + visible warning, no crash.
- [ ] Empty input defaults to `sample_project` (16 nodes).
- [ ] Symbol/source lookups after a custom-project analysis reflect that project's data, not stale fixture data.

**Guardrails:** Do not silently drop the `sample_project` default behavior — it remains the Phase 0–10 baseline and must still work exactly as before. Do not add project history, bookmarks, or multi-project-at-once support — this phase is "analyze one arbitrary path at a time," nothing more.

**Est. time:** not pre-budgeted (built after the original 2-day window as an approved extension).

---

### Phase 12 — Quick Wins Bundle (Sprint 2)

**STATUS: NEXT UP.** Sprint 2, 10h total budget (Phase 12 + Phase 13 + 1h regression buffer). Selected because each item reuses data already computed — low risk to Phases 0–11.

**Objective:** Three independent, additive capabilities: opening a file in the system's default editor, a sortable/filterable table view of the analyzed project, and an instability score per symbol.

**Preconditions:** Phases 0–11 complete and verified.

**Tasks — 12a: Open in System Editor**
1. Add `POST /api/open_in_editor` accepting `{ "file_path": "string" }`. On the backend, resolve `file_path` relative to the last-analyzed `project_root` and launch it via the OS default handler (`os.startfile` on Windows, `["open", path]` via `subprocess.run` on macOS, `["xdg-open", path]` via `subprocess.run` on Linux). This is a fire-and-forget external launch — it must never block the request or open inside this app's own window.
2. Return `{ "launched": true }` on success; on a missing file, return a clean 404, never a stack trace.
3. Add an "Open in Editor" button to both the Inspector panel and the Code Viewer, wired to call this endpoint with the currently-selected symbol's `file_path`.

**Tasks — 12b: Accessible Table View**
4. Add a "Table View" toggle to the toolbar, next to the existing Graph/Code tabs. Selecting it renders the current Graph JSON's `nodes` array as an HTML `<table>`: columns `Name`, `Kind`, `Module`, `File`, `Start Line`, `End Line`. This is a pure frontend render from data already fetched by `/api/analyze` — no new backend endpoint needed.
5. Clicking a column header sorts the table by that column (toggle ascending/descending).
6. The existing Explorer filter input (Phase 5) also filters the table's visible rows by the same substring match on `name`.
7. Clicking a table row selects that symbol, same selection-sync behavior as the Explorer and graph (Phase 5/6).

**Tasks — 12c: Centrality / Instability Metric**
8. Add an `instability: float` field to the Symbol Detail response (Section 4.2), computed as `fan_out / (fan_in + fan_out)`, or `0.0` if `fan_in + fan_out == 0`. This is Martin's Instability metric — no new data collection required, it's derived entirely from the `fan_in`/`fan_out` values Phase 6 already computes.
9. Display the instability value in the Inspector panel (e.g., "Instability: 0.60") alongside the existing fan-in/fan-out display.

**Files modified:** `backend/api.py`, `backend/schemas.py` (add `instability` field, add `open_in_editor` request/response models), `frontend/static/app.js`, `frontend/index.html`, `frontend/static/app.css`.

**Interface contract additions (extends Section 4.2 and 4.3):**
- `SymbolDetail` gains `instability: float`.
- `POST /api/open_in_editor` → `{ "file_path": "string" }` → `{ "launched": true }` or a clean 404.

**Test Procedure:**
1. Call `/api/open_in_editor` with a mocked subprocess/`os.startfile` call (do not actually require an interactive editor window in automated tests); assert it was invoked with the correct resolved absolute path for the given `file_path`.
2. Call it with a nonexistent file; assert a clean 404, not a 500 or stack trace.
3. Open Table View against `sample_project`; assert exactly 16 rows render.
4. Click the "Kind" column header; assert rows re-order (e.g., all `class` rows grouped together).
5. Type a filter string; assert the table's visible rows narrow the same way the Explorer tree does.
6. Call `/api/symbol/sample_project.Dog`; assert `instability` equals `fan_out / (fan_in + fan_out)` computed independently from that same response's `fan_in`/`fan_out` fields. Repeat for `sample_project.Animal` and `sample_project.build_zoo` — three different symbols, each self-consistency-checked.

**Success Criteria:**
- [ ] Open-in-editor launches with the correct path (verified via mock), and fails cleanly (404, no crash) for a missing file.
- [ ] Table View renders all 16 sample-project rows, correctly, with working sort and the same filter behavior as the Explorer.
- [ ] Table row selection stays in sync with Graph/Explorer/Inspector selection (same bidirectional sync as Phase 5).
- [ ] `instability` is present and arithmetically correct for at least 3 distinct symbols.

**Guardrails:** Do not make the editor launch block the UI or open inside this app's window — it is a true fire-and-forget external process. Do not add any new backend computation for the table view — it must come from data already in the Graph JSON. Do not add any metric beyond instability in this phase (no new centrality algorithms) — that stays scoped exactly to Martin's Instability formula above.

**Est. time:** 4.0h (12a: 0.5h, 12b: 1.5h, 12c: 2.0h)

---

### Phase 13 — Design-Pattern Detection (Sprint 2)

**STATUS: NEXT, after Phase 12.** Part of the same 10h Sprint 2 budget.

**Objective:** Detect three structurally-recognizable design patterns — Singleton, Factory, Observer — in the analyzed project using precise AST-based heuristics, and surface them in the UI. This is heuristic pattern-matching on code structure, not guaranteed correct identification of design intent — document this limitation explicitly in the UI and in `README.md`.

**Preconditions:** Phase 1 (analysis engine) and Phase 11 (custom project paths) complete.

**Detection Heuristics — implement exactly as specified, do not invent alternative rules:**

1. **Singleton:** A class is flagged `Singleton` if ALL of the following hold:
   - It defines a `__new__` method.
   - That method's body contains an `if` statement whose test compares a class-level attribute (`cls.<name>` or `ClassName.<name>`) to `None`.
   - Inside that `if` block, there is an assignment to that same attribute.
   - The method returns that attribute (directly, or via the class attribute reference) at the end.
   - Evidence string to report: `"__new__ guards and returns a cached class-level instance"`.

2. **Factory:** A function or method is flagged `Factory` if ALL of the following hold:
   - Its body contains 2 or more `return <ClassName>(...)` statements (a `constructs` edge whose call is the direct subject of a `return`).
   - Those `ClassName`s are at least 2 distinct classes defined within the analyzed project.
   - Those return statements occur in different branches of the same `if`/`elif`/`else` chain (not sequential unconditional returns).
   - Evidence string to report: `"returns different constructed types across conditional branches"`.

3. **Observer/Subject:** A class is flagged `Observer` (specifically, as the *subject* in the pattern) if ALL of the following hold:
   - It has a method containing a `for <var> in self.<attr>:` loop (iterating a `self`-owned attribute).
   - Inside that loop's body, there is a method call on the loop variable (`<var>.<method>(...)`).
   - Evidence string to report: `"iterates a self-owned collection and invokes a method on each element"`.

**Tasks:**
1. Implement `detect_patterns(graph: dict, ast_trees: dict) -> list[dict]` in `backend/analyzer.py` (or a new `backend/patterns.py` — your call, but keep it a clearly separate function from `analyze_project`), applying the three heuristics above against the already-parsed AST. Each match produces `{ "pattern": "Singleton" | "Factory" | "Observer", "symbol_id": "string", "evidence": "string" }` using the exact evidence strings specified above.
2. Add `GET /api/patterns` returning `{ "patterns": [...] }` for the currently-analyzed project (same in-memory last-analysis pattern as other endpoints — no re-analysis).
3. Create three new fixture files for testing (do **not** modify `sample_project/sample_project.py` — it must stay exactly as specified in Section 7):
   - `tests/pattern_fixtures/singleton_example.py`
   - `tests/pattern_fixtures/factory_example.py`
   - `tests/pattern_fixtures/observer_example.py`
   Each file should contain a minimal, clean example of its pattern per the heuristic rules above (e.g., the `Singleton`/`ShapeFactory`+`Circle`+`Square`/`Subject`+`ConcreteObserver` examples are acceptable reference shapes — write clean, minimal versions of each).
4. Add a "Patterns" tab in the center area (alongside Graph/Code/Table) listing detected patterns as a simple list: pattern name, symbol name, evidence string. Clicking an entry selects that symbol (same selection-sync as other views).

**Files created/modified:** `backend/analyzer.py` or `backend/patterns.py`, `backend/api.py`, `backend/schemas.py` (add `PatternMatch` model), `tests/pattern_fixtures/*.py`, `tests/test_patterns.py`, `frontend/static/app.js`, `frontend/index.html`.

**Interface contract addition (extends Section 4.3):**
`GET /api/patterns` → `{ "patterns": [ { "pattern": "string", "symbol_id": "string", "evidence": "string" } ] }`.

**Test Procedure:**
1. Unit-test `detect_patterns` directly against each of the three fixture files individually; assert each fixture produces exactly one match of its intended pattern type, with the exact evidence string specified above.
2. Analyze `tests/pattern_fixtures/` as a project path (using Phase 11's custom-path support) via `/api/analyze`, then call `/api/patterns`; assert all three patterns are present in the result.
3. Analyze `sample_project` (the regression fixture) and call `/api/patterns`; assert the result is `{ "patterns": [] }` — the sample project intentionally contains none of these patterns, which is a useful negative-control test.
4. In the UI, open the Patterns tab against the pattern fixtures project; confirm three entries appear and each is clickable and syncs selection correctly.

**Success Criteria:**
- [ ] Each of the three fixtures is detected individually with the correct, exact evidence string.
- [ ] Analyzing the fixtures directory via the API returns all three patterns.
- [ ] Analyzing `sample_project` returns zero patterns (negative control passes — confirms no false positives on the regression fixture).
- [ ] Patterns tab in the UI lists and correctly syncs selection for all three.

**Guardrails:** Implement exactly the three heuristics specified above — do not add other patterns (e.g., Strategy, Decorator) in this phase, and do not loosen the heuristics to catch "near-matches," since that increases false positives on unrelated code (including `sample_project`, which must still return zero matches). Do not claim certainty in the UI — label this feature as heuristic-based pattern matching, not verified design intent.

**Est. time:** 5.0h (detection logic ~3.0h, API + fixtures + tests ~1.0h, UI tab ~1.0h)

---

### Phase 14 — Persistent/Incremental Caching

**STATUS: NEXT** (part of Sprint 3, alongside the Sprint 2 corrections, Phase 15, and Phase 17).

**Objective:** Avoid re-parsing unchanged files on every "Analyze" click, without ever risking stale cross-file relationships.

**Design:** Split analysis into two stages:
- **Stage A (per-file, cacheable):** parse each `.py` file, extract that file's own nodes and `defines` edges, plus unresolved candidate `inherits`/`constructs`/`calls` targets as plain names (not yet resolved against other files).
- **Stage B (global, always runs fresh, never cached):** merge all files' Stage A output into one project-wide symbol table, then resolve the candidate targets into final `inherits`/`constructs`/`calls` edges. This must run in full on every `/api/analyze` call — it's cheap (no disk I/O, no re-parsing) but a change in any one file can affect how other files' calls resolve, so cross-file edges are never themselves cached.

**Tasks:**
1. Refactor `analyzer.py`'s per-file parsing into a Stage A function returning `{nodes, defines_edges, candidate_edges}` per file.
2. Create `backend/cache.py`: read/write a single JSON cache file per project at `.codestruct_cache/<sha256 of absolute project_root>.json`, storing `{file_relpath: {mtime, size, stage_a_output}}`.
3. On `analyze_project`: for each file, compare current `(mtime, size)` to the cache entry; reuse cached Stage A output on a match (cache hit), otherwise re-parse and update the cache entry (cache miss). Drop cache entries for files no longer present in the project.
4. Always run Stage B fresh from the (cached-or-fresh) per-file data to produce final edges.
5. Add `force_refresh: bool = False` to the `POST /api/analyze` request body — when true, bypass the cache entirely for every file.
6. Add `cache_hits: int` and `cache_misses: int` to the Graph JSON `summary` object; surface them in the Status & Logs panel (e.g., "12 cached, 2 re-parsed").

**Files created/modified:** `backend/analyzer.py`, `backend/cache.py` (new), `backend/api.py`, `backend/schemas.py` (add `cache_hits`/`cache_misses` to `GraphSummary`), `tests/test_cache.py` (new), `tests/cache_fixtures/` (new — a small 2-file fixture for multi-file cache invalidation testing; do not reuse or modify `sample_project.py`).

**Interface contract addition (extends Section 4.1):** `GraphSummary` gains `cache_hits: int`, `cache_misses: int`.

**Test Procedure:**
1. Analyze `sample_project` twice consecutively with nothing changed; assert the second run reports `cache_hits: 1, cache_misses: 0` and produces identical node/edge counts to the first run.
2. Using `tests/cache_fixtures/` (2 files), modify one file's content between two analyze calls; assert the next analysis reports exactly 1 cache hit and 1 cache miss, and that the merged graph is still correct (cross-file edges still resolve).
3. Delete a file from a temp copy of a fixture between two analyze calls; assert its nodes disappear from the next analysis and its cache entry is dropped.
4. Call `/api/analyze` with `force_refresh: true` on an unchanged project; assert `cache_hits: 0`.
5. Re-run the Section 7 deterministic oracle against `sample_project` with caching enabled; assert unchanged counts (16 nodes, 2 inherits, 15 defines, 3 constructs).

**Success Criteria:**
- [ ] Second consecutive analyze of an unchanged project: full cache hit, identical results to the first run.
- [ ] Modifying one file in a multi-file fixture causes exactly that file to miss cache; others hit; merged graph stays correct.
- [ ] Deleting a file removes its data from the next analysis and its cache entry.
- [ ] `force_refresh: true` bypasses the cache entirely.
- [ ] `sample_project`'s deterministic counts are unchanged with caching enabled.

**Guardrails:** Never cache resolved cross-file edges (`inherits`/`constructs`/`calls`) themselves — only per-file Stage A output. Stage B always runs in full on every call. Use JSON for the cache file, never `pickle`. No UI toggle needed beyond the `force_refresh` escape hatch — caching is otherwise transparent.

**Est. time:** 3.5h

---

### Phase 15 — Change-Impact Analysis

**STATUS: NEXT** (part of Sprint 3, alongside the Sprint 2 corrections, Phase 14, and Phase 17).

**Objective:** Given a selected symbol, show what else in the project depends on it — a "blast radius" view, computed as a transitive backward walk over the existing graph's edges. No new analysis engine is needed; this reuses the Graph JSON already produced by Phase 1/14.

**Design:** "Impact" means: everything reachable by following `calls`, `constructs`, and `inherits` edges **backward** (i.e., from a selected node, find all nodes with an edge pointing *at* it, then all nodes pointing at those, and so on), breadth-first, with a visited-set to handle cycles and a `max_depth` cap (default 5) to bound the walk on large projects. Each impacted node is reported once, at the shallowest depth it was reached. `defines` edges are **excluded** from the walk — they represent structural containment, not a change-impact relationship, and including them would flood every result with the entire ancestor-container chain.

**Tasks:**
1. Implement `compute_impact(graph: dict, node_id: str, max_depth: int) -> list[dict]` (in `backend/analyzer.py` or a new `backend/impact.py`) doing the BFS described above over `calls`/`constructs`/`inherits` edges only, returning `[{id, name, depth, via_edge_type}]` sorted by depth ascending.
2. Add `GET /api/impact/{node_id}?max_depth=5` returning `{ "symbol_id": "string", "max_depth": int, "impacted": [...] }`, operating on the currently-analyzed project's in-memory graph.
3. Add an "Impact" section to the Inspector panel: a button or expandable section that calls this endpoint for the currently-selected symbol and lists results grouped by depth, each entry clickable with the same selection-sync behavior as other views.

**Files created/modified:** `backend/analyzer.py` or `backend/impact.py` (new), `backend/api.py`, `backend/schemas.py` (add `ImpactedSymbol`, `ImpactResponse`), `tests/test_impact.py` (new), `frontend/static/app.js`, `frontend/index.html`.

**Interface contract addition (extends Section 4.3):** `GET /api/impact/{node_id}?max_depth=5` → `{ "symbol_id": "string", "max_depth": int, "impacted": [ { "id": "string", "name": "string", "depth": int, "via_edge_type": "calls" | "constructs" | "inherits" } ] }`.

**Deterministic Test Oracle (reuses `sample_project`, no new fixture needed):**
- Impact of `sample_project.Animal`, `max_depth=5`: depth 1 = `Dog`, `Cat` (via `inherits`); depth 2 = `build_zoo` (via `constructs`, since `build_zoo` constructs both `Dog` and `Cat`, first reached here); depth 3 = `main` (via `calls`, since `main` calls `build_zoo`).
- Impact of `sample_project.Zoo`, `max_depth=5`: depth 1 = `build_zoo` (via `constructs`); depth 2 = `main` (via `calls`).
- Impact of `sample_project.Animal`, `max_depth=1`: depth 1 only = `Dog`, `Cat` — `build_zoo` and `main` excluded.
- Impact of `sample_project.main`: empty list — nothing calls, constructs, or inherits from `main`.

**Test Procedure:**
1. Run all four Deterministic Test Oracle cases above as automated tests; assert exact match on node sets, depths, and `via_edge_type` for each.
2. In the UI, select `Animal`, open its Impact section; confirm it lists `Dog`, `Cat`, `build_zoo`, `main` grouped correctly by depth, each clickable with selection sync.

**Success Criteria:**
- [ ] All four Deterministic Test Oracle cases pass exactly.
- [ ] `max_depth` correctly truncates results.
- [ ] A symbol with no dependents returns an empty `impacted` list, not an error.
- [ ] UI Impact section lists and syncs selection correctly.

**Guardrails:** Do not include `defines` edges in the impact walk. Always cap by `max_depth` and guard cycles with a visited-set. Do not attempt to resolve the polymorphic-call ambiguity noted in Phase 1/Section 8 — if a call wasn't resolved into an edge by the analysis engine, it simply won't appear in the impact walk; this is an inherited, already-documented limitation, not a new problem to solve in this phase.

**Est. time:** 4.0h (BFS logic + endpoint + tests ~2.0h, UI ~1.5h, docs ~0.5h)

---

### Phase 17 — UI/UX Overhaul: Collapsible Docks, Scrollable Toolbar, Design System

**STATUS: NEXT.** Frontend-only — touches no backend logic, API contracts, or data shapes. Prioritized ahead of Phases 14–16 (which are deferred feature work) because this addresses current demo-readiness. Numbered 17, not 14, to avoid renumbering the already-documented backlog phases.

**Preconditions:** Phase 13 complete. The two open corrections from the Sprint 2 review (the fabricated `run_simulation` edge description in the regression report, and the duplicated project folder tree) should be resolved before or alongside this phase — they're unrelated to this phase's scope but should not be left outstanding indefinitely.

**Objective:** Four specific problems, visible in the current running app: (1) the Explorer, Inspector, Qwen Assistant, and Status/Logs docks cannot be collapsed, so the center workspace is permanently cramped; (2) the toolbar's view-tabs and file-context controls overflow with no way to reach hidden items; (3) there is no deliberate visual design system — colors, type, and spacing are ad hoc rather than token-driven; (4) the overall look reads as generic dev-tool chrome rather than something purpose-built for this product.

**Design Direction (apply before writing any CSS):**

This is a static-analysis/architecture-visualization tool — the subject matter is code structure shown as a diagram, so the visual language should read like a precise technical blueprint, not a generic SaaS dashboard or an unmodified IDE theme clone.

- **Color tokens** (define as CSS custom properties on `:root`, replace every hardcoded hex in `app.css` with these):
  - `--bg-canvas: #0B1220` (deep blueprint-ink background, the graph/code canvas)
  - `--bg-panel: #121A2B` (dock surfaces — Explorer, Inspector, Qwen, toolbar)
  - `--bg-elevated: #1A2439` (inputs, hover states, active tab)
  - `--accent: #4FD1C5` (blueprint cyan — used only for active/selected/live states: selected graph node, active tab, focus ring. Never used as decoration.)
  - `--accent-warm: #F2B855` (used sparingly: pattern-detection badges, the heuristic-disclaimer banner, warnings)
  - `--text-primary: #E8EDF5`
  - `--text-muted: #7C8AA3`
  - `--border: #22304A` (1px hairline dividers between panels — not drop shadows, not rounded card borders)
- **Typography:** two typefaces with clearly distinct roles, vendored locally as `.woff2` files under `frontend/static/vendor/fonts/` (do not depend on a live Google Fonts connection — same offline-first principle as vendoring Cytoscape in Phase 4):
  - UI chrome (labels, buttons, panel headers, Inspector fields, toolbar): **Inter**.
  - Code and monospaced data (Code Viewer, symbol IDs, line numbers, the Table View's `File` column): **JetBrains Mono**.
- **Spacing/radius:** a 4px-based spacing scale (`--space-1: 4px` through `--space-6: 24px`); two radius tokens — `--radius-sm: 4px` for interactive elements (buttons, inputs, pills), `--radius-none: 0` for structural panel edges. Do not apply one uniform rounded-card-with-shadow treatment to every panel — that reads as generic SaaS-kit styling. Panels are separated by hairline `--border` dividers, not boxes.
- **Existing kind/relationship badges** (`CLS`/`MET`/`FN`/`MOD` in the Explorer, `INHERITS`/`DEFINES`/`CALLS`/`CONSTRUCTS` in the Inspector, pattern-type tags in the Patterns tab) are a legitimate, information-dense technical convention — keep them, but unify them into one shared CSS class so height, radius, and type scale are consistent across all three locations instead of three separate one-off styles.

**Tasks:**

*17a — Design Token System*
1. Add the token block above to `:root` in `app.css`; replace every hardcoded color currently in the stylesheet with the matching variable.
2. Vendor Inter and JetBrains Mono as local `.woff2` files; apply Inter to UI chrome and JetBrains Mono to all code/monospace contexts.
3. Unify the kind/relationship/pattern badges into one shared `.badge` class per the note above.

*17b — Collapsible Docks*
4. Add a collapse/expand toggle (chevron icon) to each of the four dock headers: Explorer (left), Inspector (right-top), Qwen Assistant (right-bottom), Status & Logs (bottom).
5. Collapsing a dock reduces it to a thin rail, never to zero width/height — left/right docks collapse to a 40px icon rail with a vertical label; the bottom dock collapses to a 32px strip showing only its latest log line. The user must always be able to see the panel exists and re-expand it with one click.
6. Collapse state is held in frontend JS runtime state only (a plain in-memory object) — it resets to all-expanded on app restart. No new persistence mechanism.
7. Collapsing/expanding a dock must never clear its contents — the Qwen chat history, the current Inspector selection, and the Explorer's current filter text all survive a collapse/expand cycle.
8. The center workspace (Graph/Table/Patterns/Code Viewer) must re-flow correctly and remain usable in every combination of collapsed/expanded docks, including all four collapsed at once.

*17c — Scrollable Toolbar*
9. Wrap the toolbar's view-tab group (Graph View / Table View / Patterns / Code Viewer / file-context selector / line-range indicator / Open in Editor / READ-ONLY badge) in a horizontally-scrollable container (`overflow-x: auto`, no wrap). Support mouse-wheel, trackpad, and click-drag horizontal scroll.
10. Style the scrollbar for this container to match the token system (thin, `--border`-colored) rather than the browser default, and add a soft edge-fade gradient on whichever side(s) have more content to scroll to — hide the fade on a side once fully scrolled to that edge.
11. The app name/logo, project-path input, "Analyze" button, and "Open Project" button stay fixed outside the scrollable region, pinned left and right respectively, always visible regardless of scroll position.

*17d — Supporting Non-Functional Requirements*
12. Every interactive element (buttons, tabs, table headers, tree items, dock toggles) gets a visible keyboard focus state: a 2px outline in `--accent`.
13. Icon-only buttons (dock toggles, any iconified actions) have a minimum interactive target size of 32×32px.
14. Responsive floor: below 1024px window width, all four docks default to their collapsed rail state on load (the user can still manually expand any of them); at or above 1024px, they default to expanded.

**Files modified:** `frontend/static/app.css`, `frontend/static/app.js`, `frontend/index.html`, new `frontend/static/vendor/fonts/*.woff2`.

**Test Procedure:**
1. Click each of the four dock toggles individually; confirm each collapses to its rail/strip state and expands back, and confirm the center workspace re-flows to use the freed space each time.
2. Collapse the Qwen panel mid-conversation and the Explorer with an active filter; expand both back; confirm chat history and filter text were preserved.
3. Resize the window to below 1024px width; confirm all four docks load/default to the collapsed state. Resize back above 1024px on a fresh load; confirm they default to expanded.
4. Shrink the window so the toolbar's view-tab group overflows; confirm horizontal scroll works via mouse wheel and via click-drag, and confirm the edge-fade gradient appears and disappears correctly at each scroll boundary.
5. Tab through every interactive element via keyboard only (no mouse); confirm each shows a visible focus outline.
6. Take screenshots of the default state and of at least two different collapsed-dock combinations at both 1280×800 and 1024×768; visually confirm no overlapping, clipped, or misaligned content.
7. Re-run the full Phase 0–13 regression suite (`pytest -v`); confirm all tests still pass unchanged — this phase must not touch backend logic.

**Success Criteria:**
- [ ] All four docks collapse to a visible rail/strip state and expand back on click, without losing current selection, filter text, or chat history.
- [ ] Toolbar view-tab group scrolls horizontally when it overflows, with working edge-fade indicators; the app name, project-path input, Analyze, and Open Project controls remain pinned and visible at all scroll positions.
- [ ] Below 1024px width, docks default to collapsed; at/above it, they default to expanded.
- [ ] Every interactive element has a visible keyboard focus state, and icon-only buttons meet the 32×32px minimum target size.
- [ ] The color/type/spacing/radius token system is applied consistently — no hardcoded hex colors remain in `app.css` outside the `:root` token block, and both vendored fonts load without an internet connection.
- [ ] Full Phase 0–13 regression suite passes unchanged.

**Guardrails:** This is a frontend-only visual/layout phase — do not change any backend logic, API contracts, data shapes, or test fixtures. Never fully hide a collapsed dock (always leave the rail/strip visible). Do not apply a uniform rounded-card-with-drop-shadow treatment to every panel — keep hairline dividers per the design direction above. Do not depend on a live internet connection for fonts — vendor them locally. Do not strip the existing kind/relationship badges in the name of "cleaning up" — unify their styling, don't remove the convention.

**Est. time:** 4.5h (token system + font vendoring ~1.0h, collapsible docks ~1.5h, scrollable toolbar ~1.0h, keyboard focus/responsive floor/badge unification ~1.0h)

---

### Phase 17 Follow-Up — Toolbar Deduplication

**STATUS: NEXT.** Found via screenshot review after Phase 17 was otherwise verified complete — automated/CDP checks confirmed each toolbar row worked individually and missed that two rows now duplicate the same controls.

**Objective:** The app currently renders two toolbar rows. The top row is Phase 17's new pinned/scrollable toolbar (compact tab labels: Graph / Table / Patterns / Code, plus the file-context cluster — filename, line range, "Open in Editor," the READ-ONLY badge — plus the project-path input, Analyze, Open Project). The second row, directly below it, is the original Phase 3/4 toolbar, which still independently renders the same view-switcher tabs (full labels: "Graph View" / "Table View" / "Patterns" / "Code Viewer") *and* the same file-context cluster a second time. Collapse this down to one source of truth per control.

**Tasks:**
1. Remove the view-switcher tab buttons (Graph View / Table View / Patterns / Code Viewer) from the second row entirely — the top row's compact tab group is now the only view switcher.
2. Remove the file-context cluster (filename/module label, line range, "Open in Editor," READ-ONLY badge) from the second row as well — it's duplicated for the same reason the tabs were, and should live only in the top row's pinned file-context cluster.
3. Keep the second row's view-specific sub-controls exactly as they are: the Module/Class/Function/Method filter checkboxes and the `+`/`-`/Fit/Layout controls when Graph View is active.
4. The second row should render only when the active view actually has sub-controls to show. Currently that's Graph View only — for Table View, Patterns, and Code Viewer, the second row should collapse to zero height rather than rendering empty, since there's nothing view-specific to put there yet.
5. Re-verify the Phase 17 collapsible-dock and scrollable-toolbar behavior still works correctly with the second row's height now changing dynamically based on the active view (the center workspace must still re-flow correctly when the second row appears/disappears).

**Files modified:** `frontend/index.html`, `frontend/static/app.js`, `frontend/static/app.css`.

**Test Procedure:**
1. Switch to each of the four views (Graph, Table, Patterns, Code) in turn; confirm the view-switcher tabs and the file-context cluster appear exactly once, in the top row, in every case.
2. Confirm the Module/Class/Function/Method filters and `+`/`-`/Fit/Layout controls still appear and still function when Graph View is active.
3. Confirm the second row is absent (zero height, not just empty) when Table View, Patterns, or Code Viewer is active.
4. Take a screenshot of each of the four views; visually confirm no duplicate controls anywhere.
5. Re-run the full regression suite; confirm all previously-passing tests still pass.

**Success Criteria:**
- [ ] Every control (view tabs, file-context cluster) appears exactly once, regardless of which view is active.
- [ ] Graph View's filter/zoom sub-controls are preserved and functional.
- [ ] The second row disappears entirely (not just visually empty) for views with no sub-controls.
- [ ] Screenshots of all four views confirm no duplication.
- [ ] Full regression suite still passes.

**Guardrails:** Do not remove or alter the Module/Class/Function/Method filters or the `+`/`-`/Fit/Layout controls — those are staying, only the duplicated tabs and file-context cluster are being removed from the second row. Do not touch backend logic.

**Est. time:** 1.0h

**STATUS UPDATE: DONE, verified.** Old second-row tabs and duplicate file-context cluster removed; `#center-sub-toolbar` correctly collapses to `height: 0` for non-Graph views; confirmed visually in a follow-up screenshot.

---

### Phase 17 Follow-Up 2 — Missing Re-Expand Control on Inspector/Qwen Docks

**STATUS: COMPLETE, verified.** Inspector and Qwen Assistant docks collapse to persistent 40px vertical rails matching Explorer's pattern, re-expand correctly upon clicking either the rail or the header chevron, preserve selection and chat draft state, and show consistent 4-dock collapsed rail treatment.

**Objective:** Collapsing Inspector or Qwen Assistant must leave the same kind of persistent, clickable rail that Explorer and Status/Logs already have — never a full disappearance.

**Tasks:**
1. Find wherever the Explorer/Status collapse-to-rail logic lives (the 40px icon rail with vertical label, per the original Phase 17 spec) and apply the identical pattern to the Inspector and Qwen Assistant docks — they are right-side docks, so the rail sits on their edge the same way Explorer's does on the left.
2. Confirm the rail is clickable and re-expands the dock, restoring its prior width and contents.
3. Re-confirm state preservation still holds through this collapse/expand cycle for both docks (Inspector's current selection, Qwen's chat history and draft input) — this was already verified for Explorer/Qwen's content persistence in the original Phase 17 work; just confirm it still holds now that the rail itself is fixed.

**Files modified:** `frontend/static/app.js`, `frontend/static/app.css`, `frontend/index.html` if the rail markup needs duplicating for these two docks.

**Test Procedure:**
1. Collapse the Inspector dock; confirm a visible rail with a re-expand control remains, matching Explorer's/Status's visual pattern.
2. Click it; confirm Inspector expands back with its prior content intact.
3. Repeat both steps for the Qwen Assistant dock, including with an active chat history and a partially-typed draft message in the input box.
4. Screenshot all four docks in their collapsed state side by side, confirming all four show the same rail treatment.

**Success Criteria:**
- [x] Inspector shows a persistent, clickable rail when collapsed, and re-expands correctly.
- [x] Qwen Assistant shows a persistent, clickable rail when collapsed, and re-expands correctly, with chat history and draft input preserved.
- [x] All four docks (Explorer, Inspector, Qwen, Status/Logs) now show visually consistent rail treatment when collapsed.

**Guardrails:** Do not change Explorer's or Status/Logs's already-working collapse behavior — copy their pattern, don't rewrite it. Do not touch backend logic.

**Est. time:** 0.5h

---

## 6. Timeline

| Day | Phases |
|---|---|
| Day 1 | Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 |
| Day 2 | Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9 → Phase 10 |
| Post-MVP (approved addendum) | Phase 11, after Phase 10's Definition of Done was already met |
| Sprint 2 (10-hour budget, for a staff demo) | Phase 12 (4.0h) → Phase 13 (5.0h) → 1.0h regression/demo rehearsal buffer |
| Sprint 3 (open-ended) | 2 open Sprint 2 corrections (see Status at a Glance) → Phase 14 (3.5h) → Phase 15 (4.0h) → Phase 17 (4.5h) |

With one builder, phases are sequential — there is no slack. If behind schedule at the Day 1/Day 2 boundary, do not skip testing steps; instead drop stretch items first (see Section 9) before cutting any phase's core Success Criteria.

## 7. Deterministic Test Oracle — Sample Project

Create `sample_project/sample_project.py` **verbatim** as below. All phase tests reference this exact file, so its structure must not be altered.

```python
"""Sample project for CodeStruct analysis testing."""


class Animal:
    """Base class for all zoo animals."""

    def __init__(self, name, age):
        self.name = name
        self.age = age

    def speak(self):
        return "..."

    def describe(self):
        return f"{self.name} is {self.age} years old"


class Dog(Animal):
    """A dog."""

    def fetch(self, item):
        return f"{self.name} fetches the {item}"

    def speak(self):
        return "Woof!"


class Cat(Animal):
    """A cat."""

    def climb_tree(self):
        return f"{self.name} climbs a tree"

    def speak(self):
        return "Meow!"


class Zoo:
    """Holds a collection of animals."""

    def __init__(self):
        self.animals = []

    def add_animal(self, animal):
        self.animals.append(animal)


def build_zoo():
    """Construct a sample zoo."""
    zoo = Zoo()
    zoo.add_animal(Dog("Rex", 3))
    zoo.add_animal(Cat("Whiskers", 2))
    return zoo


def main():
    """Entry point."""
    zoo = build_zoo()
    for animal in zoo.animals:
        print(f"{animal.name} says {animal.speak()}")


if __name__ == "__main__":
    main()
```

**Expected, deterministic counts (hard pass/fail — use these in `test_analyzer.py`):**
- `node_count` = **16** (1 module + 4 classes [`Animal`, `Dog`, `Cat`, `Zoo`] + 2 top-level functions [`build_zoo`, `main`] + 9 methods [`Animal`: `__init__`, `speak`, `describe`; `Dog`: `fetch`, `speak`; `Cat`: `climb_tree`, `speak`; `Zoo`: `__init__`, `add_animal`]).
- `inherits` edges = **2** (`Dog`→`Animal`, `Cat`→`Animal`).
- `defines` edges = **15** (module defines 4 classes + 2 functions = 6; `Animal` defines 3 methods, `Dog` defines 2, `Cat` defines 2, `Zoo` defines 2 = 9; total 15).
- `constructs` edges = **3** (`build_zoo`→`Zoo`, `build_zoo`→`Dog`, `build_zoo`→`Cat`).
- `calls` edges — **do not assert an exact total**. Known ambiguity: `animal.speak()` inside `main` is a polymorphic call (the loop variable could be a `Dog` or `Cat` at runtime) and is **not required** to resolve to a specific subclass method — it is acceptable to leave it unresolved or to conservatively attribute it to `Animal.speak`. Only assert that these two specific `calls` edges exist: `main`→`build_zoo`, and `build_zoo`→`Zoo.add_animal` (resolvable via simple same-function local-variable type inference: `zoo = Zoo()` followed by `zoo.add_animal(...)`).
- `errors` = **empty list** (this file is syntactically valid).

## 8. Known Limitations (by design, not bugs)

- Polymorphic call resolution is intentionally limited — see Section 7.
- Only within-project base classes are resolved for `inherits`; external/library base classes are skipped, not erroring.
- No caching between runs — every "Analyze" click re-parses the whole project from scratch. Acceptable for the project sizes the MVP targets; addressed by Phase 14 once that phase is complete.
- Single project analyzed at a time; no multi-project workspace support.

## 9. Backlog (explicitly deferred, not forgotten)

Three items originally listed here — "Open in system editor," "Accessible table view," and "Instability/centrality metrics" — moved into Phase 12 (Sprint 2). Design-pattern detection moved into Phase 13 (Sprint 2). Persistent caching and change-impact analysis are now fully specced as Phase 14 and Phase 15 (Sprint 3) — see Section 5. What remains genuinely deferred, with no detailed spec yet:

| Item | Why still deferred | Future phase |
|---|---|---|
| Dynamic/runtime execution analysis | Needs a process-isolation/sandboxing design decided *before* any implementation estimate is honest — deliberately gated, not rushed into any sprint | Phase 16 (gated on a security design pass first — do not implement without one) |
| Packaging/installer, desktop shortcuts | Not needed while running from source for a local demo | Unscheduled |

## 10. Definition of Done

The project is complete when:
- [ ] All Phase 0–10 Success Criteria checklists are checked off.
- [ ] `pytest` (full suite: `test_analyzer.py` + `test_api.py`) passes with zero failures.
- [ ] The full regression pass from Phase 10 has been run once, start to finish, with no manual workarounds needed.
- [ ] One non-technical reviewer has successfully used the app via the quick-start doc alone.
- [ ] Section 9's backlog items are documented as *not done* (not silently dropped) for a future build session.

The MVP (Phases 0–10) is considered done independently of Phase 11. Phase 11 is an approved addendum with its own Success Criteria (Section 5) and is tracked as done or not done on its own terms, not folded into the MVP checklist above.

**Sprint 2 Definition of Done** (Phases 12–13, tracked separately from the MVP and from Phase 11):
- [x] All Phase 12 and Phase 13 Success Criteria checklists are checked off, with real evidence per the verification standard used throughout this document (actual command output, not a bare claim of success).
- [x] The full MVP + Phase 11 regression suite still passes — Sprint 2 additions must not break anything already verified.
- [x] `sample_project` still analyzes to exactly 16 nodes and zero detected patterns (the negative-control check from Phase 13).
- [x] Phases 14, 15, and 16 remain explicitly undone and documented as such (Section 9) — not silently implemented under time pressure, and not silently dropped either.
- [ ] **Outstanding correction:** the regression report's edge description must be corrected (see Status at a Glance) before Sprint 2 is closed out as fully clean, even though the automated test evidence itself is sound.
- [ ] **Outstanding correction:** the duplicated folder tree must be consolidated to one canonical layout.

**Sprint 3 Definition of Done** (the 2 Sprint 2 corrections + Phases 14, 15, 17 — tracked separately from Sprint 2 and the MVP; Phase 16 is explicitly excluded from this sprint):
- [ ] Both outstanding Sprint 2 corrections are resolved (edge-description fix, folder-structure consolidation), each with evidence, not just a claim.
- [ ] Phase 14's Success Criteria are checked off with evidence (cache-hit/miss behavior, invalidation, `force_refresh`, unchanged deterministic counts).
- [ ] Phase 15's Success Criteria are checked off with evidence (all four Deterministic Test Oracle cases pass exactly).
- [ ] Phase 17's Success Criteria are checked off with evidence (screenshots at both tested window sizes, keyboard-navigation confirmation, scroll-behavior confirmation).
- [ ] The full Phase 0–13 regression suite still passes unchanged after all of the above.
- [ ] Phase 16 remains explicitly untouched and documented as such — not implemented under scope pressure, not silently dropped from the backlog either.

## 11. Multi-Agent Pipeline Notes (for Brain)

- Read this document's relevant phase section only — do not re-plan the architecture; it is fixed in Sections 3–4.
- When writing `prompt.md` for a phase, include that phase's Tasks, Files, Test Procedure, Success Criteria, and Guardrails verbatim or near-verbatim — do not summarize away the specifics (exact field names, exact counts, exact file paths).
- When reviewing `report.md` from Implementer/Antigravity, check it against that phase's Success Criteria checklist item-by-item before approving progression to the next phase.
- If the report claims success but the Test Procedure in this document wasn't actually run, treat the phase as **not done** and request it be run before moving on.
- Do not build anything from Section 9 (Backlog) or any phase beyond what's marked "NEXT" in the Status-at-a-Glance table without the human explicitly authorizing it first — see `Brain_Orchestrator_Prompt.md` Section 5 for the full stop-and-ask rule.
