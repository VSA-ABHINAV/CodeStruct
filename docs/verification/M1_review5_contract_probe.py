"""Read the submitted brief and compare its examples to backend behavior."""

import json
import re
import tempfile
from pathlib import Path

from codestruct.analysis import AnalysisPolicy, parse_project
from codestruct.api.pagination import decode_cursor
from codestruct.graph import build_graph, graph_to_dict
from codestruct.settings import Settings

repo = Path(__file__).resolve().parents[2]
brief = (repo / "LOVABLE_FRONTEND_BRIEF.md").read_text(encoding="utf-8")
print("Default full graph bytes:", Settings(authorized_roots={}).max_full_graph_bytes)
with tempfile.TemporaryDirectory(prefix="codestruct-review5-") as temporary:
    root = Path(temporary)
    (root / "invalid.py").write_text("def broken(\n", encoding="utf-8")
    generated = graph_to_dict(
        build_graph(parse_project(root, AnalysisPolicy(authorized_roots=(root,))))
    )
    print("Generated syntax diagnostic:", json.dumps(generated["diagnostics"]))

section = brief.split("### 5.6", 1)[1].split("### 5.7", 1)[0]
example = json.loads(re.search(r"```json\s*(.*?)```", section, re.S).group(1))
filters = dict(node_kind=None, edge_kind=None, resolution_status=None, limit=1)
try:
    offset = decode_cursor(
        example["page"]["next_cursor"], example["metadata"]["graph_id"], filters
    )
    print("Documented cursor decoded offset:", offset)
except ValueError as error:
    print("Documented cursor rejected:", error)

parser_fixture = repo / "tests/fixtures/parser_project"
locationless = graph_to_dict(
    build_graph(
        parse_project(
            parser_fixture, AnalysisPolicy(authorized_roots=(parser_fixture,))
        )
    )
)
print(
    "Diagnostics with null location:",
    sum(d["location"] is None for d in locationless["diagnostics"]),
)
