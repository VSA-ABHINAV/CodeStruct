"""Comprehensive tests for M6 bounded retrieval layer.

Covers:
- Project root containment (rejection of directory traversal, escapes, outside paths).
- Secret and sensitive file detection and exclusion.
- Bounded line/byte limits and truncation handling.
- Canonical source snippets, graph relationships, runtime observations, metrics, and evidence items.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from codestruct.analysis.retrieval import (
    is_safe_path_contained,
    is_secret_or_sensitive,
    retrieve_evidence_context,
    retrieve_source_snippet,
)

# ---------------------------------------------------------------------------
# 1. Secret & Sensitive Path Exclusion Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        ".env.production",
        "sub/.env",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa.pub",
        "certs/server.pem",
        "certs/server.key",
        "certs/bundle.pfx",
        "certs/cert.p12",
        "keys/private.der",
        "keys/ssl.crt",
        ".htpasswd",
        ".netrc",
        "config/app_secrets.json",
        "credentials.yaml",
        "db_password.txt",
        "api_token.py",
        "auth/private_key.py",
        ".git/config",
        ".ssh/id_rsa",
        ".aws/credentials",
        "cache/module.pyc",
        "lib/native.pyd",
        "data/app.sqlite3",
        "data/database.db",
    ],
)
def test_is_secret_or_sensitive_rejects_sensitive_files(path: str) -> None:
    assert is_secret_or_sensitive(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "app.py",
        "src/main.py",
        "billing/service.py",
        "models/user.py",
        "utils/helpers.py",
        "tests/test_calculator.py",
        "README.md",
        "package.json",
    ],
)
def test_is_secret_or_sensitive_allows_safe_code_files(path: str) -> None:
    assert is_secret_or_sensitive(path) is False


# ---------------------------------------------------------------------------
# 2. Project Root Containment Tests
# ---------------------------------------------------------------------------


def test_is_safe_path_contained_valid(tmp_path: Path) -> None:
    safe_file = tmp_path / "src" / "app.py"
    safe_file.parent.mkdir(parents=True)
    safe_file.write_text("print('hello')", encoding="utf-8")

    resolved = is_safe_path_contained("src/app.py", tmp_path)
    assert resolved is not None
    assert resolved == safe_file.resolve()


def test_is_safe_path_contained_rejects_traversal(tmp_path: Path) -> None:
    outside_dir = tmp_path.parent / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "secret.py"
    outside_file.write_text("secret = 123", encoding="utf-8")

    # Path traversal ../
    assert is_safe_path_contained("../outside_dir/secret.py", tmp_path) is None
    # Nested traversal
    sub = tmp_path / "sub"
    sub.mkdir()
    assert is_safe_path_contained("sub/../../outside_dir/secret.py", tmp_path) is None


def test_is_safe_path_contained_rejects_absolute_outside(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside.py"
    outside_file.write_text("outside = True", encoding="utf-8")

    assert is_safe_path_contained(str(outside_file), tmp_path) is None


def test_is_safe_path_contained_rejects_null_byte(tmp_path: Path) -> None:
    assert is_safe_path_contained("app.py\x00.exe", tmp_path) is None


def test_is_safe_path_contained_rejects_nonexistent_and_directories(
    tmp_path: Path,
) -> None:
    assert is_safe_path_contained("nonexistent.py", tmp_path) is None
    assert is_safe_path_contained("", tmp_path) is None

    sub = tmp_path / "sub"
    sub.mkdir()
    # Directory is not a regular file
    assert is_safe_path_contained("sub", tmp_path) is None


# ---------------------------------------------------------------------------
# 3. Bounded Source Snippet Retrieval Tests
# ---------------------------------------------------------------------------


def test_retrieve_source_snippet_bounds_lines(tmp_path: Path) -> None:
    file = tmp_path / "large.py"
    lines = [f"line_{i} = {i}\n" for i in range(1, 201)]
    file.write_text("".join(lines), encoding="utf-8")

    # Span around lines 50..55 with max_lines=20
    snippet = retrieve_source_snippet(
        project_root=tmp_path,
        file_path="large.py",
        line=50,
        end_line=55,
        max_lines=20,
        max_bytes=10000,
    )
    assert snippet is not None
    assert snippet.file_path == "large.py"
    assert snippet.line_count <= 20
    assert snippet.start_line <= 50
    assert snippet.end_line >= 55
    assert "line_50 = 50" in snippet.content
    assert not snippet.is_truncated


def test_retrieve_source_snippet_bounds_bytes_with_marker(tmp_path: Path) -> None:
    file = tmp_path / "dense.py"
    # Create content that exceeds 200 bytes
    lines = [
        f"# long_comment_line_number_{i:04d}_with_padding_characters_here\n"
        for i in range(50)
    ]
    file.write_text("".join(lines), encoding="utf-8")

    snippet = retrieve_source_snippet(
        project_root=tmp_path,
        file_path="dense.py",
        line=1,
        end_line=20,
        max_lines=50,
        max_bytes=250,
    )
    assert snippet is not None
    assert snippet.is_truncated is True
    assert "[TRUNCATED: byte limit reached]" in snippet.content
    assert snippet.byte_count <= 350


def test_retrieve_source_snippet_excludes_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgres://user:pass@localhost\n", encoding="utf-8"
    )

    assert retrieve_source_snippet(tmp_path, ".env", 1, 1) is None

    token_file = tmp_path / "api_token.py"
    token_file.write_text("API_KEY = 'secret123'\n", encoding="utf-8")
    assert retrieve_source_snippet(tmp_path, "api_token.py", 1, 1) is None


def test_retrieve_source_snippet_outside_root_returns_none(tmp_path: Path) -> None:
    outside = tmp_path.parent / "escape.py"
    outside.write_text("escape = 1", encoding="utf-8")

    assert retrieve_source_snippet(tmp_path, "../escape.py", 1, 1) is None


def test_retrieve_source_snippet_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("", encoding="utf-8")

    snippet = retrieve_source_snippet(tmp_path, "empty.py", 1, 1)
    assert snippet is not None
    assert snippet.content == ""
    assert snippet.line_count == 0


def test_retrieve_source_snippet_safety_caps_giant_file(
    tmp_path: Path, monkeypatch
) -> None:
    fake_file = tmp_path / "giant.py"
    fake_file.write_text("small text", encoding="utf-8")

    # Mock stat to report > 2MB size
    import os

    orig_stat = Path.stat

    def mock_stat(self, *args, **kwargs):
        st = orig_stat(self, *args, **kwargs)
        if self.name == "giant.py":
            return os.stat_result(
                (
                    st.st_mode,
                    st.st_ino,
                    st.st_dev,
                    st.st_nlink,
                    st.st_uid,
                    st.st_gid,
                    5 * 1024 * 1024,
                    st.st_atime,
                    st.st_mtime,
                    st.st_ctime,
                )
            )
        return st

    monkeypatch.setattr(Path, "stat", mock_stat)
    assert retrieve_source_snippet(tmp_path, "giant.py", 1, 1) is None


# ---------------------------------------------------------------------------
# 4. Canonical Evidence Assembly Tests
# ---------------------------------------------------------------------------


def test_retrieve_evidence_context_comprehensive(tmp_path: Path) -> None:
    src_file = tmp_path / "calc.py"
    src_file.write_text(
        "def compute_total(items):\n"
        '    """Compute total sum."""\n'
        "    subtotal = sum(items)\n"
        "    return apply_tax(subtotal)\n",
        encoding="utf-8",
    )

    graph: dict[str, Any] = {
        "nodes": [
            {
                "id": "node-target",
                "name": "compute_total",
                "qualified_name": "calc.compute_total",
                "kind": "function",
                "file_path": "calc.py",
                "line": 1,
                "end_line": 4,
                "attributes": [
                    {"key": "fan_in", "value": 4},
                    {"key": "fan_out", "value": 2},
                    {"key": "instability", "value": 0.33},
                    {"key": "degree_centrality", "value": 0.5},
                    {"key": "community_id", "value": 7},
                    {"key": "in_cycle", "value": False},
                    {"key": "runtime_calls", "value": 120},
                    {"key": "runtime_exceptions", "value": 0},
                    {"key": "runtime_duration_ms", "value": 45.2},
                    {"key": "docstring", "value": "Compute total sum."},
                ],
                "evidence_ids": ["ev-decl-01"],
            },
            {
                "id": "node-caller",
                "name": "checkout",
                "qualified_name": "order.checkout",
                "kind": "function",
            },
            {
                "id": "node-callee",
                "name": "apply_tax",
                "qualified_name": "tax.apply_tax",
                "kind": "function",
            },
            {
                "id": "node-ambiguous",
                "name": "ambig",
                "qualified_name": "ambig",
                "kind": "function",
            },
        ],
        "edges": [
            # Resolved CALL from caller -> target
            {
                "id": "edge-call-in",
                "source_id": "node-caller",
                "target_id": "node-target",
                "kind": "CALL",
                "resolution_status": "resolved",
                "evidence_ids": ["ev-call-in-01"],
            },
            # Resolved CALL from target -> callee
            {
                "id": "edge-call-out",
                "source_id": "node-target",
                "target_id": "node-callee",
                "kind": "CALL",
                "resolution_status": "resolved",
                "evidence_ids": ["ev-call-out-01"],
            },
            # Unresolved CALL should be excluded from dependency network
            {
                "id": "edge-call-unresolved",
                "source_id": "node-target",
                "target_id": "node-ambiguous",
                "kind": "CALL",
                "resolution_status": "unresolved",
                "evidence_ids": ["ev-unresolved-99"],
            },
        ],
        "evidence": [
            {
                "id": "ev-decl-01",
                "origin": "STATIC_AST",
                "observation_kind": "function_definition",
                "location": {"path": "calc.py", "start_line": 1, "end_line": 4},
                "excerpt": "def compute_total(items):",
            },
            {
                "id": "ev-call-in-01",
                "origin": "STATIC_AST",
                "observation_kind": "call_site",
                "location": {"path": "order.py", "start_line": 20},
                "excerpt": "compute_total(cart.items)",
            },
            {
                "id": "ev-call-out-01",
                "origin": "STATIC_AST",
                "observation_kind": "call_site",
                "location": {"path": "calc.py", "start_line": 4},
                "excerpt": "apply_tax(subtotal)",
            },
        ],
    }

    context = retrieve_evidence_context(graph, "node-target", project_root=tmp_path)
    assert context.node_id == "node-target"
    assert context.name == "compute_total"
    assert context.docstring == "Compute total sum."

    # Source snippet retrieved
    assert context.source_snippet is not None
    assert "def compute_total" in context.source_snippet.content

    # Metrics
    assert context.metrics["fan_in"] == 4
    assert context.metrics["fan_out"] == 2
    assert context.metrics["instability"] == 0.33
    assert context.metrics["degree_centrality"] == 0.5
    assert context.metrics["community_id"] == 7
    assert context.metrics["in_cycle"] is False

    # Runtime stats
    assert context.runtime_stats["runtime_calls"] == 120
    assert context.runtime_stats["runtime_duration_ms"] == 45.2

    # Resolved dependencies only
    assert "order.checkout" in context.callers
    assert "tax.apply_tax" in context.callees
    assert "ambig" not in context.callees

    # Evidence IDs
    assert "ev-decl-01" in context.canonical_evidence_ids
    assert "ev-call-in-01" in context.canonical_evidence_ids
    assert "ev-call-out-01" in context.canonical_evidence_ids


def test_retrieve_evidence_context_missing_node() -> None:
    with pytest.raises(KeyError, match="not found in graph"):
        retrieve_evidence_context({"nodes": []}, "missing-node")


def test_retrieve_evidence_context_imports_inherits_and_span() -> None:
    graph = {
        "nodes": [
            {
                "id": "node-class-derived",
                "name": "DerivedService",
                "qualified_name": "pkg.DerivedService",
                "kind": "class",
                "location": {
                    "path": "pkg/service.py",
                    "span": {
                        "start": {"line": 10},
                        "end": {"line": 25},
                    },
                },
                "attributes": [
                    ("ca", 2),
                    ("ce", 3),
                    ("cohesion", 0.75),
                    ("fan_in", "invalid_int"),
                    ("instability", "invalid_float"),
                ],
            },
            {
                "id": "node-base",
                "name": "BaseService",
                "qualified_name": "pkg.BaseService",
                "kind": "class",
            },
            {
                "id": "node-mod-utils",
                "name": "utils",
                "qualified_name": "pkg.utils",
                "kind": "module",
            },
            {
                "id": "node-parent-pkg",
                "name": "pkg",
                "kind": "package",
            },
        ],
        "edges": [
            # INHERITS
            {
                "id": "e-inherit",
                "source_id": "node-class-derived",
                "target_id": "node-base",
                "kind": "INHERITS",
                "resolution_status": "resolved",
                "evidence_ids": ["ev-inherit-01"],
            },
            # IMPORTS
            {
                "id": "e-import",
                "source_id": "node-class-derived",
                "target_id": "node-mod-utils",
                "kind": "IMPORTS",
                "resolution_status": "resolved",
                "evidence_ids": ["ev-import-01"],
            },
            # DEFINES from parent pkg
            {
                "id": "e-defines",
                "source_id": "node-parent-pkg",
                "target_id": "node-class-derived",
                "kind": "DEFINES",
                "evidence_ids": ["ev-defines-01"],
            },
        ],
    }

    context = retrieve_evidence_context(graph, "node-class-derived")
    assert context.line == 10
    assert context.end_line == 25
    assert "pkg.BaseService" in context.inherits
    assert "pkg.utils" in context.imports
    assert context.metrics.get("ca") == 2
    assert context.metrics.get("ce") == 3
    assert context.metrics.get("cohesion") == 0.75
    assert "fan_in" not in context.metrics  # invalid int handled gracefully
    assert "ev-defines-01" in context.canonical_evidence_ids


def test_is_safe_path_contained_root_not_dir(tmp_path: Path) -> None:
    file_as_root = tmp_path / "file.txt"
    file_as_root.write_text("hello", encoding="utf-8")
    assert is_safe_path_contained("test.py", file_as_root) is None


def test_is_safe_path_contained_absolute_within_root(tmp_path: Path) -> None:
    f = tmp_path / "inside.py"
    f.write_text("ok = True", encoding="utf-8")
    resolved = is_safe_path_contained(str(f.resolve()), tmp_path)
    assert resolved == f.resolve()
