# Development troubleshooting

- **Install:** confirm supported versions, activate `.venv`, install `.[dev]`, and run `npm --prefix frontend ci`.
- **No projects:** configure unique aliases to existing directories and restart the API; public responses deliberately hide paths.
- **Worker startup:** use the documented importable entry point. On Windows do not launch spawn tests through `python -c`.
- **Connection:** confirm API listener, Vite proxy/base URL, and exact CORS origin. Non-JSON 5xx proxy failures appear as backend unavailable.
- **SQLite:** stop writers, check permission/free space, and back up before recovery. Never damage the normal database in tests.
- **Cache:** Refresh bypasses reuse; content/policy/analyzer/schema changes invalidate automatically.
- **Large graph:** initial retrieval is bounded. Use Load more, filters, overview, or Table; restart from page one after a cursor error.
- **Cleanup:** stop services/workers, then resolve and delete only the configured ignored runtime/test-output path.
- **Editor capability vs. UNAUTHORIZED_ROOT:** Files opened in an external editor outside `CODESTRUCT_AUTHORIZED_ROOTS` are analyzed via temporary `cap_*` capabilities. The backend authorizes only the target file's containing folder in the per-job `AnalysisPolicy` while pinning `single_file_name` to the exact file. If `UNAUTHORIZED_ROOT` appears, verify that the capability token was passed to `POST /api/v1/analyses` and that the per-job policy includes the resolved directory in `policy.authorized_roots`.

