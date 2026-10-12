"""Safe, bounded, persistent per-file parse caching for CodeStruct."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterator

from codestruct.analysis.diagnostics import DiagnosticCode, DiagnosticSeverity
from codestruct.analysis.models import (
    CallKind,
    CallSiteObservation,
    ClassDefinition,
    DecoratorMetadata,
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

logger = logging.getLogger("codestruct.storage.file_cache")

FILE_CACHE_FORMAT_VERSION = "1"
PARSER_VERSION = "2"
DEFAULT_MAX_CACHE_ENTRIES = 5000
DEFAULT_MAX_CACHE_BYTES = 50 * 1024 * 1024  # 50 MiB


def _span_to_dict(span: SourceSpan | None) -> dict[str, Any] | None:
    if span is None:
        return None
    return {
        "start_line": span.start_line,
        "start_column": span.start_column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }


def _dict_to_span(data: dict[str, Any] | None) -> SourceSpan | None:
    if data is None:
        return None
    return SourceSpan(
        start_line=int(data["start_line"]),
        start_column=int(data["start_column"]),
        end_line=int(data["end_line"]) if data.get("end_line") is not None else None,
        end_column=(
            int(data["end_column"]) if data.get("end_column") is not None else None
        ),
    )


def file_parse_result_to_dict(result: FileParseResult) -> dict[str, Any]:
    """Convert FileParseResult dataclass into a JSON-serializable dict."""
    sf = result.source_file
    sf_dict = {
        "id": sf.id,
        "relative_path": sf.relative_path,
        "module_name": sf.module_name,
        "is_package": sf.is_package,
        "size_bytes": sf.size_bytes,
        "modified_ns": sf.modified_ns,
    }

    mod_dict = None
    if result.module is not None:
        mod = result.module
        mod_dict = {
            "id": mod.id,
            "name": mod.name,
            "qualified_name": mod.qualified_name,
            "source_file_id": mod.source_file_id,
            "relative_path": mod.relative_path,
            "is_package": mod.is_package,
            "has_docstring": mod.has_docstring,
            "span": _span_to_dict(mod.span),
        }

    classes_list = []
    for cls in result.classes:
        classes_list.append(
            {
                "id": cls.id,
                "name": cls.name,
                "qualified_name": cls.qualified_name,
                "enclosing_scope_id": cls.enclosing_scope_id,
                "span": _span_to_dict(cls.span),
                "decorators": [
                    {
                        "id": d.id,
                        "expression": d.expression,
                        "span": _span_to_dict(d.span),
                    }
                    for d in cls.decorators
                ],
                "has_docstring": cls.has_docstring,
            }
        )

    functions_list = []
    for fn in result.functions:
        functions_list.append(
            {
                "id": fn.id,
                "name": fn.name,
                "qualified_name": fn.qualified_name,
                "kind": fn.kind.value,
                "enclosing_scope_id": fn.enclosing_scope_id,
                "span": _span_to_dict(fn.span),
                "parameters": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "kind": p.kind.value,
                        "annotation": p.annotation,
                        "has_default": p.has_default,
                        "span": _span_to_dict(p.span),
                    }
                    for p in fn.parameters
                ],
                "decorators": [
                    {
                        "id": d.id,
                        "expression": d.expression,
                        "span": _span_to_dict(d.span),
                    }
                    for d in fn.decorators
                ],
                "return_annotation": fn.return_annotation,
                "has_docstring": fn.has_docstring,
            }
        )

    variables_list = []
    for var in result.variables:
        variables_list.append(
            {
                "id": var.id,
                "name": var.name,
                "qualified_name": var.qualified_name,
                "enclosing_scope_id": var.enclosing_scope_id,
                "span": _span_to_dict(var.span),
                "type_annotation": var.type_annotation,
                "value_expression": var.value_expression,
                "is_constant": var.is_constant,
            }
        )

    imports_list = []
    for imp in result.imports:
        imports_list.append(
            {
                "id": imp.id,
                "kind": imp.kind.value,
                "module": imp.module,
                "relative_level": imp.relative_level,
                "names": [{"name": n.name, "alias": n.alias} for n in imp.names],
                "enclosing_scope_id": imp.enclosing_scope_id,
                "span": _span_to_dict(imp.span),
            }
        )

    inheritance_list = []
    for inh in result.inheritance:
        inheritance_list.append(
            {
                "id": inh.id,
                "class_id": inh.class_id,
                "expression": inh.expression,
                "expression_kind": inh.expression_kind,
                "status": inh.status.value,
                "span": _span_to_dict(inh.span),
            }
        )

    calls_list = []
    for call in result.calls:
        calls_list.append(
            {
                "id": call.id,
                "expression": call.expression,
                "kind": call.kind.value,
                "enclosing_scope_id": call.enclosing_scope_id,
                "enclosing_qualified_name": call.enclosing_qualified_name,
                "status": call.status.value,
                "span": _span_to_dict(call.span),
            }
        )

    diagnostics_list = []
    for diag in result.diagnostics:
        diagnostics_list.append(
            {
                "id": diag.id,
                "code": diag.code.value,
                "severity": diag.severity.value,
                "message": diag.message,
                "relative_path": diag.relative_path,
                "span": _span_to_dict(diag.span),
            }
        )

    return {
        "source_file": sf_dict,
        "module": mod_dict,
        "classes": classes_list,
        "functions": functions_list,
        "variables": variables_list,
        "imports": imports_list,
        "inheritance": inheritance_list,
        "calls": calls_list,
        "diagnostics": diagnostics_list,
        "encoding": result.encoding,
        "parsed": result.parsed,
    }


def dict_to_file_parse_result(data: dict[str, Any]) -> FileParseResult:
    """Reconstruct FileParseResult dataclass from serialized dictionary."""
    sf_data = data["source_file"]
    source_file = SourceFile(
        id=sf_data["id"],
        relative_path=sf_data["relative_path"],
        module_name=sf_data["module_name"],
        is_package=bool(sf_data["is_package"]),
        size_bytes=int(sf_data["size_bytes"]),
        modified_ns=int(sf_data["modified_ns"]),
    )

    module = None
    if data.get("module") is not None:
        m_data = data["module"]
        span = _dict_to_span(m_data["span"])
        if span is None:
            raise ValueError("ModuleMetadata must have a span")
        module = ModuleMetadata(
            id=m_data["id"],
            name=m_data["name"],
            qualified_name=m_data["qualified_name"],
            source_file_id=m_data["source_file_id"],
            relative_path=m_data["relative_path"],
            is_package=bool(m_data["is_package"]),
            has_docstring=bool(m_data["has_docstring"]),
            span=span,
        )

    classes = []
    for c in data.get("classes", []):
        span = _dict_to_span(c["span"])
        if span is None:
            raise ValueError("ClassDefinition must have a span")
        decorators = tuple(
            DecoratorMetadata(
                id=d["id"],
                expression=d["expression"],
                span=_dict_to_span(d["span"]) or SourceSpan(1, 1),
            )
            for d in c.get("decorators", [])
        )
        classes.append(
            ClassDefinition(
                id=c["id"],
                name=c["name"],
                qualified_name=c["qualified_name"],
                enclosing_scope_id=c["enclosing_scope_id"],
                span=span,
                decorators=decorators,
                has_docstring=bool(c.get("has_docstring", False)),
            )
        )

    functions = []
    for f in data.get("functions", []):
        span = _dict_to_span(f["span"])
        if span is None:
            raise ValueError("FunctionDefinition must have a span")
        decorators = tuple(
            DecoratorMetadata(
                id=d["id"],
                expression=d["expression"],
                span=_dict_to_span(d["span"]) or SourceSpan(1, 1),
            )
            for d in f.get("decorators", [])
        )
        parameters = tuple(
            ParameterMetadata(
                id=p["id"],
                name=p["name"],
                kind=ParameterKind(p["kind"]),
                annotation=p.get("annotation"),
                has_default=bool(p.get("has_default", False)),
                span=_dict_to_span(p["span"]) or SourceSpan(1, 1),
            )
            for p in f.get("parameters", [])
        )
        functions.append(
            FunctionDefinition(
                id=f["id"],
                name=f["name"],
                qualified_name=f["qualified_name"],
                kind=DefinitionKind(f["kind"]),
                enclosing_scope_id=f["enclosing_scope_id"],
                span=span,
                parameters=parameters,
                decorators=decorators,
                return_annotation=f.get("return_annotation"),
                has_docstring=bool(f.get("has_docstring", False)),
            )
        )

    variables = []
    for v in data.get("variables", []):
        span = _dict_to_span(v["span"])
        if span is None:
            raise ValueError("VariableDefinition must have a span")
        variables.append(
            VariableDefinition(
                id=v["id"],
                name=v["name"],
                qualified_name=v["qualified_name"],
                enclosing_scope_id=v["enclosing_scope_id"],
                span=span,
                type_annotation=v.get("type_annotation"),
                value_expression=v.get("value_expression"),
                is_constant=bool(v.get("is_constant", False)),
            )
        )

    imports = []
    for i in data.get("imports", []):
        span = _dict_to_span(i["span"])
        if span is None:
            raise ValueError("ImportStatement must have a span")
        names = tuple(
            ImportAlias(n["name"], n.get("alias")) for n in i.get("names", [])
        )
        imports.append(
            ImportStatement(
                id=i["id"],
                kind=ImportKind(i["kind"]),
                module=i.get("module"),
                relative_level=int(i.get("relative_level", 0)),
                names=names,
                enclosing_scope_id=i["enclosing_scope_id"],
                span=span,
            )
        )

    inheritance = []
    for inh in data.get("inheritance", []):
        span = _dict_to_span(inh["span"])
        if span is None:
            raise ValueError("InheritanceReference must have a span")
        inheritance.append(
            InheritanceReference(
                id=inh["id"],
                class_id=inh["class_id"],
                expression=inh["expression"],
                expression_kind=inh["expression_kind"],
                status=ResolutionStatus(inh["status"]),
                span=span,
            )
        )

    calls = []
    for c in data.get("calls", []):
        span = _dict_to_span(c["span"])
        if span is None:
            raise ValueError("CallSiteObservation must have a span")
        calls.append(
            CallSiteObservation(
                id=c["id"],
                expression=c["expression"],
                kind=CallKind(c["kind"]),
                enclosing_scope_id=c["enclosing_scope_id"],
                enclosing_qualified_name=c["enclosing_qualified_name"],
                status=ResolutionStatus(c["status"]),
                span=span,
            )
        )

    diagnostics = []
    for d in data.get("diagnostics", []):
        span = _dict_to_span(d.get("span"))
        diagnostics.append(
            ParserDiagnostic(
                id=d["id"],
                code=DiagnosticCode(d["code"]),
                severity=DiagnosticSeverity(d["severity"]),
                message=d["message"],
                relative_path=d.get("relative_path"),
                span=span,
            )
        )

    return FileParseResult(
        source_file=source_file,
        module=module,
        classes=tuple(classes),
        functions=tuple(functions),
        variables=tuple(variables),
        imports=tuple(imports),
        inheritance=tuple(inheritance),
        calls=tuple(calls),
        diagnostics=tuple(diagnostics),
        encoding=data.get("encoding"),
        parsed=bool(data.get("parsed", False)),
    )


def compute_parse_policy_fingerprint(policy: AnalysisPolicy) -> str:
    """Compute a deterministic hash for parse-affecting policy parameters."""
    opts = {
        "source_grammar": policy.source_grammar,
        "max_file_size": policy.max_file_size,
        "single_file_name": policy.single_file_name,
    }
    encoded = json.dumps(opts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_file_cache_key(
    root_identity: str,
    relative_path: str,
    content_sha256: str,
    parser_version: str,
    policy_fingerprint: str,
) -> str:
    """Compute a strict SHA-256 cache key bound to root, path, content digest, and versions."""
    normalized_path = relative_path.replace("\\", "/").strip("/")
    parts = [
        FILE_CACHE_FORMAT_VERSION,
        root_identity,
        normalized_path,
        content_sha256,
        parser_version,
        policy_fingerprint,
    ]
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


class PersistentFileParseCache:
    """Safe, persistent, process-concurrent, bounded per-file parse cache backed by SQLite."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        max_entries: int = DEFAULT_MAX_CACHE_ENTRIES,
        max_bytes: int = DEFAULT_MAX_CACHE_BYTES,
    ) -> None:
        if db_path is None:
            from codestruct.settings import load_settings

            settings = load_settings()
            self._db_path = settings.database_path or Path("codestruct.sqlite3")
        else:
            self._db_path = Path(db_path).resolve()

        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        self._init_db()

    @property
    def database_path(self) -> Path:
        return self._db_path

    @contextlib.contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self._db_path),
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None,  # autocommit / explicit transactions
        )
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    def _init_db(self) -> None:
        try:
            with self._lock, self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS file_parse_cache(
                        cache_key TEXT PRIMARY KEY,
                        root_identity TEXT NOT NULL,
                        relative_path TEXT NOT NULL,
                        content_sha256 TEXT NOT NULL,
                        parser_version TEXT NOT NULL,
                        policy_fingerprint TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        stored_size INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        last_accessed_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_file_parse_cache_lru ON file_parse_cache(last_accessed_at)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_file_parse_cache_lookup ON file_parse_cache(root_identity, relative_path)"
                )
        except Exception as exc:
            logger.warning("Could not initialize file_parse_cache table: %s", exc)

    def get(
        self,
        root: Path | str,
        relative_path: str,
        content_sha256: str,
        policy: AnalysisPolicy,
    ) -> FileParseResult | None:
        """Retrieve a cached FileParseResult by content hash and root identity."""
        root_identity = os.path.normcase(str(Path(root).resolve()))
        policy_fingerprint = compute_parse_policy_fingerprint(policy)
        key = compute_file_cache_key(
            root_identity,
            relative_path,
            content_sha256,
            PARSER_VERSION,
            policy_fingerprint,
        )

        try:
            with self._lock, self._get_connection() as conn:
                row = conn.execute(
                    "SELECT result_json FROM file_parse_cache WHERE cache_key = ?",
                    (key,),
                ).fetchone()

                if row is None:
                    self._misses += 1
                    return None

                result_json = row[0]
                try:
                    payload = json.loads(result_json)
                    result = dict_to_file_parse_result(payload)
                except Exception as corrupt_exc:
                    logger.warning(
                        "Corrupted file parse cache entry for %s (%s); evicting: %s",
                        relative_path,
                        key,
                        corrupt_exc,
                    )
                    conn.execute(
                        "DELETE FROM file_parse_cache WHERE cache_key = ?",
                        (key,),
                    )
                    self._misses += 1
                    return None

                # Update LRU access timestamp
                conn.execute(
                    "UPDATE file_parse_cache SET last_accessed_at = ? WHERE cache_key = ?",
                    (time.time(), key),
                )
                self._hits += 1
                return result
        except Exception as exc:
            logger.warning("File cache read failed for %s: %s", relative_path, exc)
            self._misses += 1
            return None

    def put(
        self,
        root: Path | str,
        relative_path: str,
        content_sha256: str,
        policy: AnalysisPolicy,
        result: FileParseResult,
    ) -> None:
        """Store a FileParseResult in the persistent cache with bounded storage and eviction."""
        if not result.parsed:
            return  # Do not cache failed unparsed results

        root_identity = os.path.normcase(str(Path(root).resolve()))
        policy_fingerprint = compute_parse_policy_fingerprint(policy)
        key = compute_file_cache_key(
            root_identity,
            relative_path,
            content_sha256,
            PARSER_VERSION,
            policy_fingerprint,
        )

        try:
            payload = file_parse_result_to_dict(result)
            result_json = json.dumps(payload, separators=(",", ":"))
            stored_size = len(result_json.encode("utf-8"))
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            now_epoch = time.time()

            with self._lock, self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # Enforce capacity / eviction before insert
                    self._evict_if_needed(conn, stored_size)

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO file_parse_cache(
                            cache_key, root_identity, relative_path, content_sha256,
                            parser_version, policy_fingerprint, result_json,
                            stored_size, created_at, last_accessed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            key,
                            root_identity,
                            relative_path.replace("\\", "/").strip("/"),
                            content_sha256,
                            PARSER_VERSION,
                            policy_fingerprint,
                            result_json,
                            stored_size,
                            now_iso,
                            now_epoch,
                        ),
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
        except Exception as exc:
            logger.warning("File cache write failed for %s: %s", relative_path, exc)

    def _evict_if_needed(self, conn: sqlite3.Connection, incoming_size: int) -> None:
        """Evict oldest LRU entries if count or byte bounds are exceeded."""
        row = conn.execute(
            "SELECT count(*), coalesce(sum(stored_size), 0) FROM file_parse_cache"
        ).fetchone()
        current_count = row[0] if row else 0
        current_bytes = row[1] if row else 0

        target_count = self.max_entries - 1
        target_bytes = self.max_bytes - incoming_size

        if current_count > target_count or current_bytes > target_bytes:
            # Delete 10% or at least 1 oldest entry
            evict_batch = max(1, current_count // 10)
            conn.execute(
                """
                DELETE FROM file_parse_cache
                WHERE cache_key IN (
                    SELECT cache_key FROM file_parse_cache
                    ORDER BY last_accessed_at ASC
                    LIMIT ?
                )
                """,
                (evict_batch,),
            )

    def invalidate_file(self, root: Path | str, relative_path: str) -> int:
        """Invalidate all cached versions of a specific file."""
        root_identity = os.path.normcase(str(Path(root).resolve()))
        normalized_path = relative_path.replace("\\", "/").strip("/")
        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM file_parse_cache WHERE root_identity = ? AND relative_path = ?",
                    (root_identity, normalized_path),
                )
                return cursor.rowcount
        except Exception as exc:
            logger.warning("File cache invalidation failed: %s", exc)
            return 0

    def invalidate_root(self, root: Path | str) -> int:
        """Invalidate all cached entries for a root."""
        root_identity = os.path.normcase(str(Path(root).resolve()))
        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM file_parse_cache WHERE root_identity = ?",
                    (root_identity,),
                )
                return cursor.rowcount
        except Exception as exc:
            logger.warning("File cache root invalidation failed: %s", exc)
            return 0

    def invalidate(self, root: Path | str, relative_path: str) -> None:
        """Invalidate all cached versions of a specific file."""
        self.invalidate_file(root, relative_path)

    def clear(self, root: Path | str | None = None) -> None:
        """Clear cache entries, optionally scoped to a single root."""
        try:
            with self._lock, self._get_connection() as conn:
                if root is None:
                    conn.execute("DELETE FROM file_parse_cache")
                else:
                    root_identity = os.path.normcase(str(Path(root).resolve()))
                    conn.execute(
                        "DELETE FROM file_parse_cache WHERE root_identity = ?",
                        (root_identity,),
                    )
        except Exception as exc:
            logger.warning("File cache clear failed: %s", exc)

    def stats(self) -> dict[str, Any]:
        """Return cache entry count, total byte size, and hit/miss statistics."""
        try:
            with self._lock, self._get_connection() as conn:
                row = conn.execute(
                    "SELECT count(*), coalesce(sum(stored_size), 0) FROM file_parse_cache"
                ).fetchone()
                count = row[0] if row else 0
                total_bytes = row[1] if row else 0
        except Exception:
            count = 0
            total_bytes = 0

        return {
            "entries": count,
            "stored_bytes": total_bytes,
            "total_bytes": total_bytes,
            "hits": self._hits,
            "misses": self._misses,
        }
