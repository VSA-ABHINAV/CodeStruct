from pathlib import Path

import main
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_home_endpoint_response():
    response = TestClient(main.app).get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "CodeStruct Backend is Working!"}


def test_analyze_endpoint_response_shape_and_sample_content(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT / "backend")

    response = TestClient(main.app).get("/analyze")
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {"files", "dependencies"}
    assert {item["file"] for item in body["files"]} == {
        "database.py",
        "main.py",
        "user.py",
    }
    assert all(
        set(item) == {"file", "imports", "classes", "functions", "inheritance", "calls"}
        for item in body["files"]
    )
    assert {
        (item["source"], item["target"], item["type"]) for item in body["dependencies"]
    } == {
        ("main.py", "user.py", "import"),
        ("user.py", "database.py", "import"),
    }
