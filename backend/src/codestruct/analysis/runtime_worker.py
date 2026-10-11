# ruff: noqa: S110
"""Isolated child process worker for executing opted-in target scripts under dynamic tracing."""

from __future__ import annotations

import io
import json
import runpy
import sys
from pathlib import Path
from typing import Any

from codestruct.analysis.dynamic_tracer import DynamicTracer, RuntimeTraceResult


class CappedStream(io.TextIOBase):
    """Limits total written bytes to prevent unbounded output memory consumption."""

    def __init__(self, target_stream: Any, max_bytes: int = 65536) -> None:
        self._target = target_stream
        self._max_bytes = max_bytes
        self._written = 0

    def write(self, s: str) -> int:
        if self._written >= self._max_bytes:
            return len(s)
        encoded = s.encode("utf-8", errors="replace")
        allowed = encoded[: max(0, self._max_bytes - self._written)]
        self._written += len(allowed)
        try:
            return self._target.write(allowed.decode("utf-8", errors="replace"))
        except Exception:
            return len(s)

    def flush(self) -> None:
        try:
            self._target.flush()
        except Exception:
            pass


def run_worker(payload_path: str) -> None:
    payload_file = Path(payload_path)
    if not payload_file.is_file():
        sys.stderr.write(f"Payload file not found: {payload_path}\n")
        sys.exit(1)

    try:
        with open(payload_file, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        sys.stderr.write(f"Failed to load payload: {e}\n")
        sys.exit(1)

    project_root = Path(payload["project_root"]).resolve()
    target_file = Path(payload["target_file"]).resolve()
    entry_function = payload.get("entry_function")
    args = payload.get("args") or []
    max_events = int(payload.get("max_events", 50000))
    max_output_bytes = int(payload.get("max_output_bytes", 65536))
    result_file = Path(payload["result_file"]).resolve()

    # Cap stdout and stderr
    sys.stdout = CappedStream(sys.stdout, max_bytes=max_output_bytes)
    sys.stderr = CappedStream(sys.stderr, max_bytes=max_output_bytes)

    # Setup environment
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    sys.argv = [str(target_file)] + list(args)

    tracer = DynamicTracer(
        authorized_roots=(project_root,),
        max_events=max_events,
    )

    success = False
    error_msg: str | None = None
    trace: RuntimeTraceResult | None = None

    tracer.start()
    try:
        mod_globals = runpy.run_path(str(target_file), run_name="__main__")
        if (
            entry_function
            and entry_function in mod_globals
            and callable(mod_globals[entry_function])
        ):
            mod_globals[entry_function]()
        success = True
    except Exception as exc:
        error_msg = str(exc)
        success = False
    finally:
        trace = tracer.stop()

    if trace is None:
        trace = RuntimeTraceResult(
            events=(),
            total_calls=0,
            execution_time_seconds=0.0,
            overhead_seconds=0.0,
            threads_observed=(),
            exceptions_observed=0,
        )

    out_data = {
        "success": success,
        "error": error_msg,
        "total_calls": trace.total_calls,
        "execution_time_seconds": trace.execution_time_seconds,
        "overhead_seconds": trace.overhead_seconds,
        "threads_observed": list(trace.threads_observed),
        "exceptions_observed": trace.exceptions_observed,
        "events": [
            {
                "caller_file": e.caller_file,
                "caller_name": e.caller_name,
                "caller_line": e.caller_line,
                "callee_file": e.callee_file,
                "callee_name": e.callee_name,
                "callee_line": e.callee_line,
                "call_count": e.call_count,
                "thread_id": e.thread_id,
                "has_exception": e.has_exception,
                "duration_seconds": e.duration_seconds,
            }
            for e in trace.events
        ],
    }

    try:
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=2)
    except Exception as e:
        sys.stderr.write(f"Failed to write result file: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write(
            "Usage: python -m codestruct.analysis.runtime_worker <payload_file>\n"
        )
        sys.exit(1)
    run_worker(sys.argv[1])
