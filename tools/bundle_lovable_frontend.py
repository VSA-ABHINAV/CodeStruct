"""Copy the verified Lovable SPA build to FastAPI's local /app asset directory."""

import shutil
from pathlib import Path


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    source = repository / "frontend.lovable" / "dist"
    target = repository / "backend" / "src" / "codestruct" / "web"
    if not (source / "index.html").is_file():
        raise SystemExit(
            "Build frontend.lovable with CODESTRUCT_FRONTEND_BASE=/app/ first."
        )
    if "/app/assets/" not in (source / "index.html").read_text(encoding="utf-8"):
        raise SystemExit("Refusing to bundle assets built without the /app/ base.")
    backup = repository / ".codestruct" / "lovable-integration-backup"
    if (target / "index.html").exists() and not (backup / "index.html").exists():
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target / "index.html", backup / "index.html")
    # Retain prior hashed assets and any user files. Only generated current files are copied.
    shutil.copytree(source, target, dirs_exist_ok=True)
    print("Bundled Lovable frontend for /app; previous entry point backed up locally.")


if __name__ == "__main__":
    main()
