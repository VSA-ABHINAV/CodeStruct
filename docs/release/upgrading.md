# Upgrade procedure

1. Stop CodeStruct cleanly and confirm no worker remains.
2. Copy the SQLite database and its WAL/SHM state consistently while stopped; record the candidate and prior artifact checksums.
3. Preserve authorized-project and origin configuration separately.
4. Install the candidate wheel in a new environment; do not overwrite the prior environment.
5. Run `codestruct doctor`. Startup applies supported forward migrations transactionally and refuses future/unsupported schemas.
6. Start on loopback and verify liveness, readiness, version, project discovery, one cold analysis, bounded graph retrieval, then a warm cache hit.
7. Retain the backup until the acceptance window closes.

Graph, analyzer, resolver, policy, and cache-format versions participate in cache keys; incompatible cache entries are not successful hits. Source projects are never migration targets and must never be deleted. Reverse migrations are not implemented.
