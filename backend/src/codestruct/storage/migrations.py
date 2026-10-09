from __future__ import annotations

import sqlite3

from .errors import UnsupportedSchemaError
from .schema import DDL, SCHEMA_VERSION


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_metadata'"
        ).fetchone()
        if not exists:
            for statement in DDL.split(";"):
                if statement.strip():
                    connection.execute(statement)
            connection.execute("DELETE FROM schema_metadata")
            connection.execute(
                "INSERT INTO schema_metadata(version) VALUES (?)", (SCHEMA_VERSION,)
            )
        else:
            version = connection.execute(
                "SELECT version FROM schema_metadata"
            ).fetchone()
            if version is None:
                raise UnsupportedSchemaError("database schema metadata is missing")
            if version[0] > SCHEMA_VERSION:
                raise UnsupportedSchemaError(
                    "database schema is newer than this application"
                )
            if version[0] == 1:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS expired_jobs(analysis_id TEXT PRIMARY KEY, forget_after_epoch REAL NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS runtime_sessions(session_id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, target_file TEXT NOT NULL, entry_function TEXT, status TEXT NOT NULL, total_calls INTEGER NOT NULL, execution_time_seconds REAL NOT NULL, overhead_seconds REAL NOT NULL, covered_nodes INTEGER NOT NULL, total_nodes INTEGER NOT NULL, coverage_percent REAL NOT NULL, trace_events_count INTEGER NOT NULL, created_at TEXT NOT NULL, error_message TEXT)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_runtime_analysis ON runtime_sessions(analysis_id)"
                )
                connection.execute(
                    "UPDATE schema_metadata SET version=?", (SCHEMA_VERSION,)
                )
            elif version[0] == 2:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS runtime_sessions(session_id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, target_file TEXT NOT NULL, entry_function TEXT, status TEXT NOT NULL, total_calls INTEGER NOT NULL, execution_time_seconds REAL NOT NULL, overhead_seconds REAL NOT NULL, covered_nodes INTEGER NOT NULL, total_nodes INTEGER NOT NULL, coverage_percent REAL NOT NULL, trace_events_count INTEGER NOT NULL, created_at TEXT NOT NULL, error_message TEXT)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_runtime_analysis ON runtime_sessions(analysis_id)"
                )
                connection.execute(
                    "UPDATE schema_metadata SET version=?", (SCHEMA_VERSION,)
                )
            elif version[0] < SCHEMA_VERSION:
                raise UnsupportedSchemaError("no supported migration path exists")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
