from pathlib import Path

from analyzer import analyze_file, analyze_project, create_dependency_graph

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PROJECT = PROJECT_ROOT / "sample_project"
AST_SHAPES_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ast_shapes.py"


def test_sample_project_analysis_matches_current_output():
    files = analyze_project(SAMPLE_PROJECT)
    files_by_name = {item["file"]: item for item in files}

    assert files_by_name == {
        "database.py": {
            "file": "database.py",
            "imports": [],
            "classes": ["Database"],
            "functions": ["get_user"],
            "inheritance": [],
            "calls": [],
        },
        "main.py": {
            "file": "main.py",
            "imports": ["user"],
            "classes": [],
            "functions": [],
            "inheritance": [],
            "calls": [
                {"type": "method", "object": "user", "function": "UserService"},
                {"type": "method", "object": "service", "function": "get_user"},
            ],
        },
        "user.py": {
            "file": "user.py",
            "imports": ["database"],
            "classes": ["UserService", "User", "Admin"],
            "functions": ["get_user"],
            "inheritance": [{"child": "Admin", "parent": "User"}],
            "calls": [
                {
                    "type": "method",
                    "object": "database",
                    "function": "Database",
                },
                {"type": "method", "object": "db", "function": "get_user"},
            ],
        },
    }


def test_sample_project_dependency_graph_matches_current_output():
    dependencies = create_dependency_graph(SAMPLE_PROJECT)

    assert {
        (item["source"], item["target"], item["type"]) for item in dependencies
    } == {
        ("main.py", "user.py", "import"),
        ("user.py", "database.py", "import"),
    }


def test_supported_ast_shapes_and_duplicate_suppression():
    assert analyze_file(AST_SHAPES_FIXTURE) == {
        "file": "ast_shapes.py",
        "imports": ["os", "package"],
        "classes": ["Child"],
        "functions": ["run"],
        "inheritance": [{"child": "Child", "parent": "Base"}],
        "calls": [
            {"type": "function", "name": "helper"},
            {"type": "method", "object": "package", "function": "factory"},
        ],
    }
