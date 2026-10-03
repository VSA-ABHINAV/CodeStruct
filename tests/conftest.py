"""Suite-wide marker ownership without rewriting useful historical tests."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.path)).as_posix()
        if "/performance/" in path:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        elif path.endswith(("test_cache_integration.py", "test_v1_api.py")):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.process)
        elif path.endswith(
            ("test_api_characterization.py", "test_analyzer_characterization.py")
        ):
            item.add_marker(pytest.mark.contract)
        elif path.endswith("test_storage.py"):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

        if "link" in item.name or "junction" in item.name:
            item.add_marker(pytest.mark.platform)
