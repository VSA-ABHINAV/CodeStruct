import os
from dataclasses import replace
from pathlib import Path

import pytest
from codestruct.analysis.diagnostics import DiagnosticCode
from codestruct.analysis.policy import AnalysisPolicy
from codestruct.analysis.python_parser import PythonAstParser
from codestruct.analysis.scanner import derive_module_name, scan_project

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARSER_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "parser_project"


@pytest.mark.parametrize(
    ("relative_path", "expected"),
    [
        ("main.py", "main"),
        ("pkg/module.py", "pkg.module"),
        ("pkg/__init__.py", "pkg"),
        ("__init__.py", "__root__"),
    ],
)
def test_module_name_derivation(relative_path, expected):
    assert derive_module_name(relative_path) == expected


def test_recursive_scan_is_deterministic_and_uses_relative_identity():
    policy = AnalysisPolicy(exclude_patterns=("generated/**",))

    first = scan_project(PARSER_FIXTURE, policy)
    second = scan_project(PARSER_FIXTURE, policy)

    assert first == second
    paths = [item.relative_path for item in first.source_files]
    assert paths == sorted(paths)
    assert "pkg/module.py" in paths
    assert "deep/one/two/deep.py" in paths
    assert ".venv/ignored.py" not in paths
    assert "vendor/ignored.py" not in paths
    assert "generated/ignored.py" not in paths
    duplicate_ids = {
        item.id
        for item in first.source_files
        if item.relative_path.endswith("duplicate.py")
    }
    assert len(duplicate_ids) == 2
    assert (
        next(
            item
            for item in first.source_files
            if item.relative_path == "pkg/__init__.py"
        ).module_name
        == "pkg"
    )
    assert (
        next(
            item for item in first.source_files if item.relative_path == "pkg/module.py"
        ).id
        == "src_6ae6ba2c0b8bca91ff994d17"
    )


def test_authorized_root_accepts_descendant_and_rejects_escape(tmp_path):
    allowed = tmp_path / "allowed"
    project = allowed / "project"
    outside = tmp_path / "outside"
    project.mkdir(parents=True)
    outside.mkdir()
    (project / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
    (outside / "no.py").write_text("VALUE = 2\n", encoding="utf-8")
    policy = AnalysisPolicy(authorized_roots=(allowed,))

    accepted = scan_project(project, policy)
    rejected = scan_project(project / ".." / ".." / "outside", policy)

    assert [item.relative_path for item in accepted.source_files] == ["ok.py"]
    assert rejected.source_files == ()
    assert [item.code for item in rejected.diagnostics] == [
        DiagnosticCode.UNAUTHORIZED_ROOT
    ]


def test_invalid_project_root_is_reported_without_path_disclosure():
    missing = PARSER_FIXTURE / "directory-that-does-not-exist"

    result = scan_project(missing, AnalysisPolicy())

    assert result.source_files == ()
    assert result.diagnostics[0].code is DiagnosticCode.INVALID_PROJECT_ROOT
    assert str(missing) not in result.diagnostics[0].message


@pytest.mark.parametrize(
    ("policy", "expected_code"),
    [
        (AnalysisPolicy(max_files=2), DiagnosticCode.FILE_COUNT_LIMIT_REACHED),
        (AnalysisPolicy(max_depth=0), DiagnosticCode.DEPTH_LIMIT_REACHED),
        (AnalysisPolicy(max_file_size=0), DiagnosticCode.FILE_TOO_LARGE),
    ],
)
def test_scanner_enforces_limits(policy, expected_code):
    result = scan_project(PARSER_FIXTURE, policy)

    assert result.limit_reached
    assert expected_code in {item.code for item in result.diagnostics}


def test_matched_unsupported_file_is_diagnosed_without_reading_it():
    result = scan_project(PARSER_FIXTURE, AnalysisPolicy(include_patterns=("*",)))

    assert DiagnosticCode.UNSUPPORTED_FILE in {item.code for item in result.diagnostics}
    assert "unsupported.txt" not in {item.relative_path for item in result.source_files}


def test_scanner_has_cancellation_checkpoints():
    checks = 0

    def cancellation_check():
        nonlocal checks
        checks += 1
        return checks >= 4

    result = scan_project(PARSER_FIXTURE, AnalysisPolicy(), cancellation_check)

    assert result.cancelled
    assert DiagnosticCode.CANCELLATION_REQUESTED in {
        item.code for item in result.diagnostics
    }


def test_parser_rejects_tampered_relative_path():
    scan = scan_project(PARSER_FIXTURE, AnalysisPolicy())
    source_file = replace(scan.source_files[0], relative_path="../outside.py")

    result = PythonAstParser().parse(PARSER_FIXTURE, source_file, AnalysisPolicy())

    assert not result.parsed
    assert result.diagnostics[0].code is DiagnosticCode.PATH_TRAVERSAL_REJECTED
    assert str(PARSER_FIXTURE) not in result.diagnostics[0].message


def test_link_is_skipped_when_platform_permits_creation(tmp_path):
    project = tmp_path / "project"
    target = tmp_path / "target"
    project.mkdir()
    target.mkdir()
    (target / "outside.py").write_text("VALUE = 1\n", encoding="utf-8")
    link = project / "linked"
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory links are unavailable for this test account")

    result = scan_project(project, AnalysisPolicy())

    assert result.source_files == ()
    assert DiagnosticCode.PATH_LINK_SKIPPED in {
        item.code for item in result.diagnostics
    }
