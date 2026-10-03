# Deployment

## Local packaged service

Install the reviewed wheel, configure project aliases and a writable data location, run `codestruct doctor`, then `codestruct serve`. The default listener is `127.0.0.1:8000`; the UI is `/app/`, liveness is `/health/live`, readiness is `/health/ready`, and version metadata is `/api/v1/version`. Neither startup nor analysis depends on the working directory.

Windows PowerShell example:

```powershell
$env:CODESTRUCT_AUTHORIZED_ROOTS = 'team=D:\projects\team'
$env:CODESTRUCT_DATABASE_PATH = "$env:LOCALAPPDATA\CodeStruct\codestruct.sqlite3"
codestruct doctor
codestruct serve
```

POSIX example (not yet executed on this project):

```sh
export CODESTRUCT_AUTHORIZED_ROOTS='team=/srv/projects/team'
export CODESTRUCT_DATABASE_PATH="${XDG_DATA_HOME:-$HOME/.local/share}/CodeStruct/codestruct.sqlite3"
codestruct doctor
codestruct serve
```

The installed package may be read-only; configuration, SQLite/WAL, cache, and logs belong outside it. Logs currently go to process stdout/stderr; use the service manager for rotation. Mount analyzed projects read-only when possible and keep the runtime-data directory private and writable only by the service identity.

## Network and container boundary

CodeStruct has no public authentication. Do not expose it directly to an untrusted network. A network deployment requires an authenticated reverse proxy, TLS termination, explicit trusted origins, request/concurrency limits, network isolation, and private cache headers. Non-loopback CLI binding emits a warning.

`Dockerfile` is a multi-stage Node/Python build and runs the runtime as UID 10001. `compose.example.yml` binds only loopback, persists `/data`, and mounts sample source read-only. Docker was not available/validated unless the Phase 14 result explicitly says otherwise; image build may download base images and requires separate authorization.

Stop with the service manager or an interrupt so Uvicorn can close workers and SQLite connections. Back up SQLite while stopped. Monitor readiness plus safe structured application logs; never publish raw tracebacks or canonical project paths.
