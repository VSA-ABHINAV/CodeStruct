CodeStruct

A single-window desktop tool that statically analyzes a Python project's structure — modules, classes, functions, methods, and the relationships between them — and renders it as an interactive, explorable architecture graph. Includes a project explorer, a symbol inspector, a read-only code viewer, design-pattern detection, change-impact analysis, and a local AI assistant that can explain selected code using the same analysis data as context.

Everything runs locally. No code from the analyzed project is ever executed — analysis is purely static, via Python's built-in ast module.

Features

Core analysis

Static AST-based analysis of modules, classes, functions, and methods, with inherits, defines, constructs, and calls relationships.
Analyze any project path, not just a fixed sample — including a single .py file.
Incremental caching: unchanged files are skipped on re-analysis; only modified files are re-parsed, with correctness preserved across file changes and deletions.

Visualization & navigation

Interactive graph view (pan, zoom, fit, filter by kind) built on Cytoscape.js.
Sortable, filterable table view of every symbol in the project.
Project Explorer with a filterable file/symbol tree, synced bidirectionally with every other view.
Read-only, syntax-highlighted code viewer with jump-to-source.
"Open in system editor" for actually editing a file outside the app.
Symbol Inspector: fan-in/fan-out, Martin's Instability metric, docstrings, and incoming/outgoing relationships.

Architecture intelligence

Design-pattern detection (Singleton, Factory, Observer) via structural heuristics — flagged as heuristic pattern-matching, not verified design intent.
Change-impact analysis: select a symbol and see everything that transitively depends on it, grouped by depth.

AI assistant

Local chat assistant (Qwen 2.5-coder, via Ollama) with the currently-selected symbol automatically injected as context.

Interface

Single native window, one process — no embedded subprocess UI.
Collapsible docks (Explorer, Inspector, AI Assistant, Status/Logs), each collapsing to a persistent, re-expandable rail rather than disappearing.
Scrollable toolbar with pinned core controls.
Works fully offline — all fonts and libraries are vendored locally, nothing is loaded from a CDN at runtime.
Prerequisites
Python 3.10+
Ollama, running locally, with the qwen2.5-coder:3b model pulled:
  ollama pull qwen2.5-coder:3b
Setup
bash
git clone <repository-url>
cd codestruct
pip install -r requirements.txt
Running
bash
python run.py

This starts a local FastAPI server and opens CodeStruct in a native window. Click Open Project to analyze a project of your choice, or Analyze to run against whatever project path is currently loaded (defaults to the bundled sample_project).

Running the tests
bash
pytest -v

The suite covers the analysis engine, the API layer, pattern detection, caching/invalidation, and change-impact analysis, using a fixed sample project (sample_project/sample_project.py) as a deterministic test fixture — do not modify that file, several tests assert exact node and edge counts against it.

Project structure
codestruct/
  backend/
    main.py           # FastAPI app + pywebview launcher
    analyzer.py        # AST analysis engine, caching, impact analysis
    cache.py             # Incremental analysis cache
    schemas.py             # Pydantic data models
    api.py                   # API route handlers
    qwen_client.py             # Ollama HTTP client
  frontend/
    index.html
    static/
      app.js
      app.css
      vendor/           # Vendored Cytoscape.js and fonts (offline-first)
  sample_project/
    sample_project.py   # Fixed test fixture — do not modify
  tests/
  docs/
    quick_start.md       # Non-technical quick-start guide
    pipeline/              # Build specification and implementation history
  run.py
  requirements.txt
API

The backend exposes a local HTTP API (see docs/pipeline/CodeStruct_Project_Plan.md for full request/response schemas):

Method	Path	Purpose
POST	/api/analyze	Analyze a project path, return the architecture graph
GET	/api/symbol/{node_id}	Symbol detail: metrics, relationships, docstring
GET	/api/source	Syntax-highlighted source for a line range
GET	/api/impact/{node_id}	Transitive change-impact for a symbol
GET	/api/patterns	Detected design patterns in the current project
POST	/api/open_in_editor	Launch a file in the system default editor
POST	/api/qwen/chat	Chat with the AI assistant, with symbol context
GET	/api/qwen/status	AI assistant connection status
GET	/api/config	Startup configuration (e.g. initial project path)
Known limitations
Polymorphic method calls (e.g. a call on a variable whose runtime type depends on a loop or branch) are not resolved to a specific subclass method — this is a deliberate scope limit, not a bug.
Only within-project base classes are resolved for inheritance; external/library base classes are skipped without error.
Pattern detection is heuristic, structural matching — not a guarantee of design intent.
Single project analyzed at a time; no multi-project workspace.
Dynamic/runtime execution analysis is intentionally not implemented — it would require a process-isolation design that hasn't been built yet (see Roadmap).
Roadmap
Dynamic/runtime execution analysis — gated on a security/sandboxing design that hasn't been written yet. Not scheduled until that design exists and is reviewed.
Packaging/installer — not needed while running from source; unscheduled.
Development history

This project was rebuilt from scratch after an earlier version failed due to an unstable embedded-IDE architecture. The full build specification, phase-by-phase implementation evidence, and verification reports are kept in docs/pipeline/ as a genuine project record, not just planning scratch work.
