"""Exercise an installed wheel through its console entry point and HTTP API."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def request(
    base: str, path: str, method: str = "GET", body: dict[str, object] | None = None
) -> tuple[int, dict[str, object]]:
    data = None if body is None else json.dumps(body).encode()
    call = urllib.request.Request(  # noqa: S310
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(call, timeout=5) as response:  # noqa: S310
            payload = response.read()
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError:
                decoded = {"text": payload.decode("utf-8", errors="replace")}
            return response.status, decoded
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def start(console: Path, work: Path, environment: dict[str, str], port: int):
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(  # noqa: S603
        [str(console), "serve", "--port", str(port), "--log-level", "warning"],
        cwd=work,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)


def wait_ready(base: str) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            if request(base, "/health/ready")[0] == 200:
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise TimeoutError("packaged server did not become ready")


def wait_terminal(base: str, analysis_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, job = request(base, f"/api/v1/analyses/{analysis_id}")
        if status == 200 and job.get("terminal"):
            return job
        time.sleep(0.1)
    raise TimeoutError("packaged analysis did not reach a terminal state")


def submit(base: str, root_id: str) -> tuple[int, dict[str, object]]:
    return request(
        base,
        "/api/v1/analyses",
        "POST",
        {
            "project": {"root_id": root_id, "relative_path": "."},
            "options": {"metrics": False},
            "refresh": False,
        },
    )


def main() -> int:
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--console", required=True, type=Path)
    arguments.add_argument("--work", required=True, type=Path)
    arguments.add_argument("--sample", required=True, type=Path)
    args = arguments.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    cancel_project = args.work / "Cancellation Project"
    cancel_project.mkdir(exist_ok=True)
    for index in range(400):
        cancel_project.joinpath(f"module_{index:04d}.py").write_text(
            f"VALUE_{index} = {index}\n", encoding="utf-8"
        )
    environment = dict(os.environ)
    environment["CODESTRUCT_AUTHORIZED_ROOTS"] = os.pathsep.join(
        (f"sample={args.sample}", f"cancel={cancel_project}")
    )
    environment["CODESTRUCT_DATABASE_PATH"] = str(
        args.work / "Runtime Data" / "db.sqlite3"
    )
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    process = start(args.console, args.work, environment, port)
    try:
        wait_ready(base)
        assert request(base, "/app/")[0] == 200
        assert request(base, "/api/v1/version")[1]["version"] == "0.1.0.dev0"
        projects = request(base, "/api/v1/projects")[1]["projects"]
        assert {item["id"] for item in projects} == {"sample", "cancel"}
        status, created = submit(base, "sample")
        assert status == 202
        analysis_id = str(created["analysis_id"])
        completed = wait_terminal(base, analysis_id)
        if completed["state"] not in {"completed", "partially_completed"}:
            raise AssertionError(
                f"packaged analysis failed with state {completed['state']} "
                f"and message {completed['progress']['message_code']}"
            )
        graph_status, graph = request(
            base, f"/api/v1/analyses/{analysis_id}/graph?limit=100"
        )
        assert graph_status == 200 and graph["nodes"]
        assert request(base, f"/api/v1/analyses/{analysis_id}/diagnostics")[0] == 200
        cache_status, cached = submit(base, "sample")
        assert cache_status == 200 and cached["cache_hit"] is True
        cancel_status, cancelling = submit(base, "cancel")
        assert cancel_status == 202
        cancelled_id = str(cancelling["analysis_id"])
        assert request(base, f"/api/v1/analyses/{cancelled_id}", "DELETE")[0] in {
            200,
            202,
        }
        cancelled = wait_terminal(base, cancelled_id)
        assert cancelled["state"] == "cancelled"
    finally:
        stop(process)

    restarted = start(args.console, args.work, environment, port)
    try:
        wait_ready(base)
        recovered_status, recovered = request(base, f"/api/v1/analyses/{analysis_id}")
        assert recovered_status == 200 and recovered["terminal"] is True
        assert (
            request(base, f"/api/v1/analyses/{analysis_id}/graph?limit=100")[0] == 200
        )
    finally:
        stop(restarted)
    print(
        json.dumps(
            {
                "version": "0.1.0.dev0",
                "frontend": "served",
                "analysis": completed["state"],
                "cache_hit": True,
                "cancellation": "cancelled",
                "restart_recovery": True,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
