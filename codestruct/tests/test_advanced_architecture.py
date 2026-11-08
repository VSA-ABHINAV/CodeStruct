"""Tests for Phase 19: Advanced Architecture (AST + LLM Component Clustering & Narrative Generation).

Covers all 5 Test Procedures specified in prompt.md:
1. Validator Unit Test — Invented Symbol ID (Mocked): dropped and logged.
2. Validator Unit Test — Omitted Real Symbol (Mocked): surfaced in unclustered_symbol_ids.
3. Integration Test — /api/architecture/advanced with Mocked LLM.
4. Live Qualitative Run (Unmocked) against sample_project (logged, not gated).
5. Cache Reuse Confirmation: LLM invoked only once across repeated calls.
"""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure codestruct package root is in sys.path
TESTS_DIR = Path(__file__).resolve().parent
CODESTRUCT_DIR = TESTS_DIR.parent
if str(CODESTRUCT_DIR) not in sys.path:
    sys.path.insert(0, str(CODESTRUCT_DIR))

from backend.advanced_architecture import (
    MalformedLLMOutputError,
    clear_architecture_cache,
    cluster_architecture,
    validate_clustering,
)
from backend.main import app
from backend.schemas import AdvancedArchitectureResponse

SAMPLE_PROJECT_DIR = CODESTRUCT_DIR / "sample_project"


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear architecture cache before each test."""
    clear_architecture_cache()
    yield
    clear_architecture_cache()


@pytest.fixture(scope="module")
def client():
    """Create a TestClient instance for the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Test Procedure 1: Validator Unit Test — Invented Symbol ID (Mocked)
# ---------------------------------------------------------------------------

def test_validator_drops_invented_symbol_id(caplog):
    """Validator drops and logs invented symbol IDs while preserving valid components."""
    real_node_ids = {
        "sample_project",
        "sample_project.Animal",
        "sample_project.Animal.__init__",
        "sample_project.Animal.speak",
        "sample_project.Animal.describe",
        "sample_project.Dog",
        "sample_project.Dog.__init__",
        "sample_project.Dog.speak",
        "sample_project.Dog.fetch",
        "sample_project.Cat",
        "sample_project.Cat.__init__",
        "sample_project.Cat.speak",
        "sample_project.Zoo",
        "sample_project.Zoo.__init__",
        "sample_project.Zoo.add_animal",
        "sample_project.build_zoo",
    }

    mock_llm_response = {
        "components": [
            {
                "component_id": "comp_1",
                "name": "Animal Hierarchy",
                "member_symbol_ids": [
                    "sample_project.Animal",
                    "sample_project.Dog",
                    "sample_project.Cat",
                    "sample_project.NonExistentClass",  # Invented ID!
                    "sample_project.ImaginaryService",  # Invented ID!
                ],
                "role": "Domain Entities",
                "rationale": "Core domain models and inheritance hierarchy",
            },
            {
                "component_id": "comp_2",
                "name": "Zoo Management",
                "member_symbol_ids": [
                    "sample_project.Zoo",
                    "sample_project.build_zoo",
                    "sample_project.FakeMethod",  # Invented ID!
                ],
                "role": "Service Container",
                "rationale": "Orchestrates animals and builds collection",
            },
        ],
        "unclustered_symbol_ids": ["sample_project.GhostSymbol"],  # Invented ID!
        "narrative": "A simple animal management system demonstrating inheritance and polymorphism.",
    }

    with caplog.at_level(logging.WARNING):
        validated, dropped_ids = validate_clustering(mock_llm_response, real_node_ids)

    # 1. Assert invented IDs are dropped
    assert "sample_project.NonExistentClass" in dropped_ids
    assert "sample_project.ImaginaryService" in dropped_ids
    assert "sample_project.FakeMethod" in dropped_ids
    assert "sample_project.GhostSymbol" in dropped_ids
    assert len(dropped_ids) == 4

    # 2. Assert logged
    log_text = caplog.text
    assert "Dropping invented symbol ID: 'sample_project.NonExistentClass'" in log_text
    assert "Dropping invented symbol ID: 'sample_project.ImaginaryService'" in log_text
    assert "Dropping invented symbol ID: 'sample_project.FakeMethod'" in log_text
    assert "Dropping invented symbol ID from unclustered list: 'sample_project.GhostSymbol'" in log_text

    # 3. Assert valid components still present with ONLY real IDs
    assert len(validated["components"]) == 2
    comp1 = validated["components"][0]
    assert comp1["component_id"] == "comp_1"
    assert comp1["name"] == "Animal Hierarchy"
    assert set(comp1["member_symbol_ids"]) == {
        "sample_project.Animal",
        "sample_project.Dog",
        "sample_project.Cat",
    }
    assert "sample_project.NonExistentClass" not in comp1["member_symbol_ids"]

    comp2 = validated["components"][1]
    assert set(comp2["member_symbol_ids"]) == {
        "sample_project.Zoo",
        "sample_project.build_zoo",
    }
    assert "sample_project.FakeMethod" not in comp2["member_symbol_ids"]

    # 4. Assert narrative preserved
    assert validated["narrative"] == mock_llm_response["narrative"]


# ---------------------------------------------------------------------------
# Test Procedure 2: Validator Unit Test — Omitted Real Symbol (Mocked)
# ---------------------------------------------------------------------------

def test_validator_surfaces_omitted_real_symbols():
    """Validator surfaces omitted real symbols in unclustered_symbol_ids rather than losing them."""
    real_node_ids = {
        "sample_project.Animal",
        "sample_project.Dog",
        "sample_project.Cat",
        "sample_project.Zoo",
    }

    # Mock LLM omits "sample_project.Animal" from all components and unclustered
    mock_llm_response = {
        "components": [
            {
                "component_id": "comp_1",
                "name": "Canine & Feline",
                "member_symbol_ids": ["sample_project.Dog", "sample_project.Cat"],
                "role": "Concrete Animals",
                "rationale": "Subclasses of animal",
            },
            {
                "component_id": "comp_2",
                "name": "Manager",
                "member_symbol_ids": ["sample_project.Zoo"],
                "role": "Container",
                "rationale": "Manages animals",
            },
        ],
        "unclustered_symbol_ids": [],
        "narrative": "System with dog, cat, and zoo.",
    }

    validated, dropped = validate_clustering(mock_llm_response, real_node_ids)

    # Assert omitted symbol "sample_project.Animal" appears in unclustered_symbol_ids
    assert "sample_project.Animal" in validated["unclustered_symbol_ids"]
    assert "sample_project.Dog" not in validated["unclustered_symbol_ids"]
    assert "sample_project.Cat" not in validated["unclustered_symbol_ids"]
    assert "sample_project.Zoo" not in validated["unclustered_symbol_ids"]

    # Verify accounting: clustered + unclustered == total real symbols
    clustered = set()
    for c in validated["components"]:
        clustered.update(c["member_symbol_ids"])
    total_accounted = clustered.union(set(validated["unclustered_symbol_ids"]))
    assert total_accounted == real_node_ids


# ---------------------------------------------------------------------------
# Validator Unit Test — Malformed Output Handling
# ---------------------------------------------------------------------------

def test_validator_rejects_malformed_output():
    """Validator raises MalformedLLMOutputError on non-JSON or missing schema keys."""
    real_node_ids = {"mod.A", "mod.B"}

    # Not JSON
    with pytest.raises(MalformedLLMOutputError):
        validate_clustering("I am an AI, here is the architecture...", real_node_ids)

    # Missing narrative
    with pytest.raises(MalformedLLMOutputError):
        validate_clustering({"components": []}, real_node_ids)

    # Missing components
    with pytest.raises(MalformedLLMOutputError):
        validate_clustering({"narrative": "text"}, real_node_ids)

    # Malformed component
    with pytest.raises(MalformedLLMOutputError):
        validate_clustering({
            "components": [{"bad_key": 1}],
            "narrative": "text",
        }, real_node_ids)


# ---------------------------------------------------------------------------
# Test Procedure 3: Integration Test — /api/architecture/advanced with Mocked LLM
# ---------------------------------------------------------------------------

def test_api_advanced_architecture_mocked_llm(client):
    """POST /api/architecture/advanced returns correctly validated response with deterministic mocked LLM."""
    # Ensure sample_project is analyzed
    analyze_resp = client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})
    assert analyze_resp.status_code == 200, f"Analysis failed: {analyze_resp.text}"
    graph_data = analyze_resp.json()
    all_real_ids = {n["id"] for n in graph_data["nodes"]}

    mock_llm_output = json.dumps({
        "components": [
            {
                "component_id": "comp_animals",
                "name": "Animal Domain Model",
                "member_symbol_ids": [
                    "sample_project.Animal",
                    "sample_project.Dog",
                    "sample_project.Cat",
                    "sample_project.InventedBeast",  # Should be dropped
                ],
                "role": "Domain Entities",
                "rationale": "Hierarchical animal classes sharing core behaviors",
            },
            {
                "component_id": "comp_zoo",
                "name": "Zoo Orchestration",
                "member_symbol_ids": [
                    "sample_project.Zoo",
                    "sample_project.build_zoo",
                ],
                "role": "Application Service",
                "rationale": "Aggregates animal instances into collections",
            },
        ],
        "unclustered_symbol_ids": [],
        "narrative": "Sample project implements an object-oriented animal hierarchy with a zoo container.",
    })

    with patch("backend.advanced_architecture.query_qwen", return_value=mock_llm_output) as mock_query:
        response = client.post("/api/architecture/advanced", json={"force_refresh": True})
        assert response.status_code == 200, f"Endpoint failed: {response.text}"
        mock_query.assert_called_once()

    data = response.json()
    validated_response = AdvancedArchitectureResponse(**data)

    # 1. Assert structure
    assert len(validated_response.components) == 2
    assert validated_response.narrative == "Sample project implements an object-oriented animal hierarchy with a zoo container."

    # 2. Assert all member_symbol_ids exist in graph
    for comp in validated_response.components:
        for sid in comp.member_symbol_ids:
            assert sid in all_real_ids, f"Symbol {sid} not in real node IDs"
    assert "sample_project.InventedBeast" not in validated_response.components[0].member_symbol_ids

    # 3. Assert unclustered_symbol_ids accounts for all remaining symbols
    clustered = set()
    for comp in validated_response.components:
        clustered.update(comp.member_symbol_ids)
    for sid in validated_response.unclustered_symbol_ids:
        assert sid in all_real_ids, f"Unclustered symbol {sid} not in real node IDs"

    accounted = clustered.union(set(validated_response.unclustered_symbol_ids))
    assert accounted == all_real_ids, "Not all symbols accounted for in components or unclustered list"


# ---------------------------------------------------------------------------
# Test Procedure 5: Cache Reuse Confirmation
# ---------------------------------------------------------------------------

def test_cache_reuse_avoids_reinvoking_llm(client):
    """Calling /api/architecture/advanced twice without re-analysis reuses cache and invokes LLM only once."""
    # Ensure sample project analyzed
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    mock_llm_output = json.dumps({
        "components": [
            {
                "component_id": "comp_1",
                "name": "Core",
                "member_symbol_ids": ["sample_project.Animal"],
                "role": "Model",
                "rationale": "Base class",
            }
        ],
        "unclustered_symbol_ids": [],
        "narrative": "Deterministic mock narrative.",
    })

    with patch("backend.advanced_architecture.query_qwen", return_value=mock_llm_output) as mock_query:
        # First call: triggers LLM
        res1 = client.post("/api/architecture/advanced", json={"force_refresh": False})
        assert res1.status_code == 200
        assert mock_query.call_count == 1

        # Second call: must reuse cache, no second LLM call!
        res2 = client.post("/api/architecture/advanced", json={"force_refresh": False})
        assert res2.status_code == 200
        assert mock_query.call_count == 1, f"Expected 1 call to LLM, but got {mock_query.call_count}"

        # Responses must be identical
        assert res1.json() == res2.json()

        # Third call with force_refresh=True: must re-invoke LLM
        res3 = client.post("/api/architecture/advanced", json={"force_refresh": True})
        assert res3.status_code == 200
        assert mock_query.call_count == 2, f"Expected 2 calls after force_refresh, got {mock_query.call_count}"


# ---------------------------------------------------------------------------
# Test Procedure 4: Live Qualitative Run (Unmocked)
# ---------------------------------------------------------------------------

def test_live_qualitative_run_unmocked(client, capsys):
    """Run /api/architecture/advanced live unmocked against sample_project and log output as evidence."""
    # Ensure sample_project is analyzed
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    # Call live unmocked with force_refresh=True
    response = client.post("/api/architecture/advanced", json={"force_refresh": True})
    assert response.status_code == 200, f"Live call failed: {response.text}"

    data = response.json()
    validated = AdvancedArchitectureResponse(**data)

    print("\n--- LIVE QUALITATIVE RUN (UNMOCKED EVIDENCE) ---")
    print(f"Component count: {len(validated.components)}")
    for comp in validated.components:
        print(f"  * Component: {comp.name} [{comp.role}] (members: {len(comp.member_symbol_ids)})")
        print(f"    Rationale: {comp.rationale}")
        print(f"    Symbols: {comp.member_symbol_ids}")
    print(f"Unclustered symbols ({len(validated.unclustered_symbol_ids)}): {validated.unclustered_symbol_ids}")
    print(f"Narrative:\n{validated.narrative}")
    print("------------------------------------------------\n")


def test_malformed_llm_output_triggers_stricter_retry(client):
    """Malformed LLM output triggers exactly one retry with stricter prompt before succeeding."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    malformed_first_reply = "I'm not outputting JSON right now! Here is some chat instead."
    valid_second_reply = json.dumps({
        "components": [
            {
                "component_id": "comp_1",
                "name": "Core",
                "member_symbol_ids": ["sample_project.Animal"],
                "role": "Model",
                "rationale": "Base class",
            }
        ],
        "unclustered_symbol_ids": [],
        "narrative": "Valid narrative on retry.",
    })

    with patch("backend.advanced_architecture.query_qwen", side_effect=[malformed_first_reply, valid_second_reply]) as mock_query:
        res = client.post("/api/architecture/advanced", json={"force_refresh": True})
        assert res.status_code == 200
        assert mock_query.call_count == 2
        data = res.json()
        assert data["narrative"] == "Valid narrative on retry."


def test_malformed_retry_failure_returns_error(client):
    """If both initial call and retry fail validation, endpoint returns 502 with clear error."""
    client.post("/api/analyze", json={"project_path": str(SAMPLE_PROJECT_DIR)})

    bad_reply = "Still not valid JSON on retry."

    with patch("backend.advanced_architecture.query_qwen", side_effect=[bad_reply, bad_reply]):
        res = client.post("/api/architecture/advanced", json={"force_refresh": True})
        assert res.status_code == 502
        assert "LLM architectural clustering failed validation" in res.json()["detail"]
