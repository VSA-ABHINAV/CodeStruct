"""Bounded deterministic content and policy fingerprints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codestruct import __version__
from codestruct.analysis import AnalysisPolicy, scan_project
from codestruct.graph.builder import SCHEMA_VERSION

CACHE_FORMAT_VERSION = "1"
RESOLVER_VERSION = "1"


def policy_fingerprint(policy: AnalysisPolicy) -> str:
    value = {
        "include": policy.include_patterns,
        "exclude": policy.exclude_patterns,
        "directories": sorted(policy.excluded_directories),
        "files": sorted(policy.excluded_file_names),
        "depth": policy.max_depth,
        "count": policy.max_files,
        "size": policy.max_file_size,
        "grammar": policy.source_grammar,
        "single_file": policy.single_file_name,
        "metrics": policy.compute_metrics,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=list).encode()
    ).hexdigest()


def project_fingerprint(root: Path, policy: AnalysisPolicy) -> str:
    scan = scan_project(root, policy)
    digest = hashlib.sha256()
    for source in scan.source_files:
        path = root / Path(source.relative_path)
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise OSError("a source file changed during fingerprinting")
        digest.update(source.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
    digest.update(str(len(scan.source_files)).encode())
    return digest.hexdigest()


def cache_key(
    root_id: str, relative_path: str, project_hash: str, policy_hash: str
) -> str:
    value = (
        CACHE_FORMAT_VERSION,
        root_id,
        relative_path.replace("\\", "/"),
        project_hash,
        policy_hash,
        __version__,
        RESOLVER_VERSION,
        SCHEMA_VERSION,
    )
    return hashlib.sha256("\0".join(value).encode()).hexdigest()
