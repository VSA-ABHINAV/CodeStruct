from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from codestruct.jobs.models import TERMINAL_STATES, JobState
from codestruct.jobs.service import AnalysisService
from codestruct.settings import Settings

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"
OUTPUT = REPOSITORY / "tests" / "test-output"


def wait(service: AnalysisService, analysis_id: str, timeout: float = 20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = service.get(analysis_id)
        if record.state in TERMINAL_STATES:
            return record
        time.sleep(0.05)
    raise TimeoutError("analysis did not become terminal")


class CacheIntegrationTests(unittest.TestCase):
    def test_cold_warm_refresh_and_restart(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=OUTPUT) as directory:
            database = Path(directory) / "cache.sqlite3"
            settings = Settings(
                authorized_roots={"sample": SAMPLE},
                database_path=database,
                max_concurrent_jobs=1,
                max_queued_jobs=2,
                analysis_timeout_seconds=20,
                cancellation_grace_seconds=1,
                result_retention_seconds=60,
                polling_interval_ms=250,
            )
            first_service = AnalysisService(settings)
            try:
                cold = wait(
                    first_service, first_service.create("sample", ".").analysis_id
                )
                self.assertEqual(cold.state, JobState.COMPLETED)
                self.assertFalse(cold.cache_hit)
                warm = first_service.create("sample", ".")
                self.assertTrue(warm.cache_hit)
                self.assertEqual(warm.graph, cold.graph)
                refreshed = wait(
                    first_service,
                    first_service.create("sample", ".", refresh=True).analysis_id,
                )
                self.assertFalse(refreshed.cache_hit)
                graph = refreshed.graph
                analysis_id = refreshed.analysis_id
            finally:
                first_service.shutdown()
            reopened = AnalysisService(settings)
            try:
                self.assertEqual(reopened.get(analysis_id).graph, graph)
                warm_after_restart = reopened.create("sample", ".")
                self.assertTrue(warm_after_restart.cache_hit)
            finally:
                reopened.shutdown()
                import gc

                gc.collect()
                time.sleep(0.1)

    def test_metrics_option_metadata_and_cache(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=OUTPUT) as directory:
            database = Path(directory) / "cache_metrics.sqlite3"
            settings = Settings(
                authorized_roots={"sample": SAMPLE},
                database_path=database,
                max_concurrent_jobs=1,
                max_queued_jobs=2,
                analysis_timeout_seconds=20,
                cancellation_grace_seconds=1,
                result_retention_seconds=60,
                polling_interval_ms=250,
            )
            service = AnalysisService(settings)
            try:
                # 1. Without metrics
                job_false = wait(
                    service,
                    service.create("sample", ".", compute_metrics=False).analysis_id,
                )
                self.assertEqual(job_false.state, JobState.COMPLETED)
                self.assertFalse(job_false.cache_hit)
                self.assertFalse(job_false.graph["metadata"]["metrics_computed"])

                # 2. With metrics
                job_true = wait(
                    service,
                    service.create("sample", ".", compute_metrics=True).analysis_id,
                )
                self.assertEqual(job_true.state, JobState.COMPLETED)
                self.assertFalse(job_true.cache_hit)
                self.assertTrue(job_true.graph["metadata"]["metrics_computed"])

                # 3. Cache hit on metrics=True
                job_true_warm = service.create("sample", ".", compute_metrics=True)
                self.assertTrue(job_true_warm.cache_hit)
                self.assertTrue(job_true_warm.graph["metadata"]["metrics_computed"])
            finally:
                service.shutdown()


if __name__ == "__main__":
    unittest.main()
