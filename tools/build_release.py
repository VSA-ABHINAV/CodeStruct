"""Build reproducible local artifacts in an isolated staging tree; never upload."""

from __future__ import annotations

import argparse
import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib

REPOSITORY = Path(__file__).resolve().parents[1]
OUTPUT = REPOSITORY / "release-output"
IGNORED = {
    ".git",
    ".venv",
    ".codestruct",
    ".codestruct-release-staging",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "dist",
    "coverage",
    "release-output",
    "__pycache__",
}


def run(
    command: list[str],
    cwd: Path,
    *,
    environment: dict[str, str] | None = None,
) -> None:
    subprocess.run(command, cwd=cwd, env=environment, check=True)  # noqa: S603


def source_version(path: Path) -> str:
    module = ast.parse(path.read_text("utf-8"), filename=path.name)
    for statement in module.body:
        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in statement.targets
            )
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            return statement.value.value
    raise ValueError("authoritative version assignment is missing")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-npm-ci",
        action="store_true",
        help="use only for an already verified staging dependency tree",
    )
    args = parser.parse_args()
    output = OUTPUT.resolve()
    if output.parent != REPOSITORY.resolve() or output.name != "release-output":
        raise SystemExit("refusing to use an unexpected release output path")
    OUTPUT.mkdir(exist_ok=True)
    for artifact in OUTPUT.glob("*"):
        if artifact.is_file():
            artifact.unlink()
    staging_root = (REPOSITORY / ".codestruct-release-staging").resolve()
    if (
        staging_root.parent != REPOSITORY.resolve()
        or staging_root.name != ".codestruct-release-staging"
    ):
        raise SystemExit("refusing to use an unexpected staging path")
    if staging_root.exists():
        raise SystemExit(
            "release staging already exists; inspect and remove it before retrying"
        )
    staging_root.mkdir()
    try:
        stage = staging_root / "source"
        shutil.copytree(REPOSITORY, stage, ignore=shutil.ignore_patterns(*IGNORED))
        frontend = stage / "frontend.lovable"
        if not args.skip_npm_ci:
            run(["npm.cmd" if os.name == "nt" else "npm", "ci"], frontend)
        environment = dict(os.environ)
        environment["CODESTRUCT_FRONTEND_BASE"] = "/app/"
        run(
            ["npm.cmd" if os.name == "nt" else "npm", "run", "build"],
            frontend,
            environment=environment,
        )
        built = frontend / "dist"
        if not built.joinpath("index.html").is_file():
            raise SystemExit("frontend build did not produce index.html")
        shutil.copytree(
            built, stage / "backend" / "src" / "codestruct" / "web", dirs_exist_ok=True
        )
        environment["SOURCE_DATE_EPOCH"] = environment.get("SOURCE_DATE_EPOCH", "0")
        run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                str(OUTPUT),
            ],
            stage,
            environment=environment,
        )
        project = tomllib.loads(stage.joinpath("pyproject.toml").read_text("utf-8"))
        if project["tool"]["setuptools"]["dynamic"]["version"]["attr"] != (
            "codestruct.__about__.__version__"
        ):
            raise SystemExit("unexpected authoritative version source")
        about = stage / "backend" / "src" / "codestruct" / "__about__.py"
        version = source_version(about)
        run(
            [
                sys.executable,
                str(stage / "tools" / "verify_artifacts.py"),
                str(OUTPUT),
                "--version",
                version,
            ],
            stage,
        )
    finally:
        shutil.rmtree(staging_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
