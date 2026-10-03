"""Verify local release archives without installing or executing their contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from pathlib import Path

from packaging.version import Version

FORBIDDEN = (
    ".env",
    ".sqlite",
    ".sqlite3",
    "-wal",
    "-shm",
    "__pycache__",
    ".coverage",
    "node_modules",
    "test-output",
    ".map",
)
SENSITIVE_CONTENT = (
    b"-----BEGIN PRIVATE KEY",
    b"D:\\REP\\",
    b"C:\\Users\\",
)
FORBIDDEN_FRONTEND_CONTENT = (
    b"http://localhost",
    b"http://127.0.0.1",
    b"CODESTRUCT_AUTHORIZED_ROOTS",
    b"CODESTRUCT_DATABASE_PATH",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def members(path: Path) -> list[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    with tarfile.open(path, "r:gz") as archive:
        return archive.getnames()


def payloads(path: Path):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                yield name, archive.read(name)
        return
    with tarfile.open(path, "r:gz") as archive:
        for item in archive.getmembers():
            if item.isfile():
                extracted = archive.extractfile(item)
                if extracted is not None:
                    yield item.name, extracted.read()


def inspect(path: Path, version: str) -> dict[str, object]:
    names = members(path)
    normalized = path.name.replace("-", "_")
    if version.replace("-", "_") not in normalized:
        raise ValueError(f"artifact filename does not contain version: {path.name}")
    if any(marker in name.lower() for name in names for marker in FORBIDDEN):
        raise ValueError(f"forbidden archive member in {path.name}")
    for name, content in payloads(path):
        if any(marker in content for marker in SENSITIVE_CONTENT):
            raise ValueError(f"private material detected in {path.name}:{name}")
        if name.endswith(".js") and "/web/assets/" in name.replace("\\", "/"):
            if any(marker in content for marker in FORBIDDEN_FRONTEND_CONTENT):
                raise ValueError(
                    f"unsafe production frontend setting in {path.name}:{name}"
                )
    if path.suffix == ".whl":
        required = (
            "codestruct/__about__.py",
            "codestruct/cli.py",
            "codestruct/web/index.html",
        )
        if not all(any(name.endswith(item) for name in names) for item in required):
            raise ValueError(f"wheel is missing package/frontend content: {path.name}")
        if not any("codestruct/web/assets/" in name for name in names):
            raise ValueError("wheel has no hashed frontend assets")
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": digest(path),
        "members": len(names),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True, type=Version)
    args = parser.parse_args()
    artifacts = sorted(
        [*args.directory.glob("*.whl"), *args.directory.glob("*.tar.gz")]
    )
    if len(artifacts) != 2:
        raise SystemExit("expected exactly one wheel and one source distribution")
    report = [inspect(path, str(args.version)) for path in artifacts]
    output = args.directory / "SHA256SUMS.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
