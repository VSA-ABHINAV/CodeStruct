"""Tests for CS-015: Persistent per-file parse caching."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from pathlib import Path

import pytest
from codestruct.analysis.diagnostics import DiagnosticCode, DiagnosticSeverity
from codestruct.analysis.models import (
    CallKind,
    CallSiteObservation,
    ClassDefinition,
    DefinitionKind,
    FileParseResult,
    FunctionDefinition,
    ImportAlias,
    ImportKind,
    ImportStatement,
    InheritanceReference,
    ModuleMetadata,
    ParameterKind,
    ParameterMetadata,
    ParserDiagnostic,
    ResolutionStatus,
    SourceFile,
    SourceSpan,
    VariableDefinition,
)
from codestruct.analysis.policy import AnalysisPolicy
from codestruct.analysis.python_parser import PARSER_VERSION, parse_project
from codestruct.storage.errors import UnsupportedSchemaError
from codestruct.storage.file_cache import (
    PersistentFileParseCache,
    compute_file_cache_key,
    compute_parse_policy_fingerprint,
    dict_to_file_parse_result,
    file_parse_result_to_dict,
)
from codestruct.storage.migrations import migrate
from codestruct.storage.schema import SCHEMA_VERSION


def _make_dummy_source_file(
    rel_path: str = "pkg/mod.py", size: int = 100
) -> SourceFile:
    return SourceFile(
        id=f"sf_{rel_path}",
        relative_path=rel_path,
        module_name="pkg.mod",
        is_package=False,
        size_bytes=size,
        modified_ns=123456789,
    )


def test_compute_file_cache_key_invariants():
    content_a = b"def hello():\n    return 42\n"
    content_b = b"def hello():\n    return 43\n"  # Same length!
    hash_a = hashlib.sha256(content_a).hexdigest()
    hash_b = hashlib.sha256(content_b).hexdigest()

    policy_1 = compute_parse_policy_fingerprint(
        AnalysisPolicy(max_file_size=1024 * 1024)
    )
    policy_2 = compute_parse_policy_fingerprint(
        AnalysisPolicy(max_file_size=2048 * 1024)
    )

    key_1 = compute_file_cache_key(
        "root_a", "pkg/mod.py", hash_a, PARSER_VERSION, policy_1
    )
    key_2 = compute_file_cache_key(
        "root_a", "pkg/mod.py", hash_a, PARSER_VERSION, policy_1
    )
    assert key_1 == key_2  # Deterministic

    # Same file size but different content MUST produce different key
    key_diff_content = compute_file_cache_key(
        "root_a", "pkg/mod.py", hash_b, PARSER_VERSION, policy_1
    )
    assert key_1 != key_diff_content

    # Different policy fingerprint
    key_diff_policy = compute_file_cache_key(
        "root_a", "pkg/mod.py", hash_a, PARSER_VERSION, policy_2
    )
    assert key_1 != key_diff_policy

    # Different parser version
    key_diff_version = compute_file_cache_key(
        "root_a", "pkg/mod.py", hash_a, "99", policy_1
    )
    assert key_1 != key_diff_version

    # Different root identity (cross-project containment)
    key_diff_root = compute_file_cache_key(
        "root_b", "pkg/mod.py", hash_a, PARSER_VERSION, policy_1
    )
    assert key_1 != key_diff_root

    # Path normalization (relative backslashes vs forward slashes)
    key_slash = compute_file_cache_key(
        "root_a", "pkg/sub/mod.py", hash_a, PARSER_VERSION, policy_1
    )
    key_backslash = compute_file_cache_key(
        "root_a", r"pkg\sub\mod.py", hash_a, PARSER_VERSION, policy_1
    )
    assert key_slash == key_backslash


def test_file_parse_result_serialization_roundtrip():
    sf = _make_dummy_source_file("pkg/mod.py")
    span = SourceSpan(start_line=10, start_column=4, end_line=12, end_column=20)
    mod = ModuleMetadata(
        id="mod_1",
        name="mod",
        qualified_name="pkg.mod",
        source_file_id=sf.id,
        relative_path="pkg/mod.py",
        is_package=False,
        has_docstring=True,
        span=span,
    )
    cls = ClassDefinition(
        id="cls_1",
        name="Worker",
        qualified_name="pkg.mod.Worker",
        enclosing_scope_id=mod.id,
        span=span,
        has_docstring=True,
    )
    func = FunctionDefinition(
        id="fn_1",
        name="run",
        qualified_name="pkg.mod.Worker.run",
        kind=DefinitionKind.METHOD,
        enclosing_scope_id=cls.id,
        span=span,
        parameters=(
            ParameterMetadata(
                id="param_1",
                name="self",
                kind=ParameterKind.POSITIONAL_OR_KEYWORD,
                annotation=None,
                has_default=False,
                span=span,
            ),
        ),
        return_annotation="int",
        has_docstring=False,
    )
    var = VariableDefinition(
        id="var_1",
        name="RETRIES",
        qualified_name="pkg.mod.RETRIES",
        enclosing_scope_id=mod.id,
        span=span,
        type_annotation="int",
        value_expression="3",
        is_constant=True,
    )
    imp = ImportStatement(
        id="imp_1",
        kind=ImportKind.FROM_IMPORT,
        module="os",
        relative_level=0,
        names=(ImportAlias(name="path", alias="os_path"),),
        enclosing_scope_id=mod.id,
        span=span,
    )
    inh = InheritanceReference(
        id="inh_1",
        class_id=cls.id,
        expression="BaseWorker",
        expression_kind="Name",
        status=ResolutionStatus.SYNTACTIC_UNRESOLVED,
        span=span,
    )
    call = CallSiteObservation(
        id="call_1",
        expression="self.step()",
        kind=CallKind.ATTRIBUTE,
        enclosing_scope_id=func.id,
        enclosing_qualified_name=func.qualified_name,
        status=ResolutionStatus.SYNTACTIC_UNRESOLVED,
        span=span,
    )
    diag = ParserDiagnostic(
        id="diag_1",
        code=DiagnosticCode.FILE_SYNTAX_ERROR,
        severity=DiagnosticSeverity.WARNING,
        message="Minor parse warning",
        relative_path="pkg/mod.py",
        span=span,
    )
    result = FileParseResult(
        source_file=sf,
        module=mod,
        classes=(cls,),
        functions=(func,),
        variables=(var,),
        imports=(imp,),
        inheritance=(inh,),
        calls=(call,),
        diagnostics=(diag,),
        encoding="utf-8",
        parsed=True,
    )

    d = file_parse_result_to_dict(result)
    restored = dict_to_file_parse_result(d)

    assert restored.source_file.id == sf.id
    assert restored.source_file.relative_path == sf.relative_path
    assert restored.module is not None
    assert restored.module.qualified_name == "pkg.mod"
    assert len(restored.classes) == 1
    assert restored.classes[0].name == "Worker"
    assert len(restored.functions) == 1
    assert restored.functions[0].name == "run"
    assert restored.functions[0].parameters[0].name == "self"
    assert len(restored.variables) == 1
    assert restored.variables[0].name == "RETRIES"
    assert len(restored.imports) == 1
    assert restored.imports[0].names[0].alias == "os_path"
    assert len(restored.inheritance) == 1
    assert restored.inheritance[0].expression == "BaseWorker"
    assert len(restored.calls) == 1
    assert restored.calls[0].expression == "self.step()"
    assert len(restored.diagnostics) == 1
    assert restored.diagnostics[0].code == DiagnosticCode.FILE_SYNTAX_ERROR
    assert restored.parsed is True


def test_file_cache_put_get_and_stats(tmp_path: Path):
    db_path = tmp_path / "cache.db"
    cache = PersistentFileParseCache(db_path, max_entries=100)
    root = tmp_path / "my_project"
    root.mkdir()

    policy = AnalysisPolicy(max_file_size=1024 * 1024)
    content = b"print('hello')\n"
    content_hash = hashlib.sha256(content).hexdigest()

    # Initial get -> miss
    res = cache.get(root, "main.py", content_hash, policy)
    assert res is None
    init_stats = cache.stats()
    assert init_stats["hits"] == 0
    assert init_stats["misses"] == 1
    assert init_stats["entries"] == 0
    assert init_stats["total_bytes"] == 0

    # Store entry
    sf = _make_dummy_source_file("main.py", len(content))
    to_store = FileParseResult(
        source_file=sf,
        module=None,
        classes=(),
        functions=(),
        variables=(),
        imports=(),
        inheritance=(),
        calls=(),
        diagnostics=(),
        encoding="utf-8",
        parsed=True,
    )
    cache.put(root, "main.py", content_hash, policy, to_store)

    # Get entry -> hit
    hit_res = cache.get(root, "main.py", content_hash, policy)
    assert hit_res is not None
    assert hit_res.source_file.relative_path == "main.py"
    assert hit_res.parsed is True
    assert cache.stats()["hits"] == 1
    assert cache.stats()["entries"] == 1
    assert cache.stats()["total_bytes"] > 0


def test_file_cache_lru_eviction(tmp_path: Path):
    db_path = tmp_path / "cache.db"
    # Limit cache to 3 entries
    cache = PersistentFileParseCache(db_path, max_entries=3)
    root = tmp_path / "proj"
    root.mkdir()
    policy = AnalysisPolicy(max_file_size=1024 * 1024)

    for i in range(5):
        content = f"content_{i}".encode("utf-8")
        h = hashlib.sha256(content).hexdigest()
        sf = _make_dummy_source_file(f"file_{i}.py", len(content))
        cache.put(
            root,
            f"file_{i}.py",
            h,
            policy,
            FileParseResult(sf, None, parsed=True),
        )
        time.sleep(0.01)

    # Should have evicted older entries down to max_entries (3)
    st = cache.stats()
    assert st["entries"] <= 3

    # file_0 and file_1 were added earliest, should be evicted
    h0 = hashlib.sha256(b"content_0").hexdigest()
    assert cache.get(root, "file_0.py", h0, policy) is None

    # file_4 was added last, should still be present
    h4 = hashlib.sha256(b"content_4").hexdigest()
    assert cache.get(root, "file_4.py", h4, policy) is not None


def test_file_cache_direct_probe_byte_pressure_eviction(tmp_path: Path):
    """Direct regression for Codex review probe:

    Ten existing 10-byte entries under a 100-byte budget followed by an 80-byte entry;
    the resulting stored total must not exceed 100 bytes.
    """
    db_path = tmp_path / "cache.db"
    cache = PersistentFileParseCache(db_path, max_entries=100, max_bytes=100)

    # Populate 10 rows of 10 bytes directly into file_parse_cache
    with cache._get_connection() as conn:
        for i in range(10):
            conn.execute(
                """
                INSERT INTO file_parse_cache(
                    cache_key, root_identity, relative_path, content_sha256,
                    parser_version, policy_fingerprint, result_json,
                    stored_size, created_at, last_accessed_at
                ) VALUES (?, 'root', ?, 'hash', '2', 'fp', '{}', 10, '2026-10-14T00:00:00Z', ?)
                """,
                (f"k_{i}", f"f_{i}.py", float(i)),
            )
        conn.commit()

        st_before = cache.stats()
        assert st_before["entries"] == 10
        assert st_before["total_bytes"] == 100

        # Now simulate inserting an 80-byte entry using _evict_if_needed
        conn.execute("BEGIN IMMEDIATE")
        cache._evict_if_needed(conn, incoming_size=80)
        conn.execute(
            """
            INSERT INTO file_parse_cache(
                cache_key, root_identity, relative_path, content_sha256,
                parser_version, policy_fingerprint, result_json,
                stored_size, created_at, last_accessed_at
            ) VALUES ('k_new', 'root', 'f_new.py', 'hash', '2', 'fp', '{}', 80, '2026-10-14T00:00:00Z', 100.0)
            """
        )
        conn.commit()

    st_after = cache.stats()
    assert st_after["total_bytes"] <= 100
    assert st_after["entries"] <= 100
    # Specifically, 8 entries of 10 bytes were evicted, 2 entries of 10 bytes + 1 entry of 80 bytes = 100 bytes
    assert st_after["entries"] == 3
    assert st_after["total_bytes"] == 100


def test_file_cache_byte_pressure_via_put(tmp_path: Path):
    """Verify byte-cap enforcement through high-level cache.put."""
    db_path = tmp_path / "cache.db"
    # Small byte budget: 1000 bytes, allows ~3 entries of ~280 bytes
    cache = PersistentFileParseCache(db_path, max_entries=50, max_bytes=1000)
    root = tmp_path / "proj"
    root.mkdir()
    policy = AnalysisPolicy(max_file_size=1024 * 1024)

    for i in range(10):
        content = f"content_{i}".encode("utf-8")
        h = hashlib.sha256(content).hexdigest()
        sf = _make_dummy_source_file(f"file_{i}.py", len(content))
        cache.put(
            root,
            f"file_{i}.py",
            h,
            policy,
            FileParseResult(sf, None, parsed=True),
        )
        st = cache.stats()
        assert st["total_bytes"] <= 1000, (
            f"Exceeded byte budget after insert {i}: {st['total_bytes']}"
        )
        assert st["entries"] <= 50

    st_final = cache.stats()
    assert st_final["total_bytes"] <= 1000
    assert st_final["entries"] <= 3


def test_file_cache_simultaneous_count_and_byte_pressure(tmp_path: Path):
    """Verify eviction satisfies BOTH count and byte budgets simultaneously."""
    db_path = tmp_path / "cache.db"
    # Constrain both: max 2 entries, max 800 bytes
    cache = PersistentFileParseCache(db_path, max_entries=2, max_bytes=800)
    root = tmp_path / "proj"
    root.mkdir()
    policy = AnalysisPolicy(max_file_size=1024 * 1024)

    for i in range(8):
        content = f"content_{i}".encode("utf-8")
        h = hashlib.sha256(content).hexdigest()
        sf = _make_dummy_source_file(f"file_{i}.py", len(content))
        cache.put(
            root,
            f"file_{i}.py",
            h,
            policy,
            FileParseResult(sf, None, parsed=True),
        )
        st = cache.stats()
        assert st["entries"] <= 2, f"Count exceeded: {st['entries']}"
        assert st["total_bytes"] <= 800, f"Byte cap exceeded: {st['total_bytes']}"


def test_file_cache_oversized_entry_skipped(tmp_path: Path):
    """Verify that an entry larger than the configured byte budget is skipped entirely."""
    db_path = tmp_path / "cache.db"
    cache = PersistentFileParseCache(db_path, max_entries=10, max_bytes=400)
    root = tmp_path / "proj"
    root.mkdir()
    policy = AnalysisPolicy(max_file_size=1024 * 1024)

    # Normal entry (~280 bytes) fits in 400
    c1 = b"normal"
    h1 = hashlib.sha256(c1).hexdigest()
    sf1 = _make_dummy_source_file("normal.py", len(c1))
    cache.put(root, "normal.py", h1, policy, FileParseResult(sf1, None, parsed=True))

    st1 = cache.stats()
    assert st1["entries"] == 1
    assert st1["total_bytes"] <= 400

    # Huge entry: many functions so serialized JSON > 1000 bytes > 400
    dummy_span = SourceSpan(start_line=1, start_column=0, end_line=1, end_column=10)
    huge_funcs = tuple(
        FunctionDefinition(
            id=f"fn_{j}",
            name=f"func_{j}",
            qualified_name=f"mod.func_{j}",
            kind=DefinitionKind.FUNCTION,
            enclosing_scope_id="mod",
            span=dummy_span,
        )
        for j in range(50)
    )
    sf_huge = _make_dummy_source_file("huge.py", 1000)
    huge_result = FileParseResult(
        source_file=sf_huge,
        module=None,
        functions=huge_funcs,
        parsed=True,
    )
    c_huge = b"huge"
    h_huge = hashlib.sha256(c_huge).hexdigest()

    # Attempt to put oversized entry
    cache.put(root, "huge.py", h_huge, policy, huge_result)

    # Should have been skipped without evicting normal.py
    st2 = cache.stats()
    assert st2["entries"] == 1
    assert st2["total_bytes"] == st1["total_bytes"]
    assert cache.get(root, "normal.py", h1, policy) is not None
    assert cache.get(root, "huge.py", h_huge, policy) is None


def test_file_cache_corrupt_entry_recovery(tmp_path: Path):
    db_path = tmp_path / "cache.db"
    cache = PersistentFileParseCache(db_path)
    root = tmp_path / "proj"
    root.mkdir()
    policy = AnalysisPolicy(max_file_size=1024 * 1024)
    content = b"x = 1"
    h = hashlib.sha256(content).hexdigest()

    sf = _make_dummy_source_file("corrupt.py", len(content))
    cache.put(
        root,
        "corrupt.py",
        h,
        policy,
        FileParseResult(sf, None, parsed=True),
    )

    # Deliberately corrupt the payload in SQLite
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE file_parse_cache SET result_json = 'INVALID_JSON_CORRUPT'")
        conn.commit()

    # get should gracefully catch decode error, delete record, record miss, and return None
    result = cache.get(root, "corrupt.py", h, policy)
    assert result is None
    assert cache.stats()["misses"] == 1
    # Corrupt entry should be pruned from database
    assert cache.stats()["entries"] == 0


def test_file_cache_invalidation_by_root_and_file(tmp_path: Path):
    db_path = tmp_path / "cache.db"
    cache = PersistentFileParseCache(db_path)
    policy = AnalysisPolicy(max_file_size=1024 * 1024)
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    root_b.mkdir()

    h1 = hashlib.sha256(b"1").hexdigest()
    h2 = hashlib.sha256(b"2").hexdigest()

    cache.put(
        root_a,
        "mod.py",
        h1,
        policy,
        FileParseResult(_make_dummy_source_file("mod.py"), None, parsed=True),
    )
    cache.put(
        root_b,
        "mod.py",
        h2,
        policy,
        FileParseResult(_make_dummy_source_file("mod.py"), None, parsed=True),
    )
    cache.put(
        root_a,
        "other.py",
        h1,
        policy,
        FileParseResult(_make_dummy_source_file("other.py"), None, parsed=True),
    )
    assert cache.stats()["entries"] == 3

    # Invalidate single file in root_a
    deleted = cache.invalidate_file(root_a, "mod.py")
    assert deleted == 1
    assert cache.stats()["entries"] == 2
    assert cache.get(root_a, "mod.py", h1, policy) is None
    assert cache.get(root_a, "other.py", h1, policy) is not None
    assert cache.get(root_b, "mod.py", h2, policy) is not None

    # Invalidate root_a completely
    deleted_root = cache.invalidate_root(root_a)
    assert deleted_root == 1
    assert cache.stats()["entries"] == 1
    assert cache.get(root_b, "mod.py", h2, policy) is not None


def test_worker_parse_cache_end_to_end_invalidation(tmp_path: Path):
    """End-to-end test verifying warm reuse, same-size edit invalidation, and mtime touch resilience."""
    proj_dir = tmp_path / "sample_proj"
    proj_dir.mkdir()
    f1 = proj_dir / "mod_a.py"
    f2 = proj_dir / "mod_b.py"

    f1.write_text("class Alpha:\n    pass\n", encoding="utf-8")
    f2.write_text(
        "from mod_a import Alpha\ndef use():\n    return Alpha()\n", encoding="utf-8"
    )

    cache_db = tmp_path / "cache.db"
    file_cache = PersistentFileParseCache(cache_db)
    policy = AnalysisPolicy(max_file_size=1024 * 1024)

    # 1. Cold parse
    res1 = parse_project(
        proj_dir,
        policy=policy,
        cache=file_cache,
    )
    assert len(res1.files) == 2
    assert file_cache.stats()["misses"] == 2
    assert file_cache.stats()["hits"] == 0
    assert file_cache.stats()["entries"] == 2

    # 2. Warm parse on unchanged project
    res2 = parse_project(
        proj_dir,
        policy=policy,
        cache=file_cache,
    )
    assert len(res2.files) == 2
    assert file_cache.stats()["hits"] == 2
    # Verify class results are identical
    names1 = sorted([c.name for r in res1.files for c in r.classes])
    names2 = sorted([c.name for r in res2.files for c in r.classes])
    assert names1 == names2

    # 3. Touch mtime without changing file content (e.g. build step or touch)
    past = time.time() - 1000
    os.utime(f1, (past, past))
    res3 = parse_project(
        proj_dir,
        policy=policy,
        cache=file_cache,
    )
    assert len(res3.files) == 2
    # Still hits because content digest SHA-256 matches!
    assert file_cache.stats()["hits"] == 4

    # 4. Same-size modification to mod_a.py
    # "class Alpha:\n    pass\n" is 22 bytes. Replace with "class Beta_:\n    pass\n" (22 bytes)
    assert len("class Alpha:\n    pass\n") == len("class Beta_:\n    pass\n")
    f1.write_text("class Beta_:\n    pass\n", encoding="utf-8")

    res4 = parse_project(
        proj_dir,
        policy=policy,
        cache=file_cache,
    )
    # mod_a.py misses and is reparsed; mod_b.py hits warm cache
    assert file_cache.stats()["hits"] == 5
    assert file_cache.stats()["misses"] == 3
    mod_a_res = [r for r in res4.files if "mod_a.py" in r.source_file.relative_path][0]
    assert mod_a_res.classes[0].name == "Beta_"

    # 5. Cross-root isolation
    # Another project root with identical filenames should not collide
    other_proj = tmp_path / "other_proj"
    other_proj.mkdir()
    (other_proj / "mod_a.py").write_text("class Beta_:\n    pass\n", encoding="utf-8")
    res_other = parse_project(
        other_proj,
        policy=policy,
        cache=file_cache,
    )
    assert len(res_other.files) == 1
    # Even though content is identical, root is other_proj, so it is a cache miss
    assert file_cache.stats()["misses"] == 4


def test_file_cache_clear_and_invalidate(tmp_path: Path):
    db_path = tmp_path / "cache.db"
    cache = PersistentFileParseCache(db_path)
    root_1 = tmp_path / "root_1"
    root_2 = tmp_path / "root_2"
    root_1.mkdir()
    root_2.mkdir()
    policy = AnalysisPolicy(max_file_size=1024 * 1024)

    h = hashlib.sha256(b"abc").hexdigest()
    cache.put(
        root_1,
        "f1.py",
        h,
        policy,
        FileParseResult(_make_dummy_source_file("f1.py"), None, parsed=True),
    )
    cache.put(
        root_2,
        "f2.py",
        h,
        policy,
        FileParseResult(_make_dummy_source_file("f2.py"), None, parsed=True),
    )
    assert cache.stats()["entries"] == 2

    # Invalidate alias method
    cache.invalidate(root_1, "f1.py")
    assert cache.stats()["entries"] == 1

    # Clear specific root
    cache.put(
        root_1,
        "f1.py",
        h,
        policy,
        FileParseResult(_make_dummy_source_file("f1.py"), None, parsed=True),
    )
    cache.clear(root=root_1)
    assert cache.get(root_1, "f1.py", h, policy) is None
    assert cache.get(root_2, "f2.py", h, policy) is not None

    # Clear entire cache
    cache.clear(root=None)
    assert cache.stats()["entries"] == 0


def test_migrations_all_paths(tmp_path: Path):
    # 1. Fresh database without tables
    conn0 = sqlite3.connect(tmp_path / "fresh.db")
    migrate(conn0)
    ver = conn0.execute("SELECT version FROM schema_metadata").fetchone()[0]
    assert ver == SCHEMA_VERSION
    conn0.close()

    # 2. Migration from version 1
    conn1 = sqlite3.connect(tmp_path / "v1.db")
    conn1.execute("CREATE TABLE schema_metadata(version INTEGER PRIMARY KEY)")
    conn1.execute("INSERT INTO schema_metadata(version) VALUES (1)")
    conn1.commit()
    migrate(conn1)
    assert (
        conn1.execute("SELECT version FROM schema_metadata").fetchone()[0]
        == SCHEMA_VERSION
    )
    # Check that file_parse_cache and runtime_sessions tables exist
    assert (
        conn1.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='file_parse_cache'"
        ).fetchone()
        is not None
    )
    conn1.close()

    # 3. Migration from version 2
    conn2 = sqlite3.connect(tmp_path / "v2.db")
    conn2.execute("CREATE TABLE schema_metadata(version INTEGER PRIMARY KEY)")
    conn2.execute("INSERT INTO schema_metadata(version) VALUES (2)")
    conn2.commit()
    migrate(conn2)
    assert (
        conn2.execute("SELECT version FROM schema_metadata").fetchone()[0]
        == SCHEMA_VERSION
    )
    assert (
        conn2.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='file_parse_cache'"
        ).fetchone()
        is not None
    )
    conn2.close()

    # 4. Migration from version 3
    conn3 = sqlite3.connect(tmp_path / "v3.db")
    conn3.execute("CREATE TABLE schema_metadata(version INTEGER PRIMARY KEY)")
    conn3.execute("INSERT INTO schema_metadata(version) VALUES (3)")
    conn3.commit()
    migrate(conn3)
    assert (
        conn3.execute("SELECT version FROM schema_metadata").fetchone()[0]
        == SCHEMA_VERSION
    )
    assert (
        conn3.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='file_parse_cache'"
        ).fetchone()
        is not None
    )
    conn3.close()

    # 5. Unsupported version (missing version record)
    conn_bad = sqlite3.connect(tmp_path / "bad.db")
    conn_bad.execute("CREATE TABLE schema_metadata(version INTEGER PRIMARY KEY)")
    conn_bad.commit()
    with pytest.raises(UnsupportedSchemaError, match="schema metadata is missing"):
        migrate(conn_bad)
    conn_bad.close()

    # 6. Unsupported version (newer version > SCHEMA_VERSION)
    conn_future = sqlite3.connect(tmp_path / "future.db")
    conn_future.execute("CREATE TABLE schema_metadata(version INTEGER PRIMARY KEY)")
    conn_future.execute("INSERT INTO schema_metadata(version) VALUES (99)")
    conn_future.commit()
    with pytest.raises(UnsupportedSchemaError, match="newer than this application"):
        migrate(conn_future)
    conn_future.close()

    # 7. Unsupported version (version 0 or negative)
    conn_old = sqlite3.connect(tmp_path / "old.db")
    conn_old.execute("CREATE TABLE schema_metadata(version INTEGER PRIMARY KEY)")
    conn_old.execute("INSERT INTO schema_metadata(version) VALUES (0)")
    conn_old.commit()
    with pytest.raises(UnsupportedSchemaError, match="no supported migration path"):
        migrate(conn_old)
    conn_old.close()
