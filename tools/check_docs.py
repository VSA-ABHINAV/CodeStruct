"""Check local Markdown links and balanced Mermaid fences."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


def main() -> int:
    failures: list[str] = []
    files = sorted([ROOT / "README.md", *ROOT.joinpath("docs").rglob("*.md")])
    for document in files:
        content = document.read_text("utf-8")
        if content.count("```") % 2:
            failures.append(f"unbalanced code fence: {document.relative_to(ROOT)}")
        for raw in LINK.findall(content):
            target = raw.split("#", 1)[0].strip().strip("<>")
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                failures.append(
                    f"missing link in {document.relative_to(ROOT)}: {target}"
                )
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"PASS: {len(files)} Markdown files have resolvable local links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
