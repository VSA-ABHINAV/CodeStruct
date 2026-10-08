"""Bounded coordinator for one fresh spawned process per analysis."""

from __future__ import annotations

import logging
import multiprocessing
import time
from pathlib import Path
from queue import Empty
from threading import Event, RLock, Semaphore, Thread
from typing import Any

from codestruct.analysis import AnalysisPolicy
from codestruct.storage.cache_keys import (
    cache_key,
    policy_fingerprint,
    project_fingerprint,
)
from codestruct.storage.interfaces import JobRepository

from .models import JobState
from .registry import InvalidTransitionError
from .worker import run_analysis_worker

logger = logging.getLogger(__name__)


class QueueFullError(RuntimeError):
    pass


class SpawnJobExecutor:
    def __init__(
        self,
        registry: JobRepository,
        *,
        max_workers: int,
        max_queued: int,
        timeout_seconds: int,
        cancellation_grace_seconds: int,
    ) -> None:
        self.registry = registry
        self._slots = Semaphore(max_workers)
        self._capacity = max_workers + max_queued
        self._timeout = timeout_seconds
        self._grace = cancellation_grace_seconds
        self._lock = RLock()
        self._controllers: dict[str, tuple[Any, Any | None, Thread]] = {}
        self._shutdown = Event()

    @property
    def available(self) -> bool:
        """Report whether this local executor can accept lifecycle work."""
        return not self._shutdown.is_set()

    def submit(
        self, analysis_id: str, project_root: str, policy: AnalysisPolicy
    ) -> None:
        with self._lock:
            if len(self._controllers) >= self._capacity:
                raise QueueFullError("analysis queue is full")
            cancel_requested = multiprocessing.get_context("spawn").Event()
            thread = Thread(
                target=self._supervise,
                args=(analysis_id, project_root, policy, cancel_requested),
                daemon=True,
                name=f"codestruct-{analysis_id[:8]}",
            )
            self._controllers[analysis_id] = (cancel_requested, None, thread)
            thread.start()

    def cancel(self, analysis_id: str) -> None:
        with self._lock:
            controller = self._controllers.get(analysis_id)
            if controller:
                controller[0].set()

    def _supervise(
        self,
        analysis_id: str,
        project_root: str,
        policy: AnalysisPolicy,
        cancel: Any,
    ) -> None:
        acquired = False
        process = None
        context = multiprocessing.get_context("spawn")
        try:
            while not self._shutdown.is_set() and not cancel.is_set():
                acquired = self._slots.acquire(timeout=0.1)
                if acquired:
                    break
            if cancel.is_set() or self._shutdown.is_set():
                self.registry.transition(
                    analysis_id, JobState.CANCELLED, message_code="ANALYSIS_CANCELLED"
                )
                return
            current = self.registry.get(analysis_id)
            if current and current.state is JobState.CANCELLATION_REQUESTED:
                self.registry.transition(
                    analysis_id, JobState.CANCELLED, message_code="ANALYSIS_CANCELLED"
                )
                return
            self.registry.transition(
                analysis_id,
                JobState.SCANNING,
                percent=10,
                message_code="SCANNING_PROJECT",
            )
            progress = context.Queue()
            output = context.Queue(maxsize=1)
            data = {
                "authorized_roots": [str(value) for value in policy.authorized_roots],
                "include_patterns": list(policy.include_patterns),
                "exclude_patterns": list(policy.exclude_patterns),
                "max_depth": policy.max_depth,
                "max_files": policy.max_files,
                "max_file_size": policy.max_file_size,
                "single_file_name": policy.single_file_name,
                "compute_metrics": policy.compute_metrics,
            }

            process = context.Process(
                target=run_analysis_worker,
                args=(project_root, data, progress, cancel, output),
                name=f"codestruct-worker-{analysis_id[:8]}",
            )
            with self._lock:
                old = self._controllers[analysis_id]
                self._controllers[analysis_id] = (old[0], process, old[2])
            process.start()
            deadline = time.monotonic() + self._timeout
            result: dict[str, Any] | None = None
            while process.is_alive():
                try:
                    while True:
                        stage, percent, code = progress.get_nowait()
                        try:
                            self.registry.transition(
                                analysis_id,
                                JobState(stage),
                                percent=percent,
                                message_code=code,
                            )
                        except InvalidTransitionError:
                            pass
                except Empty:
                    pass
                if cancel.is_set() or self._shutdown.is_set():
                    process.join(self._grace)
                    if process.is_alive():
                        process.terminate()
                    process.join(2)
                    self.registry.transition(
                        analysis_id,
                        JobState.CANCELLED,
                        message_code="ANALYSIS_CANCELLED",
                    )
                    return
                if time.monotonic() >= deadline:
                    cancel.set()
                    process.join(self._grace)
                    if process.is_alive():
                        process.terminate()
                    process.join(2)
                    self.registry.transition(
                        analysis_id,
                        JobState.FAILED,
                        message_code="POLICY_TIME_LIMIT",
                        error_code="ANALYSIS_TIMEOUT",
                        error_message="The analysis exceeded its configured time limit.",
                    )
                    return
                try:
                    result = output.get(timeout=0.05)
                except Empty:
                    continue
                break
            process.join(1)
            # A fast worker can finish before the supervising thread observes
            # every milestone. Drain those ordered messages before committing
            # the terminal result so state transitions remain valid.
            try:
                while True:
                    stage, percent, code = progress.get_nowait()
                    self.registry.transition(
                        analysis_id, JobState(stage), percent=percent, message_code=code
                    )
            except Empty:
                pass
            if result is None:
                try:
                    result = output.get(timeout=0.2)
                except Empty:
                    result = {
                        "kind": "error",
                        "code": "WORKER_EXITED",
                        "message": "The analysis worker exited before producing a result.",
                    }
            if result["kind"] == "cancelled":
                self.registry.transition(
                    analysis_id, JobState.CANCELLED, message_code="ANALYSIS_CANCELLED"
                )
            elif result["kind"] == "result":
                graph = result["graph"]
                state = (
                    JobState.PARTIALLY_COMPLETED
                    if result["partial"]
                    else JobState.COMPLETED
                )
                current_record = self.registry.get(analysis_id)
                if (
                    not result["partial"]
                    and current_record
                    and current_record.cache_key
                    and hasattr(self.registry, "store_cache")
                ):
                    policy_hash = policy_fingerprint(policy)
                    current_project_hash = project_fingerprint(
                        Path(project_root), policy
                    )
                    if policy.single_file_name:
                        relative = policy.single_file_name
                    else:
                        relative = "."
                        for authorized in policy.authorized_roots:
                            try:
                                candidate = (
                                    Path(project_root)
                                    .relative_to(authorized)
                                    .as_posix()
                                )
                                relative = candidate or "."
                                break
                            except ValueError:
                                continue
                    expected = cache_key(
                        current_record.root_id,
                        relative,
                        current_project_hash,
                        policy_hash,
                    )
                    if expected == current_record.cache_key:
                        self.registry.store_cache(
                            current_record.cache_key,
                            graph,
                            policy_hash,
                            current_project_hash,
                        )
                self.registry.transition(
                    analysis_id,
                    state,
                    percent=100,
                    message_code="ANALYSIS_PARTIAL"
                    if result["partial"]
                    else "ANALYSIS_COMPLETED",
                    graph=graph,
                    diagnostics=list(graph.get("diagnostics", [])),
                )
                summary = graph.get("summary", {})
                logger.info(
                    "codestruct.analysis.completed analysis_id=%s state=%s files=%s nodes=%s edges=%s",
                    analysis_id,
                    state.value,
                    summary.get("source_units_total"),
                    summary.get("nodes_total"),
                    summary.get("edges_total"),
                )
                logger.info(
                    "event=analysis_completed analysis_id=%s stage=completed cache_hit=false files=%s nodes=%s edges=%s",
                    analysis_id,
                    summary.get("source_units_total", 0),
                    summary.get("nodes_total", 0),
                    summary.get("edges_total", 0),
                )
            else:
                self.registry.transition(
                    analysis_id,
                    JobState.FAILED,
                    message_code=result["code"],
                    error_code=result["code"],
                    error_message=result["message"],
                )
        except BaseException as error:
            logger.exception(
                "codestruct.analysis.executor_failed analysis_id=%s error_category=%s error=%s",
                analysis_id,
                type(error).__name__,
                error,
            )
            try:
                self.registry.transition(
                    analysis_id,
                    JobState.FAILED,
                    message_code="EXECUTOR_FAILED",
                    error_code="EXECUTOR_FAILED",
                    error_message="The analysis executor could not complete safely.",
                )
            except (KeyError, InvalidTransitionError):
                pass
        finally:
            if process is not None and process.is_alive():
                process.terminate()
                process.join(2)
            if acquired:
                self._slots.release()
            with self._lock:
                self._controllers.pop(analysis_id, None)

    def shutdown(self) -> None:
        self._shutdown.set()
        with self._lock:
            controllers = list(self._controllers.values())
        for cancel, process, _thread in controllers:
            cancel.set()
            if process is not None and process.is_alive():
                process.join(self._grace)
                if process.is_alive():
                    process.terminate()
                process.join(2)
