"""Fail-fast local release-candidate validation; does not publish."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)  # noqa: S603


def main() -> int:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    run([sys.executable, "-m", "pytest"])
    run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            "backend",
            "tests",
            "sample_project",
            "tools",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "backend",
            "tests",
            "sample_project",
            "tools",
        ]
    )
    run([sys.executable, "-m", "mypy"])
    run([npm, "run", "test:coverage"], ROOT / "frontend")
    run([npm, "run", "test:a11y"], ROOT / "frontend")
    run([npm, "run", "lint"], ROOT / "frontend")
    run([sys.executable, "tests/performance/benchmark.py"])
    run([sys.executable, "tools/check_docs.py"])
    run([sys.executable, "tools/build_release.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
