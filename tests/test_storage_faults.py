"""Tests for storage faults, failure behavior, corruption recovery, and restart lifecycle (CS-021).

Verifies:
1. Unavailable / unwritable database paths and HTTP 503 STORAGE_UNAVAILABLE response.
2. Transaction failure and automatic rollback guarantees.
3. Corrupt or incompatible persisted state handling in SQLiteRepository and PersistentFileParseCache.
4. Restart recovery for active jobs vs preservation of completed analyses.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from codestruct.analysis import AnalysisPolicy, parse_project
from codestruct.api.app import create_app
from codestruct.graph import build_graph, graph_to_dict
from codestruct.jobs.models import JobRecord, JobState
from codestruct.jobs.service import AnalysisService
from codestruct.settings import Settings
from codestruct.storage import SQLiteRepository
from codestruct.storage.errors import (
    CorruptCacheEntryError,
    StorageError,
    UnsupportedSchemaError,
)
from codestruct.storage.file_cache import (
    PARSER_VERSION,
    PersistentFileParseCache,
    compute_file_cache_key,
    compute_parse_policy_fingerprint,
)
from fastapi.testclient import TestClient


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_graph(temp_dir: Path) -> dict:
    sample_file = temp_dir / "sample.py"
    sample_file.write_text("def hello(): return 'world'\n", encoding="utf-8")
    policy = AnalysisPolicy(authorized_roots=(temp_dir,))
    parsed = parse_project(temp_dir, policy)
    graph = build_graph(parsed)
    return graph_to_dict(graph)


# ==============================================================================
# 1. Unavailable and Unwritable Database Faults
# ==============================================================================


@pytest.mark.unit
def test_unwritable_database_path_raises_operational_error(temp_dir: Path) -> None:
    # Pointing to an existing directory instead of a file causes SQLite to fail to open/create
    unwritable_path = temp_dir / "existing_dir"
    unwritable_path.mkdir()

    with pytest.raises((sqlite3.OperationalError, StorageError)):
        SQLiteRepository(unwritable_path, retention_seconds=60)


@pytest.mark.unit
def test_api_returns_503_on_storage_unavailable(temp_dir: Path) -> None:
    # Configure app with a database path inside an unwritable location
    settings = Settings(
        database_path=temp_dir / "unreachable" / "sub" / "db.sqlite3",
        authorized_roots=(temp_dir,),
    )
    # Intentionally corrupt or break the repository to simulate runtime storage loss
    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)

    # Force a storage failure on the service registry
    class FailingRepo:
        def cleanup_expired(self, *args, **kwargs):
            raise sqlite3.OperationalError("disk I/O error / disk full")

        def list(self, *args, **kwargs):
            raise sqlite3.OperationalError("disk I/O error / disk full")

        def get(self, *args, **kwargs):
            raise sqlite3.OperationalError("disk I/O error / disk full")

    app.state.analysis_service.registry = FailingRepo()

    resp = client.get("/api/v1/analyses/any_id")
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert data["error"]["recoverable"] is True
    assert data["error"]["retry_after_seconds"] == 1


# ==============================================================================
# 2. Transaction Failure and Rollback Safety
# ==============================================================================


@pytest.mark.unit
def test_transaction_rollback_on_failure(temp_dir: Path) -> None:
    db_path = temp_dir / "rollback_test.sqlite3"
    repo = SQLiteRepository(db_path, retention_seconds=60)

    # Record initially added
    initial_job = JobRecord("job_1", "root_1", str(temp_dir), state=JobState.QUEUED)
    repo.add(initial_job)

    # Verify initial state
    assert repo.get("job_1").state == JobState.QUEUED

    # Attempt an update that fails midway inside _connect
    with pytest.raises(RuntimeError, match="Simulated mid-transaction crash"):
        with repo._connect() as conn:
            conn.execute(
                "UPDATE jobs SET state = ? WHERE analysis_id = ?",
                (JobState.SCANNING.value, "job_1"),
            )
            # Raise before commit to trigger rollback
            raise RuntimeError("Simulated mid-transaction crash")

    # Verify rollback: state must remain QUEUED
    assert repo.get("job_1").state == JobState.QUEUED


@pytest.mark.unit
def test_file_cache_rollback_on_failed_put(temp_dir: Path) -> None:
    db_path = temp_dir / "file_cache_fault.sqlite3"
    cache = PersistentFileParseCache(db_path=db_path)

    # Create dummy source and policy
    source_file = temp_dir / "mod.py"
    source_file.write_text("x = 1\n", encoding="utf-8")
    policy = AnalysisPolicy(authorized_roots=(temp_dir,))
    parsed = parse_project(temp_dir, policy)
    result = parsed.files[0]

    # Pre-populate cache
    cache.put(temp_dir, "mod.py", "hash123", policy, result)
    assert cache.get(temp_dir, "mod.py", "hash123", policy) is not None

    # Simulate put failure midway through transaction
    orig_evict = cache._evict_if_needed

    def faulty_evict(*args, **kwargs):
        raise sqlite3.OperationalError("Simulated disk full during eviction")

    cache._evict_if_needed = faulty_evict
    try:
        # put() should catch the exception and log, without leaving inconsistent state
        cache.put(temp_dir, "mod.py", "hash456", policy, result)
    finally:
        cache._evict_if_needed = orig_evict

    # Original entry should still be accessible and valid
    assert cache.get(temp_dir, "mod.py", "hash123", policy) is not None


# ==============================================================================
# 3. Corrupt or Incompatible Persisted State Recovery
# ==============================================================================


@pytest.mark.unit
def test_corrupt_graph_json_in_cache_invalidates_and_raises(
    temp_dir: Path, sample_graph: dict
) -> None:
    db_path = temp_dir / "corrupt_cache.sqlite3"
    repo = SQLiteRepository(db_path, retention_seconds=60)
    repo.store_cache("key_corrupt", sample_graph, "pol_hash", "proj_hash")

    # Manually corrupt the stored graph JSON
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE cache_results SET graph_json = 'INVALID_JSON_GARBAGE' WHERE cache_key = 'key_corrupt'"
        )
        conn.commit()

    # Accessing the corrupted entry must raise CorruptCacheEntryError and invalidate row
    with pytest.raises(CorruptCacheEntryError):
        repo.find_cache("key_corrupt")

    # Second check: entry should now be marked invalid=1
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT invalid FROM cache_results WHERE cache_key = 'key_corrupt'"
        ).fetchone()
        assert row[0] == 1


@pytest.mark.unit
def test_file_cache_recovers_from_corrupt_entry(temp_dir: Path) -> None:
    db_path = temp_dir / "corrupt_file_cache.sqlite3"
    cache = PersistentFileParseCache(db_path=db_path)

    source_file = temp_dir / "mod_corrupt.py"
    source_file.write_text("y = 2\n", encoding="utf-8")
    policy = AnalysisPolicy(authorized_roots=(temp_dir,))
    parsed = parse_project(temp_dir, policy)
    result = parsed.files[0]

    cache.put(temp_dir, "mod_corrupt.py", "hash_c", policy, result)

    # Corrupt the payload in SQLite
    root_id = str(temp_dir.resolve()).lower()
    pol_fp = compute_parse_policy_fingerprint(policy)
    key = compute_file_cache_key(
        root_id, "mod_corrupt.py", "hash_c", PARSER_VERSION, pol_fp
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE file_parse_cache SET result_json = '{\"broken\": true}' WHERE cache_key = ?",
            (key,),
        )
        conn.commit()

    # get() must handle corruption gracefully: evict corrupted row and return None (cache miss)
    recovered = cache.get(temp_dir, "mod_corrupt.py", "hash_c", policy)
    assert recovered is None

    # Corrupted entry was deleted
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM file_parse_cache WHERE cache_key = ?", (key,)
        ).fetchone()[0]
        assert count == 0


@pytest.mark.unit
def test_unsupported_future_schema_raises_error(temp_dir: Path) -> None:
    future_db = temp_dir / "future_schema.sqlite3"
    with sqlite3.connect(future_db) as conn:
        conn.execute("CREATE TABLE schema_metadata(version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_metadata VALUES (9999)")
        conn.commit()

    with pytest.raises(UnsupportedSchemaError):
        SQLiteRepository(future_db, retention_seconds=60)


@pytest.mark.unit
def test_malformed_sqlite_disk_image_raises_storage_error(temp_dir: Path) -> None:
    bad_db = temp_dir / "malformed.sqlite3"
    bad_db.write_text("THIS IS NOT A VALID SQLITE DATABASE FILE", encoding="utf-8")

    with pytest.raises((sqlite3.DatabaseError, StorageError)):
        SQLiteRepository(bad_db, retention_seconds=60)


# ==============================================================================
# 4. Service Restart and Recovery Behavior
# ==============================================================================


@pytest.mark.unit
def test_restart_recovery_marks_interrupted_jobs_failed(temp_dir: Path) -> None:
    db_path = temp_dir / "recovery_test.sqlite3"
    repo1 = SQLiteRepository(db_path, retention_seconds=300)

    # Insert an active running job and a completed job
    running_job = JobRecord(
        analysis_id="job_interrupted",
        root_id="root_1",
        project_root=str(temp_dir),
        state=JobState.SCANNING,
        percent=45,
    )
    completed_job = JobRecord(
        analysis_id="job_completed",
        root_id="root_1",
        project_root=str(temp_dir),
        state=JobState.COMPLETED,
        percent=100,
        completed_at="2026-10-21T12:00:00Z",
    )
    repo1.add(running_job)
    repo1.add(completed_job)

    # Simulate restart by instantiating new SQLiteRepository on same database
    repo2 = SQLiteRepository(db_path, retention_seconds=300)

    # Interrupted job must be transitioned to FAILED with PROCESS_RESTARTED error
    recovered_interrupted = repo2.get("job_interrupted")
    assert recovered_interrupted.state == JobState.FAILED
    assert recovered_interrupted.error_code == "PROCESS_RESTARTED"
    assert (
        "interrupted by an application restart" in recovered_interrupted.error_message
    )

    # Completed job must remain untouched in COMPLETED state
    recovered_completed = repo2.get("job_completed")
    assert recovered_completed.state == JobState.COMPLETED
    assert recovered_completed.percent == 100
    assert recovered_completed.completed_at == "2026-10-21T12:00:00Z"


@pytest.mark.integration
def test_analysis_service_restart_lifecycle(temp_dir: Path) -> None:
    db_path = temp_dir / "service_lifecycle.sqlite3"
    settings = Settings(
        database_path=db_path,
        authorized_roots=(temp_dir,),
        result_retention_seconds=300,
    )

    # 1. Start initial service instance
    service1 = AnalysisService(settings)
    job_rec = JobRecord(
        analysis_id="service_job_1",
        root_id="root_svc",
        project_root=str(temp_dir),
        state=JobState.SCANNING,
        percent=20,
    )
    service1.registry.add(job_rec)
    service1.shutdown()

    # 2. Restart service instance (simulating daemon restart)
    service2 = AnalysisService(settings)
    recovered = service2.registry.get("service_job_1")
    assert recovered is not None
    assert recovered.state == JobState.FAILED
    assert recovered.error_code == "PROCESS_RESTARTED"
    service2.shutdown()
