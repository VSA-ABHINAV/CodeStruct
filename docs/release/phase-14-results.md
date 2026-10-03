# Phase 14 results

## Environment and scope

Validation ran on Windows 11 (build 26200), Python 3.14.6, Node 24.18.0, npm 11.16.0, pytest 9.1.1, Ruff 0.16.7, mypy 1.20.2, and build 1.6.1. No tag, remote, upload, registry publication, container build, or external deployment occurred.

## Quality and artifacts

- Backend: 82 passed, one Windows account capability skip, 85.98% branch-aware coverage; the 84% gate passed.
- Frontend: 50 passed with 82.91% line coverage; the focused axe check passed (one selected, 49 skipped by test-name filtering). ESLint and the Vite no-write production build passed.
- Ruff format/lint and mypy passed after the final source changes.
- Controlled benchmarks completed. The 303-file median was 0.920 s parsing and 1.231 s resolution/graph construction; the single 1,515-file run was 14.718 s and 6.637 s respectively. Results remain host-sensitive.
- `codestruct-0.1.0.dev0-py3-none-any.whl`: 206,105 bytes, SHA-256 `2b9f650d09fca404e8f38fac8d2109583cc3d80b7e3c52896260301d8f8e4fed`.
- `codestruct-0.1.0.dev0.tar.gz`: 195,272 bytes, SHA-256 `df5bb04db50bf4e07368578e40552f932783069efff3dcc39586ae0e1272c7ce`.
- Archive verification found 52 wheel members and 71 sdist members, including version metadata, CLI, backend packages, index, and hashed assets; it rejected forbidden path/secret/member patterns and found no tests, databases, environment files, source maps, caches, or Node tree in the wheel.

## Installation and runtime

A fresh wheel and all declared runtime dependencies installed non-editably into an isolated environment whose path contained spaces and non-ASCII characters. From a working directory outside the repository, `codestruct --version` and `codestruct doctor` reported `0.1.0.dev0`; no Node action was needed. The packaged server served the frontend, exposed the same API version, discovered only configured aliases, completed analysis and bounded graph/diagnostic retrieval, produced a real cache hit, cancelled a second job, survived a clean restart with result recovery, and shut down without a remaining tested listener. The source checkout, API, wheel, and bundled UI version checks agree.

Temporary-database tests covered schema-1 forward migration, future-schema refusal, transactional behavior, backup restoration, locks, corruption, cache persistence, restart recovery, and pagination. Reverse migrations are intentionally unavailable. The release build also built its wheel from the sdist in the prepared release environment; a second pip-isolated sdist build could not be authorized and remains pending.

## Supply chain and deployment

`npm ci` and `npm audit --omit=dev` reported zero known vulnerabilities. Direct installed dependency metadata reported FastAPI 0.141.1 (MIT), Pydantic 2.13.5 (MIT), Uvicorn 0.52.4 (BSD-3-Clause), React 19.2.8 (MIT), React DOM 19.2.8 (MIT), and React Flow 12.11.6 (MIT); this is evidence, not legal approval. The repository secret-pattern scan found no candidate after excluding the verifier's literal marker. `pip-audit` was unavailable, so no Python vulnerability result is claimed.

Docker was not installed, therefore the non-root multi-stage image, health check, and compose example were reviewed but not built or scanned. Linux/macOS workflow jobs are prepared but unexecuted. Read-only install behavior follows the no-package-write design; exhaustive unwritable-directory, disk-full, port-collision, and container permission tests remain pending.

## Release blockers and cleanup

Public distribution is blocked until the owner selects a software license and approves maintainer/author and project URL metadata. Authentication and TLS remain required external controls before untrusted network exposure. Real screen-reader, 125%/200% zoom, macOS/Linux, and exhaustive fault-injection evidence also remains pending. All external clean-install environments and their databases were removed after shutdown; one earlier ignored sandbox-created `.codestruct/release-staging` directory could not be removed because Windows denied access, and contains no source or release artifact intended for tracking.
