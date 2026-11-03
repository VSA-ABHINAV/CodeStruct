# CodeStruct Phase 13: Design-Pattern Detection Report

## 1. Files Created / Modified

- `codestruct/backend/patterns.py` (New):
  - Implemented `detect_patterns(graph: dict, ast_trees: dict = None) -> list[dict]`.
  - Implemented exact AST heuristics for:
    - **Singleton**: Class defines `__new__` method, guards against `None` on class-level attribute (`cls.<name>` or `ClassName.<name> is None`), assigns to that attribute inside the `if` block, and returns it at the end.
      Evidence string: `"__new__ guards and returns a cached class-level instance"`.
    - **Factory**: Function or method contains 2 or more `return <ClassName>(...)` statements constructing at least 2 distinct classes defined within the analyzed project across different branches of the same `if`/`elif`/`else` chain.
      Evidence string: `"returns different constructed types across conditional branches"`.
    - **Observer (Subject)**: Class contains a method with a `for <var> in self.<attr>:` loop (iterating a `self`-owned attribute) and invokes a method call on that loop variable (`<var>.<method>(...)`).
      Evidence string: `"iterates a self-owned collection and invokes a method on each element"`.
- `codestruct/backend/analyzer.py`:
  - Imported and re-exported `detect_patterns`.
  - Updated `analyze_project` to collect `ast_trees` during AST traversal and precompute detected patterns in the returned graph dictionary (`graph["patterns"]` and `graph["_ast_trees"]`).
- `codestruct/backend/schemas.py`:
  - Added `PatternMatch(BaseModel)` with `pattern: Literal["Singleton", "Factory", "Observer"]`, `symbol_id: str`, and `evidence: str`.
  - Added `PatternsResponse(BaseModel)` with `patterns: List[PatternMatch]`.
- `codestruct/backend/api.py`:
  - Added `GET /api/patterns` endpoint returning `PatternsResponse` for the currently analyzed project using cached in-memory graph data with zero re-analysis.
- `tests/pattern_fixtures/singleton_example.py` (New):
  - Minimal clean fixture with `DatabaseConnection` class implementing the singleton heuristic.
- `tests/pattern_fixtures/factory_example.py` (New):
  - Minimal clean fixture with `Circle` and `Square` classes and `create_shape` function returning distinct shapes across `if`/`elif` branches.
- `tests/pattern_fixtures/observer_example.py` (New):
  - Minimal clean fixture with `Observer` and `EventDispatcher` classes notifying subscribers via `for sub in self.subscribers: sub.update(message)`.
- `tests/test_patterns.py` (New):
  - 8 automated unit and API integration tests covering individual fixture detection, directory-level detection via `GET /api/patterns`, negative control on `sample_project` (zero false positives), and heuristic constraint edge cases.
- `codestruct/tests/` (Synchronized):
  - Synced `tests/pattern_fixtures` and `tests/test_patterns.py` to `codestruct/tests/`.
- `codestruct/frontend/index.html`:
  - Added `#tab-patterns` button in `.center-tabs` alongside Graph, Table, and Code Viewer.
  - Added `#patterns-viewport` containing `#patterns-placeholder`, a prominent disclaimer banner labeling heuristic pattern matching per specification, `#patterns-empty` for zero-match projects, and `#patterns-list`.
- `codestruct/frontend/static/app.css`:
  - Added styling for `#patterns-viewport`, `.patterns-disclaimer-banner`, `.patterns-list`, `.pattern-card`, `.pattern-badge` (`.badge-Singleton`, `.badge-Factory`, `.badge-Observer`), `.pattern-evidence`, and `.pattern-card.selected`.
- `codestruct/frontend/static/app.js`:
  - Updated `switchCenterTab(tabName)` to support `"patterns"`.
  - Implemented `loadPatterns()` and `renderPatternsView(patterns)`.
  - Implemented bidirectional selection sync: clicking a `.pattern-card` calls `selectSymbol(item.symbol_id, "patterns")`, and selecting any symbol from Graph, Explorer, Table, or Inspector highlights the matching `.pattern-card` and scrolls it into view.
  - Updated `runAnalysis()` to refresh patterns on analysis completion.
  - Exported `window.loadPatterns` and `window.renderPatternsView`.
- `README.md`:
  - Documented the Design-Pattern Detection feature and explicitly documented the heuristic limitation notice per prompt requirements.
- `PROGRESS.md`:
  - Recorded Phase 13 completion status.

---

## 2. Test Commands and Verbatim Output

### Command 1: Pytest Suite for Design-Pattern Detection
`python -m pytest tests/test_patterns.py -v`

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: D:\CodeStruct
plugins: anyio-4.15.1, langsmith-0.6.6, cov-7.1.0, platformdirs-4.12.3
collecting ... collected 8 items

tests/test_patterns.py::test_singleton_fixture_detected_individually PASSED [ 12%]
tests/test_patterns.py::test_factory_fixture_detected_individually PASSED [ 25%]
tests/test_patterns.py::test_observer_fixture_detected_individually PASSED [ 37%]
tests/test_patterns.py::test_api_patterns_endpoint_fixtures_directory PASSED [ 50%]
tests/test_patterns.py::test_api_patterns_negative_control_sample_project PASSED [ 62%]
tests/test_patterns.py::test_api_patterns_empty_when_no_project_analyzed PASSED [ 75%]
tests/test_patterns.py::test_factory_requires_distinct_project_classes PASSED [ 87%]
tests/test_patterns.py::test_observer_requires_iteration_over_self_attribute PASSED [100%]

============================== warnings summary ===============================
C:\Users\ABHINAV\AppData\Roaming\Python\Python314\site-packages\starlette\testclient.py:53
  C:\Users\ABHINAV\AppData\Roaming\Python\Python314\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 8 passed, 1 warning in 1.60s =========================
```

---

### Command 2: Full Regression Pytest Suite
`python -m pytest tests -v`

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: D:\CodeStruct
plugins: anyio-4.15.1, langsmith-0.6.6, cov-7.1.0, platformdirs-4.12.3
collecting ... collected 40 items

tests/test_analyzer.py::test_sample_project_node_counts PASSED           [  2%]
tests/test_analyzer.py::test_sample_project_inherits_edges PASSED        [  5%]
tests/test_analyzer.py::test_sample_project_defines_edges PASSED         [  7%]
tests/test_analyzer.py::test_sample_project_constructs_edges PASSED      [ 10%]
tests/test_analyzer.py::test_sample_project_calls_edges PASSED           [ 12%]
tests/test_analyzer.py::test_sample_project_errors_empty PASSED          [ 15%]
tests/test_analyzer.py::test_graceful_error_handling PASSED              [ 17%]
tests/test_api.py::test_analyze_endpoint_sample_project PASSED           [ 20%]
tests/test_api.py::test_symbol_endpoint_dog_inherits PASSED              [ 22%]
tests/test_api.py::test_symbol_endpoint_animal_details PASSED            [ 25%]
tests/test_api.py::test_symbol_endpoint_main_calls_build_zoo PASSED      [ 27%]
tests/test_api.py::test_symbol_endpoint_not_found PASSED                 [ 30%]
tests/test_api.py::test_source_endpoint_valid_range PASSED               [ 32%]
tests/test_api.py::test_source_endpoint_invalid_file_4xx PASSED          [ 35%]
tests/test_api.py::test_source_endpoint_invalid_line_range_4xx PASSED    [ 37%]
tests/test_api.py::test_source_endpoint_animal_speak_slice PASSED        [ 40%]
tests/test_api.py::test_source_endpoint_dog_fetch_slice PASSED           [ 42%]
tests/test_api.py::test_source_endpoint_build_zoo_slice PASSED           [ 45%]
tests/test_api.py::test_chat_endpoint_with_symbol_context PASSED         [ 47%]
tests/test_api.py::test_chat_endpoint_ollama_down_graceful_error PASSED  [ 50%]
tests/test_api.py::test_chat_endpoint_recovery_after_down PASSED         [ 52%]
tests/test_api.py::test_analyze_endpoint_empty_path_400 PASSED           [ 55%]
tests/test_api.py::test_analyze_endpoint_invalid_path_400 PASSED         [ 57%]
tests/test_api.py::test_analyze_endpoint_custom_path PASSED              [ 60%]
tests/test_api.py::test_analyze_endpoint_root_project_file PASSED        [ 62%]
tests/test_api.py::test_analyze_endpoint_empty_directory_warning PASSED  [ 65%]
tests/test_api.py::test_analyze_endpoint_non_python_file_400 PASSED      [ 67%]
tests/test_api.py::test_analyze_endpoint_broken_file_handled_in_errors PASSED [ 70%]
tests/test_api.py::test_qwen_status_endpoint PASSED                      [ 72%]
tests/test_api.py::test_open_in_editor_endpoint_success PASSED           [ 75%]
tests/test_api.py::test_open_in_editor_endpoint_missing_file_404 PASSED  [ 77%]
tests/test_api.py::test_symbol_detail_instability_metric PASSED          [ 80%]
tests/test_patterns.py::test_singleton_fixture_detected_individually PASSED [ 82%]
tests/test_patterns.py::test_factory_fixture_detected_individually PASSED [ 85%]
tests/test_patterns.py::test_observer_fixture_detected_individually PASSED [ 87%]
tests/test_patterns.py::test_api_patterns_endpoint_fixtures_directory PASSED [ 90%]
tests/test_patterns.py::test_api_patterns_negative_control_sample_project PASSED [ 92%]
tests/test_patterns.py::test_api_patterns_empty_when_no_project_analyzed PASSED [ 95%]
tests/test_patterns.py::test_factory_requires_distinct_project_classes PASSED [ 97%]
tests/test_patterns.py::test_observer_requires_iteration_over_self_attribute PASSED [100%]

============================== warnings summary ===============================
C:\Users\ABHINAV\AppData\Roaming\Python\Python314\site-packages\starlette\testclient.py:53
  C:\Users\ABHINAV\AppData\Roaming\Python\Python314\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 40 passed, 1 warning in 23.81s ========================
```

---

### Command 3: Live Pywebview E2E Verification
`python verify_phase13.py`

```text
INFO:     Started server process [25640]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8099 (Press CTRL+C to quit)
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [25640]
[CodeStruct Startup] Ollama service connected (qwen2.5-coder:3b).
======================================================================
STARTING PHASE 13 E2E VERIFICATION
======================================================================
[E2E] Webview DOM readyState: complete

======================================================================
TESTING SUCCESS CRITERION 1: Individual Fixture Detection
======================================================================
[SC1] Singleton individual detection: [{'pattern': 'Singleton', 'symbol_id': 'singleton_example.DatabaseConnection', 'evidence': '__new__ guards and returns a cached class-level instance'}]
[SC1] Factory individual detection: [{'pattern': 'Factory', 'symbol_id': 'factory_example.create_shape', 'evidence': 'returns different constructed types across conditional branches'}]
[SC1] Observer individual detection: [{'pattern': 'Observer', 'symbol_id': 'observer_example.EventDispatcher', 'evidence': 'iterates a self-owned collection and invokes a method on each element'}]
[SC1] PASS: True

======================================================================
TESTING SUCCESS CRITERION 2: Analyzing Fixtures Directory via API
======================================================================
[SC2] GET /api/patterns on fixtures dir: status=200
[SC2] Patterns returned count=3: [{'pattern': 'Factory', 'symbol_id': 'factory_example.create_shape', 'evidence': 'returns different constructed types across conditional branches'}, {'pattern': 'Observer', 'symbol_id': 'observer_example.EventDispatcher', 'evidence': 'iterates a self-owned collection and invokes a method on each element'}, {'pattern': 'Singleton', 'symbol_id': 'singleton_example.DatabaseConnection', 'evidence': '__new__ guards and returns a cached class-level instance'}]
[SC2] PASS: True

======================================================================
TESTING SUCCESS CRITERION 3: Negative Control on sample_project
======================================================================
[SC3] GET /api/patterns on sample_project: count=0 (expected: 0)
[SC3] PASS: True

======================================================================
TESTING SUCCESS CRITERION 4: Patterns Tab in UI & Selection Sync
======================================================================
[SC4] Tab active=True, viewport visible=True, disclaimer=True, card count=3
[SC4] Singleton card click: sel_id=singleton_example.DatabaseConnection, card_sel=True, inspector=DatabaseConnection
[SC4] Factory card click: sel_id=factory_example.create_shape, card_sel=True, prev_unsel=True, inspector=create_shape
[SC4] Observer card click: sel_id=observer_example.EventDispatcher, card_sel=True, inspector=EventDispatcher
[SC4] External selection sync: card_sel=True
[SC4] PASS: True

======================================================================
FINAL PHASE 13 VERIFICATION RESULTS
======================================================================
[SC1] PASS
[SC2] PASS
[SC3] PASS
[SC4] PASS
======================================================================
ALL 4 SUCCESS CRITERIA PASSED LIVE IN PYWEBVIEW!
======================================================================
```

---

## 3. Success Criteria Checklist

| Criterion | Requirement | Verification Method | Status |
|---|---|---|:---:|
| **SC 1** | Each of the three fixtures is detected individually with the correct, exact evidence string. | Analyzed `singleton_example.py`, `factory_example.py`, and `observer_example.py` individually in `test_patterns.py` and live pywebview. Verified exact pattern names, symbol IDs, and exact evidence strings. | **PASS** |
| **SC 2** | Analyzing the fixtures directory via the API returns all three patterns. | Analyzed `tests/pattern_fixtures/` via `POST /api/analyze` and fetched `GET /api/patterns`. Verified response status 200 and exactly 3 pattern matches (`Singleton`, `Factory`, `Observer`). | **PASS** |
| **SC 3** | Analyzing `sample_project` returns zero patterns (negative control passes — confirms no false positives on the regression fixture). | Analyzed `sample_project` via `POST /api/analyze` and called `GET /api/patterns`. Verified returned `patterns` array has `len == 0`. | **PASS** |
| **SC 4** | Patterns tab in the UI lists and correctly syncs selection for all three. | Verified in live pywebview: `#tab-patterns` switches to Patterns view, renders all 3 cards with badges/names/evidence, clicking each card synchronizes selection with Explorer and Inspector (`DatabaseConnection`, `create_shape`, `EventDispatcher`), and external selection sync highlights the corresponding card. | **PASS** |

---

## 4. Judgment Calls and Assumptions

1. **AST Extraction Architecture**:
   - Implemented `detect_patterns` in a standalone module `backend/patterns.py` and re-exported it from `backend/analyzer.py`. This keeps the core AST analyzer modular while supporting both in-memory precomputation during `analyze_project` and standalone invocations on arbitrary graphs/AST trees.
2. **Heuristic Disclaimers**:
   - In accordance with the prompt's explicit requirement not to claim certainty, a permanent notice banner was added at the top of the Patterns tab container (`.patterns-disclaimer-banner`) stating: *"Heuristic Detection: Patterns are identified via AST structural heuristics and indicate potential design patterns, not verified design intent."* This notice is also documented in `README.md`.
3. **Empty Project / Pre-Analysis Behavior**:
   - `GET /api/patterns` returns `{"patterns": []}` with status 200 when no project has yet been analyzed, preventing frontend console errors when switching tabs before analysis.
