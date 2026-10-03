# Contributing to CodeStruct

## Development workflow

Create a focused branch from an up-to-date `main`. Use one of these prefixes:

- `feat/` for product features
- `fix/` for defect fixes
- `test/` for test-only changes
- `docs/` for documentation
- `perf/` for measured performance work
- `spike/` for explicitly disposable research
- `chore/` for maintenance
- `release/` for release preparation

Keep commits small and use Conventional Commits, such as `feat: add module
filtering`, `fix: preserve qualified imports`, `test: characterize inheritance
analysis`, or `docs: document local setup`. Separate configuration, tests,
documentation, and CI changes when that makes review or rollback safer.

## Version-control and milestone policy

1. **Declared Scope Isolation:** Each milestone stays strictly within its declared scope.
2. **Pre-Review Commit & Push Gate:** Antigravity commits and pushes a milestone only after all its required gates pass and it is ready for Codex review.
3. **Bounded Correction Commits:** Review corrections receive bounded follow-up commits after their specific gates pass.
4. **Acceptance Documentation Commits:** Codex acceptance is recorded in a small acceptance/tracker commit when applicable.
5. **No Milestone Mixing:** Never combine the next milestone with the current commit.
6. **Immutable Published History & Safety:** Never rewrite published history, force-push, commit secrets/generated runtime data, or tag/release/deploy unless the user explicitly requests it.

## Pull requests

A pull request should explain the problem, scope, user-visible behavior, and
validation performed. Link related issues and update tests and documentation when
behavior changes. Keep unrelated cleanup out of the pull request. Before review,
run all commands in the root README and confirm that generated files, secrets,
local databases, and virtual environments are not included.

Authors own the implementation, self-review the diff, resolve automated-check
failures, and respond to feedback. Reviewers verify correctness, test coverage,
security impact, compatibility, and scope. At least one maintainer approval and
passing required checks should be required before merge. Authors should not
approve their own pull requests.

Authorized roots, path handling, process execution, cache keys, serialization,
SQLite, CORS, and diagnostics require security-focused review. Never commit
credentials, `.env`, environments, dependencies, coverage, builds, databases,
WAL/SHM files, logs, or generated benchmarks. Analyzed-source fixtures must be
inert and protected by no-execution regression tests. Update public docs whenever
behavior changes.

## Resolving conflicts

Update the branch from `main`, resolve conflicts deliberately in the branch, and
rerun the full validation suite. Do not discard another contributor's changes or
use destructive history rewriting on a shared branch. Ask the owners of ambiguous
changes to review the resolution.

## Releases and rollback

CodeStruct follows Semantic Versioning: patch releases contain compatible fixes,
minor releases add compatible functionality, and major releases contain breaking
changes. Record release changes before tagging a release.

Prefer reverting the smallest faulty commit or pull request to restore `main`.
For a faulty published release, revert the change, rerun required checks, and
publish a new patch version; do not move or overwrite an existing release tag.
Document any data or configuration recovery steps in the corrective pull request.

## Suggested initial commit sequence

For this repository baseline, a reviewable sequence would be:

1. `chore: configure Python project and ignore rules`
2. `test: characterize analyzer and API behavior`
3. `docs: document development and maintenance workflows`
4. `ci: add Python and frontend validation workflows`

## Test commands

After activating the repository-local `.venv` and installing `.[dev]`, use:

```powershell
python -m pytest -m "unit or contract" --no-cov
python -m pytest -m "not performance and not slow"
python -m pytest -m "integration or process" --no-cov
python -m pytest -m "process or platform" --no-cov
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

The benchmark is deliberately separate from ordinary correctness tests. Manual
keyboard, screen-reader, contrast, visual, and cross-platform workflow review is
still required even when automated accessibility and platform checks pass.
