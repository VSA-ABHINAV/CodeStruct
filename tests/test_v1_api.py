from __future__ import annotations

import time
import unittest
from dataclasses import replace
from pathlib import Path

from codestruct.api.app import create_app
from codestruct.api.schemas import CreateAnalysisRequest
from codestruct.jobs.models import JobRecord, JobState
from codestruct.jobs.registry import InvalidTransitionError, JobRegistry
from codestruct.jobs.service import AnalysisService, ProjectSelectionError
from codestruct.settings import Settings, _paths
from pydantic import ValidationError

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"
PARSER_FIXTURE = REPOSITORY / "tests" / "fixtures" / "parser_project"


class RegistryTests(unittest.TestCase):
    def test_transitions_are_monotonic_and_terminal_states_are_immutable(self):
        registry = JobRegistry(60)
        registry.add(JobRecord("ana_test", "sample", str(SAMPLE)))
        registry.transition("ana_test", JobState.VALIDATING, percent=5)
        with self.assertRaises(InvalidTransitionError):
            registry.transition("ana_test", JobState.QUEUED, percent=4)
        registry.transition("ana_test", JobState.QUEUED, percent=10)
        registry.transition("ana_test", JobState.SCANNING, percent=20)
        registry.transition("ana_test", JobState.PARSING, percent=40)
        registry.transition("ana_test", JobState.RESOLVING, percent=60)
        registry.transition("ana_test", JobState.BUILDING_GRAPH, percent=80)
        registry.transition("ana_test", JobState.COMPLETED, percent=100)
        with self.assertRaises(InvalidTransitionError):
            registry.transition("ana_test", JobState.FAILED)

    def test_expired_results_leave_a_tombstone(self):
        registry = JobRegistry(60)
        record = JobRecord("ana_expired", "sample", str(SAMPLE))
        record.expires_at_epoch = time.time() - 1
        registry.add(record)
        self.assertEqual(registry.cleanup_expired(), 1)
        self.assertIsNone(registry.get("ana_expired"))
        self.assertTrue(registry.is_expired("ana_expired"))


class ApiIntegrationTests(unittest.TestCase):
    def settings(self, root: Path = SAMPLE) -> Settings:
        return Settings(
            authorized_roots={"sample": root},
            max_concurrent_jobs=1,
            max_queued_jobs=2,
            analysis_timeout_seconds=20,
            cancellation_grace_seconds=1,
            result_retention_seconds=60,
            polling_interval_ms=250,
        )

    def test_security_validation_and_cors_configuration(self):
        service = AnalysisService(self.settings())
        try:
            with self.assertRaises(ProjectSelectionError) as escaped:
                service.resolve_project("sample", "..")
            self.assertEqual(escaped.exception.code, "PROJECT_UNAUTHORIZED")
            self.assertNotIn(str(REPOSITORY), str(escaped.exception))
            with self.assertRaises(ValidationError):
                CreateAnalysisRequest.model_validate(
                    {
                        "project": {"root_id": "sample", "relative_path": "."},
                        "unknown": True,
                    }
                )
            app = create_app(self.settings())
            cors = next(
                item
                for item in app.user_middleware
                if item.cls.__name__ == "CORSMiddleware"
            )
            self.assertNotIn("*", cors.kwargs["allow_origins"])
            self.assertFalse(cors.kwargs["allow_credentials"])
            app.state.analysis_service.shutdown()
        finally:
            service.shutdown()

    def test_project_discovery_exposes_capabilities_without_server_paths(self):
        from fastapi.testclient import TestClient

        app = create_app(self.settings())
        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/projects")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json()["projects"],
                [
                    {
                        "id": "sample",
                        "display_name": "Sample",
                        "description": None,
                        "available": True,
                    }
                ],
            )
            self.assertNotIn(str(SAMPLE), response.text)
        finally:
            app.state.analysis_service.shutdown()

    def test_authorized_root_configuration_rejects_duplicate_alias_and_location(self):
        separator = __import__("os").pathsep
        with self.assertRaisesRegex(ValueError, "aliases must be unique"):
            _paths(f"one={SAMPLE}{separator}one={PARSER_FIXTURE}", SAMPLE)
        with self.assertRaisesRegex(ValueError, "locations must be unique"):
            _paths(f"one={SAMPLE}{separator}two={SAMPLE}", SAMPLE)
        with self.assertRaisesRegex(ValueError, "aliases must use"):
            _paths(f"bad alias={SAMPLE}", SAMPLE)
        with self.assertRaisesRegex(ValueError, "existing directory"):
            _paths(f"missing={REPOSITORY / 'does-not-exist'}", SAMPLE)

    def test_large_graph_requires_and_caps_bounded_retrieval(self):
        from fastapi.testclient import TestClient

        configuration = self.settings()
        configuration = replace(
            configuration, max_full_graph_bytes=64, max_graph_page_size=2
        )
        app = create_app(configuration)
        graph = {
            "schema_version": "1.0.0",
            "metadata": {"graph_id": "graph-test"},
            "summary": {},
            "nodes": [
                {"id": f"node-{index}", "kind": "module", "name": f"module-{index}"}
                for index in range(3)
            ],
            "edges": [],
            "evidence": [],
            "diagnostics": [],
        }
        app.state.analysis_service.registry.add(
            JobRecord(
                "ana_large",
                "sample",
                str(SAMPLE),
                state=JobState.COMPLETED,
                percent=100,
                graph=graph,
            )
        )
        try:
            with TestClient(app) as client:
                self.assertEqual(
                    client.get("/api/v1/analyses/ana_large/graph").status_code, 413
                )
                self.assertEqual(
                    client.get(
                        "/api/v1/analyses/ana_large/graph", params={"limit": 3}
                    ).json()["error"]["code"],
                    "PAGE_LIMIT_EXCEEDED",
                )
                page = client.get(
                    "/api/v1/analyses/ana_large/graph", params={"limit": 2}
                )
            self.assertEqual(page.status_code, 200)
            self.assertTrue(page.json()["page"]["partial_load"])
            self.assertEqual(page.json()["page"]["total_nodes"], 3)
        finally:
            app.state.analysis_service.shutdown()

    def test_spawned_analysis_graph_diagnostics_and_non_execution(self):
        marker = PARSER_FIXTURE / "CODESTRUCT_FIXTURE_EXECUTED"
        self.assertFalse(marker.exists())
        service = AnalysisService(self.settings(PARSER_FIXTURE))
        try:
            created = service.create("sample", ".")
            analysis_id = created.analysis_id
            states = [created.state.value]
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                current = service.get(analysis_id)
                self.assertIsNotNone(current)
                states.append(current.state.value)
                if current.state in {
                    JobState.COMPLETED,
                    JobState.PARTIALLY_COMPLETED,
                    JobState.FAILED,
                    JobState.CANCELLED,
                }:
                    break
                time.sleep(0.05)
            self.assertIn(
                states[-1],
                {"completed", "partially_completed"},
                (states, current.error_code, current.error_message),
            )
            current = service.get(analysis_id)
            self.assertEqual(current.graph["schema_version"], "1.0.0")
            self.assertNotIn(str(REPOSITORY), str(current.graph))
            self.assertTrue(
                any(item["code"] == "FILE_SYNTAX_ERROR" for item in current.diagnostics)
            )
        finally:
            service.shutdown()
        self.assertFalse(marker.exists())

    def test_spawned_cancellation_is_idempotent_and_reaches_terminal_state(self):
        service = AnalysisService(self.settings(PARSER_FIXTURE))
        try:
            created = service.create("sample", ".")
            first = service.cancel(created.analysis_id)
            second = service.cancel(created.analysis_id)
            self.assertIn(
                first.state, {JobState.CANCELLATION_REQUESTED, JobState.CANCELLED}
            )
            self.assertIn(
                second.state, {JobState.CANCELLATION_REQUESTED, JobState.CANCELLED}
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                current = service.get(created.analysis_id)
                if current.state is JobState.CANCELLED:
                    break
                time.sleep(0.05)
            self.assertEqual(current.state, JobState.CANCELLED)
        finally:
            service.shutdown()


if __name__ == "__main__":
    unittest.main()
