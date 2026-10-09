SCHEMA_VERSION = 3

DDL = """
CREATE TABLE IF NOT EXISTS schema_metadata(version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(
 analysis_id TEXT PRIMARY KEY, root_id TEXT NOT NULL, project_identity TEXT NOT NULL,
 state TEXT NOT NULL, percent INTEGER, message_code TEXT NOT NULL,
 created_at TEXT NOT NULL, started_at TEXT, updated_at TEXT NOT NULL, completed_at TEXT,
 revision INTEGER NOT NULL, partial INTEGER NOT NULL, graph_json TEXT, diagnostics_json TEXT NOT NULL,
 error_code TEXT, error_message TEXT, expires_at_epoch REAL, cache_hit INTEGER NOT NULL DEFAULT 0,
 cache_key TEXT
);
CREATE TABLE IF NOT EXISTS cache_results(
 cache_key TEXT PRIMARY KEY, graph_json TEXT NOT NULL, graph_sha256 TEXT NOT NULL,
 schema_version TEXT NOT NULL, analyzer_version TEXT NOT NULL, policy_fingerprint TEXT NOT NULL,
 project_fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, last_accessed_at TEXT NOT NULL,
 expires_at_epoch REAL NOT NULL, stored_size INTEGER NOT NULL, invalid INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_expiry ON jobs(expires_at_epoch);
CREATE INDEX IF NOT EXISTS idx_cache_lru ON cache_results(last_accessed_at);
CREATE TABLE IF NOT EXISTS expired_jobs(analysis_id TEXT PRIMARY KEY, forget_after_epoch REAL NOT NULL);
CREATE TABLE IF NOT EXISTS runtime_sessions(
 session_id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, target_file TEXT NOT NULL,
 entry_function TEXT, status TEXT NOT NULL, total_calls INTEGER NOT NULL,
 execution_time_seconds REAL NOT NULL, overhead_seconds REAL NOT NULL,
 covered_nodes INTEGER NOT NULL, total_nodes INTEGER NOT NULL, coverage_percent REAL NOT NULL,
 trace_events_count INTEGER NOT NULL, created_at TEXT NOT NULL, error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_runtime_analysis ON runtime_sessions(analysis_id);
"""
