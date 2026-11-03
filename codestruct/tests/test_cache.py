"""Phase 14 — Persistent/Incremental Caching tests.

Validates:
- Second consecutive analyze of unchanged project is full cache hit.
- force_refresh=True bypasses cache.
- Modifying one file in multi-file fixture causes exactly 1 cache miss and 1 cache hit,
  while cross-file edges still resolve correctly.
- Deleting a file removes its nodes and drops its cache entry.
"""

import shutil
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
CODESTRUCT_DIR = TESTS_DIR.parent
if str(CODESTRUCT_DIR) not in sys.path:
    sys.path.insert(0, str(CODESTRUCT_DIR))

from backend.analyzer import analyze_project
from backend.cache import load_cache

SAMPLE = CODESTRUCT_DIR / "sample_project"
CACHE_FIXTURES = TESTS_DIR / "cache_fixtures"


def test_cache_hit_second_run():
    """Consecutive analyze on unchanged project produces cache hit with identical counts."""
    r1 = analyze_project(str(SAMPLE))
    r2 = analyze_project(str(SAMPLE))
    assert r2["summary"]["cache_hits"] == 1
    assert r2["summary"]["cache_misses"] == 0
    assert r2["summary"]["node_count"] == 16
    assert r2["summary"]["edge_count"] == r1["summary"]["edge_count"]


def test_force_refresh_bypasses():
    """force_refresh=True forces cache misses across all files."""
    # Prime cache first
    analyze_project(str(SAMPLE))
    r = analyze_project(str(SAMPLE), force_refresh=True)
    assert r["summary"]["cache_hits"] == 0
    assert r["summary"]["cache_misses"] == 1


def test_cache_invalidation_on_file_modification(tmp_path):
    """Modifying exactly one file in a multi-file fixture causes 1 hit and 1 miss,
    with cross-file edges still correctly resolved."""
    fixture_dir = tmp_path / "project"
    shutil.copytree(CACHE_FIXTURES, fixture_dir)

    # Initial analysis: both files should be cache misses
    res1 = analyze_project(str(fixture_dir), force_refresh=True)
    assert res1["summary"]["cache_misses"] == 2
    assert res1["summary"]["cache_hits"] == 0

    # Verify initial cross-file edges
    constructs_edges = [e for e in res1["edges"] if e["type"] == "constructs"]
    assert any("DatabaseService" in e["target"] for e in constructs_edges), (
        f"Expected cross-file constructs edge to DatabaseService, got: {res1['edges']}"
    )

    # Modify ONLY client.py (append a new helper method)
    time.sleep(0.05)  # Ensure distinct filesystem timestamp
    client_file = fixture_dir / "client.py"
    original_content = client_file.read_text(encoding="utf-8")
    client_file.write_text(original_content + "\n    def get_status(self):\n        return 'ready'\n", encoding="utf-8")

    # Re-analyze: client.py must miss, service.py must hit
    res2 = analyze_project(str(fixture_dir))
    assert res2["summary"]["cache_hits"] == 1, (
        f"Expected service.py to hit cache (hits=1), got: {res2['summary']}"
    )
    assert res2["summary"]["cache_misses"] == 1, (
        f"Expected client.py to miss cache (misses=1), got: {res2['summary']}"
    )

    # Verify cross-file edges are still completely resolved after partial cache hit
    merged_constructs = [e for e in res2["edges"] if e["type"] == "constructs"]
    merged_calls = [e for e in res2["edges"] if e["type"] == "calls"]

    assert any(
        "ApiClient.initialize" in e["source"] and "DatabaseService" in e["target"]
        for e in merged_constructs
    ), f"Cross-file constructs edge missing after partial cache hit: {merged_constructs}"

    assert any(
        "ApiClient.initialize" in e["source"] and "DatabaseService.connect" in e["target"]
        for e in merged_calls
    ), f"Cross-file calls edge missing after partial cache hit: {merged_calls}"


def test_cache_invalidation_on_file_deletion(tmp_path):
    """Deleting a file removes its nodes and purges its entry from the cache file."""
    fixture_dir = tmp_path / "project"
    shutil.copytree(CACHE_FIXTURES, fixture_dir)

    # Initial analysis
    res1 = analyze_project(str(fixture_dir), force_refresh=True)
    assert any("ApiClient" in n["name"] for n in res1["nodes"])
    assert any("DatabaseService" in n["name"] for n in res1["nodes"])

    # Check cache file on disk
    cache_before = load_cache(str(fixture_dir))
    assert "client.py" in cache_before
    assert "service.py" in cache_before

    # Delete client.py
    (fixture_dir / "client.py").unlink()

    # Re-analyze
    res2 = analyze_project(str(fixture_dir))

    # Assert client.py nodes are gone
    assert not any("ApiClient" in n["name"] for n in res2["nodes"]), (
        f"Deleted client.py nodes still present in graph: {res2['nodes']}"
    )
    assert any("DatabaseService" in n["name"] for n in res2["nodes"])

    # Assert cache entry for client.py was dropped from the persistent cache
    cache_after = load_cache(str(fixture_dir))
    assert "client.py" not in cache_after, (
        f"Deleted file cache entry was not purged: {cache_after.keys()}"
    )
    assert "service.py" in cache_after
