"""Production command-line entry point."""

from __future__ import annotations

import argparse
import importlib.metadata
import ipaddress
import os
import socket
import sqlite3
import sys
from pathlib import Path

from codestruct import __version__
from codestruct.settings import load_settings
from codestruct.storage.schema import SCHEMA_VERSION


def _host(value: str) -> str:
    if not value or any(char.isspace() for char in value):
        raise argparse.ArgumentTypeError("host must be a hostname or IP address")
    return value


def _port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _assets_ready() -> bool:
    return Path(__file__).with_name("web").joinpath("index.html").is_file()


def doctor(host: str, port: int) -> int:
    checks: list[tuple[str, bool, str]] = []
    supported_python = (3, 10) <= sys.version_info[:2] < (3, 15)
    checks.append(("python", supported_python, sys.version.split()[0]))
    try:
        installed = importlib.metadata.version("codestruct")
        checks.append(("package", installed == __version__, installed))
    except importlib.metadata.PackageNotFoundError:
        checks.append(("package", False, "metadata unavailable"))
    checks.append(
        ("frontend", _assets_ready(), "bundled" if _assets_ready() else "missing")
    )
    try:
        settings = load_settings()
    except (OSError, ValueError):
        settings = None
        checks.append(("configuration", False, "invalid or unavailable"))
    if settings is not None:
        checks.append(
            ("configuration", True, f"{len(settings.authorized_roots)} project(s)")
        )
    try:
        if settings is None:
            raise ValueError("configuration unavailable")
        database = settings.database_path
        if database is None:
            checks.append(("database", True, "in-memory mode configured"))
        else:
            database.parent.mkdir(parents=True, exist_ok=True)
            probe = database.parent / f".codestruct-write-{os.getpid()}"
            probe.touch(exist_ok=False)
            probe.unlink()
            if database.exists():
                connection = sqlite3.connect(
                    f"file:{database}?mode=ro", uri=True, timeout=2
                )
                try:
                    row = connection.execute(
                        "SELECT version FROM schema_metadata"
                    ).fetchone()
                finally:
                    connection.close()
                compatible = bool(row and 1 <= int(row[0]) <= SCHEMA_VERSION)
                checks.append(
                    ("database", compatible, f"schema {row[0] if row else 'missing'}")
                )
            else:
                checks.append(
                    ("database", True, "directory writable; database not created")
                )
    except (OSError, ValueError, sqlite3.Error):
        checks.append(("database", False, "invalid or unavailable"))
    available = True
    with socket.socket() as probe_socket:
        try:
            probe_socket.bind((host, port))
        except OSError:
            available = False
    checks.append(("port", available, "available" if available else "already in use"))
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
    return 0 if all(item[1] for item in checks) else 1


def serve(host: str, port: int, log_level: str) -> int:
    try:
        load_settings()
    except (OSError, ValueError) as error:
        print(
            f"CodeStruct configuration is invalid ({type(error).__name__}).",
            file=sys.stderr,
        )
        return 2
    if not _loopback(host):
        print(
            "WARNING: non-loopback binding has no built-in authentication or TLS; "
            "use an authenticated reverse proxy and isolation.",
            file=sys.stderr,
        )
    try:
        import uvicorn

        uvicorn.run("codestruct.api.app:app", host=host, port=port, log_level=log_level)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(
            f"CodeStruct failed to start safely: {type(error).__name__}",
            file=sys.stderr,
        )
        return 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="codestruct")
    result.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    commands = result.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser(
        "serve", help="serve the bundled local application"
    )
    serve_parser.add_argument("--host", type=_host, default="127.0.0.1")
    serve_parser.add_argument("--port", type=_port, default=8000)
    serve_parser.add_argument(
        "--log-level",
        choices=("critical", "error", "warning", "info", "debug"),
        default="info",
    )
    doctor_parser = commands.add_parser("doctor", help="run safe release diagnostics")
    doctor_parser.add_argument("--host", type=_host, default="127.0.0.1")
    doctor_parser.add_argument("--port", type=_port, default=8000)
    return result


def main() -> int:
    arguments = parser().parse_args()
    if arguments.command == "doctor":
        return doctor(arguments.host, arguments.port)
    return serve(arguments.host, arguments.port, arguments.log_level)


if __name__ == "__main__":
    raise SystemExit(main())
