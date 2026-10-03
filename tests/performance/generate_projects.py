"""Deterministic, side-effect-free synthetic Python benchmark projects."""

from __future__ import annotations

from pathlib import Path


def generate_project(
    root: Path, files: int, *, dense_cycle: int = 0, definitions: int = 3
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(files):
        package = root / f"pkg_{index // 100:03d}"
        package.mkdir(exist_ok=True)
        init = package / "__init__.py"
        if not init.exists():
            init.write_text('"""Synthetic package."""\n', encoding="utf-8")
        imports = []
        if index:
            imports.append(
                f"import pkg_{(index - 1) // 100:03d}.module_{index - 1:05d}\n"
            )
        if dense_cycle and index < dense_cycle:
            imports.extend(
                f"import pkg_{target // 100:03d}.module_{target:05d}\n"
                for target in range(dense_cycle)
                if target != index
            )
        body = [
            *imports,
            f"class Type{index}:\n    def method(self):\n        return helper_{index}()\n\n",
        ]
        body.extend(
            f"def helper_{index}_{item}(value=None):\n    return value\n\n"
            for item in range(definitions)
        )
        body.append(f"def helper_{index}():\n    return {index}\n")
        (package / f"module_{index:05d}.py").write_text("".join(body), encoding="utf-8")


def add_partial_file(root: Path) -> None:
    (root / "broken.py").write_text("def incomplete(\n", encoding="utf-8")
