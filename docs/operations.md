# Local operations

For an installed artifact, run `codestruct doctor` before `codestruct serve`.
The latter is working-directory independent, binds `127.0.0.1:8000` by default,
does not enable reload, and serves the bundled UI at `/app/`. A non-loopback bind
prints a security warning; it is not authorization to expose this unauthenticated
MVP publicly. See [deployment](release/deployment.md),
[upgrading](release/upgrading.md), and [rollback](release/rollback.md).

Start with [development setup](development/setup.md). `GET /` is legacy liveness;
`GET /api/v1/projects` verifies API/configuration readiness. Stop with Ctrl+C and
wait for application shutdown; confirm workers and listeners exit before maintenance.

SQLite uses foreign keys, busy timeout, WAL, and parent-owned per-operation
connections. Stop CodeStruct before backup. Migrations are transactional and
reject future schemas. For corruption, preserve the file and start a separately
configured database only with operator approval; never silently delete data.

Cache keys include authorized identity, content, policy, analyzer/resolver/schema.
Retention bounds time/count/bytes and excludes active work. Refresh bypasses reuse.
Recovered nonterminal jobs become interrupted/failed, never complete.

Use safe error codes and structured events for diagnosis; normal logs exclude
source, secrets, canonical roots, SQL, and tracebacks. Locked/read-only/full
storage is 503, saturation 429, expired retrieval 410, and worker/timeout failures
become terminal. Large graphs start bounded and continue by validated cursor.
Cleanup only exact verified ignored runtime/test-output paths after shutdown.
