"""Verification that static analysis never invokes semantic/LLM providers.

Requirement: Static analysis must rely solely on AST parsing, static symbol resolution,
and graph metrics; it must never invoke semantic explanation providers or make external calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestruct.analysis import llm_summary
from codestruct.jobs.service import AnalysisService
from codestruct.settings import Settings

REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE = REPOSITORY / "sample_project"


def test_static_analysis_never_invokes_semantic_provider(tmp_path: Path) -> None:
    db_path = tmp_path / "test_static.sqlite3"
    settings = Settings(
        authorized_roots={"sample": SAMPLE},
        database_path=db_path,
    )
    service = AnalysisService(settings)

    # Patch explain_node and OpenAICompatibleExplainer to assert 0 calls
    with (
        patch.object(
            llm_summary, "explain_node", wraps=llm_summary.explain_node
        ) as mock_explain,
        patch.object(
            llm_summary.RuleBasedExplainer,
            "explain",
            wraps=llm_summary.RuleBasedExplainer.explain,
        ) as mock_rule_explain,
    ):
        record = service.create("sample", ".")
        job_id = record.analysis_id

        # Wait for terminal completion
        import time

        deadline = time.time() + 30.0
        terminal_record = None
        while time.time() < deadline:
            rec = service.registry.get(job_id)
            if rec and rec.state.value in ("completed", "failed", "cancelled"):
                terminal_record = rec
                break
            time.sleep(0.1)

        assert terminal_record is not None
        assert terminal_record.state.value == "completed"
        assert terminal_record.graph is not None

        # Verify static analysis produced nodes and edges
        assert len(terminal_record.graph.get("nodes", [])) > 0

        # Assert strict non-invocation of semantic providers during static analysis
        assert mock_explain.call_count == 0
        assert mock_rule_explain.call_count == 0

    service.shutdown()
