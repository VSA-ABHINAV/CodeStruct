# Configuration

Environment variables are read at process start; `.env.example` is a template,
not an automatic loader. Invalid bounds fail startup.

| Variable | Default / range | Meaning |
|---|---|---|
| `CODESTRUCT_ENV` | `development` | Label; does not add authentication. |
| `CODESTRUCT_AUTHORIZED_ROOTS` | bundled sample | OS-separated `alias=path`; bare paths become `root-N`; aliases/locations must be unique and existing. |
| `CODESTRUCT_CORS_ORIGINS` | local Vite origins | Comma-separated exact origins; wildcard rejected. |
| `CODESTRUCT_DATABASE_PATH` | platform user-data `CodeStruct/codestruct.sqlite3` | Sensitive local job/cache data; an explicit development override may use ignored `.codestruct/runtime`. |
| `CODESTRUCT_MAX_CONCURRENT_JOBS` | 2; 1–16 | Worker bound. |
| `CODESTRUCT_MAX_QUEUED_JOBS` | 8; 0–100 | Queue bound. |
| `CODESTRUCT_ANALYSIS_TIMEOUT_SECONDS` | 120; 1–3600 | Analysis timeout. |
| `CODESTRUCT_CANCELLATION_GRACE_SECONDS` | 3; 1–30 | Cooperative cancellation grace. |
| `CODESTRUCT_RESULT_RETENTION_SECONDS` | 900; 10–86400 | Result lifetime. |
| `CODESTRUCT_POLLING_INTERVAL_MS` | 750; 250–10000 | Suggested poll delay. |
| `CODESTRUCT_MAX_DEPTH` | 40; 0–200 | Scan depth. |
| `CODESTRUCT_MAX_FILES` | 10000; 1–100000 | File count. |
| `CODESTRUCT_MAX_FILE_SIZE` | 2097152; 1–104857600 | Bytes per file. |
| `CODESTRUCT_MAX_CACHE_RESULTS` | 100; 1–10000 | Cache result count. |
| `CODESTRUCT_MAX_CACHE_BYTES` | 268435456; 1 MiB–10 GiB | Cache budget. |
| `CODESTRUCT_MAX_FULL_GRAPH_BYTES` | 4194304; 64 KiB–128 MiB | Unbounded response cutoff. |
| `CODESTRUCT_MAX_GRAPH_PAGE_SIZE` | 1000; 10–10000 | Server page cap. |
| `VITE_CODESTRUCT_API_URL` | empty | HTTP(S) frontend API base; empty uses same origin/proxy. |
| `CODESTRUCT_FRONTEND_BASE` | `/` for direct Vite builds | Release-build-only base; packaged builds set `/app/`. |

Windows uses `;` between roots and POSIX uses `:`. Example shape:
`team=PATH_TO_TEAM;sample=PATH_TO_SAMPLE`. Choose non-sensitive aliases; display
names derive from them. Restart after changes.

Packaged operation does not infer an authorized project from the current working
directory. With no `CODESTRUCT_AUTHORIZED_ROOTS`, project discovery is empty.
