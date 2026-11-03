# CodeStruct — Python Project Structure Analyzer

A desktop tool that statically analyzes a Python project's structure (modules, classes, functions, methods, and their relationships) using Python's built-in `ast` module, and renders it as an interactive graph.

## Tech Stack

| Layer | Choice |
|---|---|
| Backend framework | FastAPI + Uvicorn |
| Native window | `pywebview` |
| Graph rendering | Cytoscape.js (vendored local copy) |
| Syntax highlighting | Pygments (server-side, renders HTML) |
| AI backend | Ollama local HTTP API, model `qwen2.5-coder:3b` |
| Analysis | Python standard library `ast` module only |
| Language/runtime | Python 3.10+ |

## Folder Structure

```
codestruct/
  backend/
    __init__.py
    main.py            # FastAPI app, static file mount, pywebview launcher
    analyzer.py         # AST analysis engine
    schemas.py           # Pydantic models
    api.py                 # API route handlers
    qwen_client.py          # Ollama HTTP client
  frontend/
    index.html
    static/
      app.js
      app.css
      vendor/
        cytoscape.min.js
  sample_project/
    sample_project.py    # Fixed test fixture
  tests/
    test_analyzer.py
    test_api.py
  docs/
    quick_start.md       # This guide
  run.py                   # Top-level entry point
  requirements.txt
  README.md
```

## Running the Full Test Suite

```powershell
pytest tests -v
```

All 25 tests across Phases 0–8 should pass.

## Design-Pattern Detection (Phase 13)

CodeStruct provides automated structural detection for three classic design patterns:
- **Singleton**: Detects classes defining a `__new__` method that guards against `None` on a class-level attribute and returns the cached instance.
- **Factory**: Detects functions or methods returning 2 or more distinct project classes across different branches of an `if`/`elif`/`else` chain.
- **Observer (Subject)**: Detects classes containing a method that iterates a `self`-owned collection (`for <var> in self.<attr>:`) and invokes a method on each element.

> **Heuristic Limitation Notice**: This is heuristic pattern-matching on code structure, not guaranteed correct identification of design intent. It identifies structural AST patterns rather than verifying architectural intent.

## How to Contribute

This is a solo MVP build. Deferred features (design-pattern detection, persistent caching, multi-project support, etc.) are tracked in the project's backlog (Section 9 of the plan document). New contributions should follow the phased pipeline: write `prompt.md` for the desired phase, verify against the plan document's Success Criteria, and ensure all guardrails are respected.

## License

Internal build — CodeStruct MVP.