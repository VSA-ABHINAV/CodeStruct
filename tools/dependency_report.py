"""Write review-only direct-dependency metadata without inferring licenses."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "release-output" / "dependency-report.json"


def python_dependencies() -> list[dict[str, str | None]]:
    results = []
    for name in ("fastapi", "pydantic", "uvicorn"):
        distribution = importlib.metadata.distribution(name)
        results.append(
            {
                "name": name,
                "version": distribution.version,
                "license_expression": distribution.metadata.get("License-Expression"),
                "license_field": distribution.metadata.get("License"),
            }
        )
    return results


def npm_dependencies() -> list[dict[str, str | None]]:
    lock = json.loads(ROOT.joinpath("frontend/package-lock.json").read_text("utf-8"))
    direct = lock["packages"][""]["dependencies"]
    results = []
    for name in sorted(direct):
        entry = lock["packages"].get(f"node_modules/{name}", {})
        results.append(
            {
                "name": name,
                "version": entry.get("version"),
                "license": entry.get("license"),
            }
        )
    return results


def main() -> int:
    OUTPUT.parent.mkdir(exist_ok=True)
    report = {
        "scope": "direct runtime dependencies only; legal approval not implied",
        "python": python_dependencies(),
        "npm": npm_dependencies(),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
