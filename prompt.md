# Phase 13: Design-Pattern Detection (Sprint 2)

## Objective
Detect three structurally-recognizable design patterns — Singleton, Factory, Observer — in the analyzed project using precise AST-based heuristics, and surface them in the UI. This is heuristic pattern-matching on code structure, not guaranteed correct identification of design intent — document this limitation explicitly in the UI and in `README.md`.

## Preconditions
Phase 1 (analysis engine) and Phase 11 (custom project paths) complete.

## Detection Heuristics — implement exactly as specified, do not invent alternative rules:

### 1. Singleton
A class is flagged `Singleton` if ALL of the following hold:
- It defines a `__new__` method.
- That method's body contains an `if` statement whose test compares a class-level attribute (`cls.<name>` or `ClassName.<name>`) to `None`.
- Inside that `if` block, there is an assignment to that same attribute.
- The method returns that attribute (directly, or via the class attribute reference) at the end.
- Evidence string to report: `"__new__ guards and returns a cached class-level instance"`.

### 2. Factory
A function or method is flagged `Factory` if ALL of the following hold:
- Its body contains 2 or more `return <ClassName>(...)` statements (a `constructs` edge whose call is the direct subject of a `return`).
- Those `ClassName`s are at least 2 distinct classes defined within the analyzed project.
- Those return statements occur in different branches of the same `if`/`elif`/`else` chain (not sequential unconditional returns).
- Evidence string to report: `"returns different constructed types across conditional branches"`.

### 3. Observer/Subject
A class is flagged `Observer` (specifically, as the *subject* in the pattern) if ALL of the following hold:
- It has a method containing a `for <var> in self.<attr>:` loop (iterating a `self`-owned attribute).
- Inside that loop's body, there is a method call on the loop variable (`<var>.<method>(...)`).
- Evidence string to report: `"iterates a self-owned collection and invokes a method on each element"`.

## Tasks
1. Implement `detect_patterns(graph: dict, ast_trees: dict) -> list[dict]` in `backend/analyzer.py` (or a new `backend/patterns.py` — your call, but keep it a clearly separate function from `analyze_project`), applying the three heuristics above against the already-parsed AST. Each match produces `{ "pattern": "Singleton" | "Factory" | "Observer", "symbol_id": "string", "evidence": "string" }` using the exact evidence strings specified above.
2. Add `GET /api/patterns` returning `{ "patterns": [...] }` for the currently-analyzed project (same in-memory last-analysis pattern as other endpoints — no re-analysis).
3. Create three new fixture files for testing (do **not** modify `sample_project/sample_project.py` — it must stay exactly as specified in Section 7):
   - `tests/pattern_fixtures/singleton_example.py`
   - `tests/pattern_fixtures/factory_example.py`
   - `tests/pattern_fixtures/observer_example.py`
   Each file should contain a minimal, clean example of its pattern per the heuristic rules above (e.g., the `Singleton`/`ShapeFactory`+`Circle`+`Square`/`Subject`+`ConcreteObserver` examples are acceptable reference shapes — write clean, minimal versions of each).
4. Add a "Patterns" tab in the center area (alongside Graph/Code/Table) listing detected patterns as a simple list: pattern name, symbol name, evidence string. Clicking an entry selects that symbol (same selection-sync as other views).

## Files to create/modify
- `backend/analyzer.py` or `backend/patterns.py` (detection logic)
- `backend/api.py` (add `GET /api/patterns` endpoint)
- `backend/schemas.py` (add `PatternMatch` model)
- `tests/pattern_fixtures/singleton_example.py`
- `tests/pattern_fixtures/factory_example.py`
- `tests/pattern_fixtures/observer_example.py`
- `tests/test_patterns.py`
- `frontend/static/app.js` (Patterns tab, selection sync)
- `frontend/index.html` (Patterns tab button, list UI)

## Interface contracts

### PatternMatch (new model for Section 4.2/4.3)
```json
{
  "pattern": "Singleton | Factory | Observer",
  "symbol_id": "string",
  "evidence": "string"
}
```

### GET /api/patterns (extends Section 4.3)
**Response:**
```json
{ "patterns": [ { "pattern": "string", "symbol_id": "string", "evidence": "string" } ] }
```

## Guardrails — do NOT do the following
- Do not add other patterns (e.g., Strategy, Decorator) in this phase.
- Do not loosen the heuristics to catch "near-matches" — strict adherence to the specified rules is required to avoid false positives on `sample_project` (which must return zero matches).
- Do not claim certainty in the UI — label this feature as heuristic-based pattern matching, not verified design intent.
- Do not implement anything from the Backlog section (Section 9) of the plan document.
- Do not implement anything from a different phase (including Phases 14, 15, 16).
- If you believe something is missing from these instructions, stop and ask rather than guessing.

## What I need back in report.md
- A list of every file you created or changed.
- The exact commands you ran to test this phase (copy-pasted, not summarized).
- The exact output of those commands (not "tests passed" — the actual output).
- An explicit statement, for each Success Criteria checklist item below, of pass or fail.
- Anything you were unsure about or had to make a judgment call on.

## This phase's Success Criteria
- [ ] Each of the three fixtures is detected individually with the correct, exact evidence string.
- [ ] Analyzing the fixtures directory via the API returns all three patterns.
- [ ] Analyzing `sample_project` returns zero patterns (negative control passes — confirms no false positives on the regression fixture).
- [ ] Patterns tab in the UI lists and correctly syncs selection for all three.