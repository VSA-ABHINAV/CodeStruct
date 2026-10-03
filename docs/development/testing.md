# Development testing

```powershell
python -m pytest -m "unit or contract" --no-cov
python -m pytest -m "not performance and not slow"
python -m pytest -m "integration or process" --no-cov
python -m pytest --cov=backend --cov-branch --cov-report=term-missing --cov-report=html
python -m pytest thonny-plugin/tests --no-cov
python -m ruff format --check backend tests sample_project
python -m ruff format --check thonny-plugin
python -m ruff check backend tests sample_project
python -m ruff check thonny-plugin
python -m mypy
npm --prefix frontend test
npm --prefix frontend run test:coverage
npm --prefix frontend run test:a11y
npm --prefix frontend run lint
npm --prefix frontend run build
python tests/performance/benchmark.py
```

Markers are `unit`, `contract`, `integration`, `process`, `performance`, `slow`,
and `platform`. Benchmarks are separate from correctness tests. Automated axe is
partial evidence; screen-reader/visual review is manual.

Fixtures must be deterministic, relative, and secret-free. Analyzed Python must
never be imported, executed, or compiled for execution. Generated benchmarks go
only in ignored test-output and are cleaned after exact-path verification. See
[automated strategy](../testing/automated-test-strategy.md) and
[manual plan](../testing/manual-test-plan.md).
