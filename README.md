# CodeStruct

CodeStruct is a static analyzer for exploring the structure of a Python project.
The backend safely scans authorized roots, extracts deterministic Python AST
metadata, conservatively resolves a versioned architecture graph, and runs each
analysis in a bounded spawned worker. The React frontend submits and polls jobs
through `/api/v1` and renders results with React Flow.

Implemented capabilities include safe configured-project discovery, recursive
scanning, deterministic AST/graph extraction, conservative resolution, spawned
jobs, cancellation, SQLite caching/restart recovery, bounded graph pages,
search/filter/details/diagnostics, and an accessible table. Static analysis never
imports or executes project code.

The repository supports Python 3.10 through 3.14 and Node.js versions accepted by
Vite 8 (`^20.19.0` or `>=22.12.0`). Environment overrides are documented in
[.env.example](.env.example); when no authorized roots are configured in a source
checkout, the backend permits the repository `sample_project` under the capability
name `sample`. A wheel has no sample project and exposes no projects until configured.
Normal deployments should configure non-sensitive aliases such as
`team=PATH_TO_PROJECT`; the UI uses only the alias and the API never returns the
canonical root. See [configuration](docs/configuration.md) and the
[user guide](docs/user-guide.md).

## Python setup

From the repository root in PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On macOS or Linux, activate the environment with
`source .venv/bin/activate`. Python 3.10, 3.11, 3.12, 3.13, or 3.14 may be used.
The `dev` extra includes the runtime and development dependencies needed for the
checks below.

## Frontend setup

Install the locked frontend dependency set from the repository root:

```powershell
npm --prefix frontend ci
```

## Run the application

Start the package-based backend from the repository root:

```powershell
python -m uvicorn codestruct.api.app:app --app-dir backend/src --reload
```

The API is available at `http://127.0.0.1:8000`. The v1 workflow uses
`POST /api/v1/analyses`, status polling, graph/diagnostic retrieval, and `DELETE`
for cancellation. The transitional `GET /` and synchronous `GET /analyze`
contracts remain available during compatibility verification.

In another shell, start the frontend from the repository root:

```powershell
npm --prefix frontend run dev
```

Vite serves the development UI at `http://localhost:5173` by default.
Its development proxy forwards `/api` to the local backend. Set
`VITE_CODESTRUCT_API_URL` only when the API is deliberately served elsewhere.

Submit the default sample directly with:

```powershell
$body = '{"project":{"root_id":"sample","relative_path":"."}}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/analyses -ContentType application/json -Body $body
```

Poll the returned `links.self`; retrieve `links.graph` and `links.diagnostics`
after `completed` or `partially_completed`. `DELETE links.self` requests
idempotent cooperative cancellation. Job and result state expires after the
configured retention interval and is stored in the configured SQLite database.
Complete compatible results are reused
only after content, policy, analyzer, resolver, schema, expiry, checksum, and graph
validation checks; `refresh: true` forces a cold attempt. Interrupted nonterminal
jobs become safely failed with `PROCESS_RESTARTED` when the service reopens.

SQLite defaults to the platform user-data location (`%LOCALAPPDATA%\CodeStruct`
on Windows and `$XDG_DATA_HOME/CodeStruct` or `~/.local/share/CodeStruct` on POSIX), uses WAL,
foreign keys, a busy timeout, per-operation connections, 15-minute retention,
and bounded LRU eviction. Stop CodeStruct before development cleanup, then remove
only the configured runtime-data directory after verifying its path. Never place
the database in a shared/public artifact store because it contains local analysis
results and an internal canonical project identity.
Back up the database while CodeStruct is stopped before a version upgrade; schema
migrations are transactional and refuse unsupported future versions without
deleting data. Storage lock, corruption, migration, size, or permission failures
surface as safe service errors rather than an undocumented memory fallback.

The frontend always starts with a bounded graph page and loads more only on user
request. Direct clients may request a complete graph within the configured byte
limit; larger unbounded requests return `GRAPH_TOO_LARGE`. Request
`GET .../graph?limit=1000&cursor=...` and optionally filter by `node_kind`,
`edge_kind`, or `resolution_status`. Pages include returned/total counts and an
opaque result-bound cursor.

Measured baselines and derived capacity budgets are in
[docs/performance/baseline.md](docs/performance/baseline.md) and
[docs/performance/budgets.md](docs/performance/budgets.md).

## Validate changes

Run the backend tests and Python quality checks from the repository root:

```powershell
python -m pytest -m "unit or contract" --no-cov
python -m pytest -m "not performance and not slow"
python -m pytest -m "integration or process" --no-cov
python -m pytest thonny-plugin/tests --no-cov
python -m ruff format --check backend tests sample_project
python -m ruff format --check thonny-plugin
python -m ruff check backend tests sample_project
python -m ruff check thonny-plugin
python -m mypy
```

Run the frontend checks from the repository root:

```powershell
npm --prefix frontend test
npm --prefix frontend run test:coverage
npm --prefix frontend run test:a11y
npm --prefix frontend run lint
npm --prefix frontend run build
```

The build output is written to the ignored `frontend/dist` directory.

## Local packaged release

Version `0.1.0.dev0` is sourced from `codestruct.__about__` and injected into
the API and frontend build. Build review-only artifacts with Node 24 and the
release extra:

```powershell
python -m pip install -e ".[release]"
python tools/build_release.py
python tools/verify_artifacts.py release-output --version 0.1.0.dev0
```

The build creates an ignored wheel, source distribution, and SHA-256 report.
A prebuilt wheel needs Python 3.10–3.14 but not Node. Building a fresh frontend
from a source checkout requires Node/npm; the reviewed sdist already contains
release-built assets and can build a wheel without Node. After wheel install:

```powershell
codestruct --version
codestruct doctor
codestruct serve
```

Open `http://127.0.0.1:8000/app/`. `serve` defaults to loopback and does not
enable reload. See the [release checklist](docs/release/checklist.md),
[build guide](docs/release/building.md), and
[deployment guide](docs/release/deployment.md). Public distribution remains
blocked until the owner selects a license and approves maintainer/project URL
metadata; network exposure additionally requires external authentication and TLS.

Run the controlled performance benchmark separately; it creates and safely
removes only ignored generated fixtures under the repository test-output area:

```powershell
python tests/performance/benchmark.py
```

## Project status

Deterministic AST analysis, conservative static graph resolution, the v1
background-job API, persistent caching, and interactive graph exploration are
implemented. Dynamic analysis, incremental file caching, architecture metrics,
LLM features, and editor integration are not part of the current application.
Large graphs are not virtualized, source navigation is unavailable, and macOS,
Linux, real screen readers, 200% zoom, and complete fault injection remain pending.

Contribution and release practices are documented in [CONTRIBUTING.md](CONTRIBUTING.md).
Security reporting guidance is in [SECURITY.md](SECURITY.md).
Developer references: [setup](docs/development/setup.md),
[architecture](docs/development/architecture.md), [testing](docs/development/testing.md),
[troubleshooting](docs/development/troubleshooting.md), [API](docs/api/v1.md), and
[operations](docs/operations.md).
