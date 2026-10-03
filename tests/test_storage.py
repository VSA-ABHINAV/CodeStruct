from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from codestruct.analysis import AnalysisPolicy, parse_project
from codestruct.api.pagination import decode_cursor, slice_graph
from codestruct.graph import build_graph, graph_to_dict
from codestruct.jobs.models import JobRecord, JobState
from codestruct.storage import SQLiteRepository
from codestruct.storage.cache_keys import (
    cache_key,
    policy_fingerprint,
    project_fingerprint,
)
from codestruct.storage.errors import CorruptCacheEntryError, UnsupportedSchemaError
from codestruct.storage.schema import DDL
from codestruct.storage.schema import SCHEMA_VERSION as DATABASE_SCHEMA_VERSION

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"
OUTPUT = REPOSITORY / "tests" / "test-output"


class StorageTests(unittest.TestCase):
    def setUp(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=OUTPUT)
        self.path = Path(self.temp.name) / "test.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def graph(self):
        policy = AnalysisPolicy(authorized_roots=(SAMPLE,))
        return graph_to_dict(build_graph(parse_project(SAMPLE, policy)))

    def test_creation_persistence_recovery_and_future_schema(self):
        repository = SQLiteRepository(self.path, 60)
        repository.add(
            JobRecord("queued", "sample", str(SAMPLE), state=JobState.QUEUED)
        )
        reopened = SQLiteRepository(self.path, 60)
        recovered = reopened.get("queued")
        self.assertEqual(recovered.state, JobState.FAILED)
        self.assertEqual(recovered.error_code, "PROCESS_RESTARTED")
        future = Path(self.temp.name) / "future.sqlite3"
        with closing(sqlite3.connect(future)) as connection:
            connection.execute("CREATE TABLE schema_metadata(version INTEGER NOT NULL)")
            connection.execute("INSERT INTO schema_metadata VALUES (999)")
            connection.commit()
        with self.assertRaises(UnsupportedSchemaError):
            SQLiteRepository(future, 60)
        legacy = Path(self.temp.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy)) as connection:
            connection.executescript(DDL)
            connection.execute("INSERT INTO schema_metadata VALUES (1)")
            connection.commit()
        SQLiteRepository(legacy, 60)
        with closing(sqlite3.connect(legacy)) as connection:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                DATABASE_SCHEMA_VERSION,
            )

    def test_cache_integrity_expiry_and_eviction(self):
        repository = SQLiteRepository(self.path, 60)
        graph = self.graph()
        repository.store_cache("key", graph, "policy", "project")
        self.assertEqual(repository.find_cache("key").graph, graph)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "UPDATE cache_results SET graph_json='{}' WHERE cache_key='key'"
            )
            connection.commit()
        with self.assertRaises(CorruptCacheEntryError):
            repository.find_cache("key")
        repository.store_cache("a", graph, "p", "a")
        repository.store_cache("b", graph, "p", "b")
        self.assertEqual(repository.evict(1, 10**9), 2)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "UPDATE cache_results SET expires_at_epoch=?", (time.time() - 1,)
            )
            connection.commit()
        repository.cleanup_expired()
        self.assertIsNone(repository.find_cache("b"))

    def test_content_policy_and_path_changes_invalidate_keys(self):
        root = Path(self.temp.name) / "project"
        root.mkdir()
        source = root / "one.py"
        source.write_text("import os\n", encoding="utf-8")
        policy = AnalysisPolicy(authorized_roots=(root,))
        first_hash = project_fingerprint(root, policy)
        first = cache_key("root", ".", first_hash, policy_fingerprint(policy))
        source.write_text("import sys\n", encoding="utf-8")
        changed = cache_key(
            "root", ".", project_fingerprint(root, policy), policy_fingerprint(policy)
        )
        self.assertNotEqual(first, changed)
        (root / "two.py").write_text("VALUE = 1\n", encoding="utf-8")
        added = project_fingerprint(root, policy)
        self.assertNotEqual(first_hash, added)
        source.unlink()
        removed = project_fingerprint(root, policy)
        self.assertNotEqual(added, removed)
        stricter = AnalysisPolicy(authorized_roots=(root,), max_depth=2)
        self.assertNotEqual(policy_fingerprint(policy), policy_fingerprint(stricter))

    def test_deterministic_pagination_and_cursor_rejection(self):
        graph = self.graph()
        first = slice_graph(
            graph,
            limit=3,
            cursor=None,
            node_kind=None,
            edge_kind=None,
            resolution_status=None,
        )
        again = slice_graph(
            graph,
            limit=3,
            cursor=None,
            node_kind=None,
            edge_kind=None,
            resolution_status=None,
        )
        self.assertEqual(first, again)
        self.assertTrue(first["page"]["partial_load"])
        second = slice_graph(
            graph,
            limit=3,
            cursor=first["page"]["next_cursor"],
            node_kind=None,
            edge_kind=None,
            resolution_status=None,
        )
        self.assertFalse(
            {n["id"] for n in first["nodes"]} == {n["id"] for n in second["nodes"]}
        )
        with self.assertRaises(ValueError):
            decode_cursor(
                first["page"]["next_cursor"] + "x",
                graph["metadata"]["graph_id"],
                {
                    "node_kind": None,
                    "edge_kind": None,
                    "resolution_status": None,
                    "limit": 3,
                },
            )
        node_ids = {item["id"] for item in first["nodes"]}
        self.assertTrue(
            all(
                edge["source_id"] in node_ids
                and (edge["target_id"] is None or edge["target_id"] in node_ids)
                for edge in first["edges"]
            )
        )


if __name__ == "__main__":
    unittest.main()
