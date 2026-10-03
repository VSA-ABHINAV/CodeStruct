"""Real backend end-to-end smoke verification for Milestone 2."""

import json
import time
from pathlib import Path

from codestruct.api.app import create_app
from codestruct.settings import Settings
from fastapi.testclient import TestClient


def run_m2_smoke(tmp_path: Path):
    proj_dir = tmp_path / "m2_sample_project"
    proj_dir.mkdir()

    (proj_dir / "core.py").write_text(
        "class BaseEngine:\n"
        "    def run(self):\n"
        "        pass\n"
        "\n"
        "class Engine(BaseEngine):\n"
        "    def execute(self):\n"
        "        self.run()\n",
        encoding="utf-8",
    )

    (proj_dir / "service.py").write_text(
        "from core import Engine\n"
        "\n"
        "class Service:\n"
        "    def __init__(self):\n"
        "        self.engine = Engine()\n"
        "    def start(self):\n"
        "        self.engine.execute()\n",
        encoding="utf-8",
    )

    (proj_dir / "utils.py").write_text(
        "def log_msg(msg: str) -> None:\n    pass\n",
        encoding="utf-8",
    )

    (proj_dir / "utils.pyi").write_text(
        "def log_msg(msg: str) -> None: ...\n",
        encoding="utf-8",
    )

    (proj_dir / "main.py").write_text(
        "import utils\n"
        "from service import Service\n"
        "\n"
        "def main():\n"
        "    utils.log_msg('Starting')\n"
        "    srv = Service()\n"
        "    srv.start()\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "m2_smoke.sqlite3"
    settings = Settings(
        authorized_roots={"m2_proj": proj_dir},
        database_path=db_path,
    )
    app = create_app(settings)

    results = {}
    try:
        with TestClient(app) as client:
            # 1. Run analysis with options.metrics = False
            resp_no_m = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "m2_proj", "relative_path": "."},
                    "options": {"metrics": False},
                },
            )
            assert resp_no_m.status_code == 202, (
                f"Failed create metrics=False: {resp_no_m.text}"
            )
            id_no_m = resp_no_m.json()["analysis_id"]

            for _ in range(200):
                poll = client.get(f"/api/v1/analyses/{id_no_m}").json()
                if poll.get("terminal"):
                    break
                time.sleep(0.05)

            graph_no_m = client.get(f"/api/v1/analyses/{id_no_m}/graph").json()
            nodes_no_m = graph_no_m["nodes"]
            _ = graph_no_m["edges"]
            assert graph_no_m["metadata"]["metrics_computed"] is False, (
                "metrics_computed must be False when options.metrics=False"
            )

            # 2. Run analysis with options.metrics = True
            resp_m = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "m2_proj", "relative_path": "."},
                    "options": {"metrics": True},
                },
            )
            assert resp_m.status_code == 202, (
                f"Failed create metrics=True: {resp_m.text}"
            )
            id_m = resp_m.json()["analysis_id"]
            assert id_m != id_no_m

            for _ in range(200):
                poll = client.get(f"/api/v1/analyses/{id_m}").json()
                if poll.get("terminal"):
                    break
                time.sleep(0.05)

            graph_m = client.get(f"/api/v1/analyses/{id_m}/graph").json()
            nodes_m = graph_m["nodes"]
            edges_m = graph_m["edges"]
            assert graph_m["metadata"]["metrics_computed"] is True, (
                "metrics_computed must be True when options.metrics=True"
            )

            # 3. Test explanation on a node with metrics
            service_class_node = next(n for n in nodes_m if n["name"] == "Service")
            assert service_class_node["location"]["path"] == "service.py"
            assert service_class_node["location"]["start_line"] == 3
            assert service_class_node["location"]["end_line"] == 7

            explain_resp = client.get(
                f"/api/v1/analyses/{id_m}/nodes/{service_class_node['id']}/explain"
            )
            assert explain_resp.status_code == 200
            explanation_data = explain_resp.json()
            assert "service.py:3-7" in explanation_data["summary"], (
                f"Expected service.py:3-7 in summary, got {explanation_data['summary']}"
            )
            assert "Static Evidence Observations" in explanation_data["prompt"], (
                "Prompt must carry bounded static evidence observations"
            )

            # 4. Test explanation on a node without metrics
            service_class_no_m = next(n for n in nodes_no_m if n["name"] == "Service")
            explain_no_m_resp = client.get(
                f"/api/v1/analyses/{id_no_m}/nodes/{service_class_no_m['id']}/explain"
            )
            assert explain_no_m_resp.status_code == 200
            explanation_no_m_data = explain_no_m_resp.json()

            # 5. Test module node metrics (Ca, Ce, instability, cohesion, relational density, community, component)
            service_mod_node = next(
                n for n in nodes_m if n["name"] == "service" and n["kind"] == "module"
            )
            mod_attrs = dict(service_mod_node.get("attributes", []))
            assert "ca" in mod_attrs, "Module node must report Ca"
            assert "ce" in mod_attrs, "Module node must report Ce"
            assert "module_instability" in mod_attrs, (
                "Module node must report module_instability"
            )
            assert "cohesion" in mod_attrs, "Module node must report cohesion"
            assert "relational_density" in mod_attrs, (
                "Module node must report relational_density"
            )
            assert "community" in mod_attrs, "Module node must report community"
            assert "component" in mod_attrs, "Module node must report component"

            # 6. Test cache hit on repeat metrics=True
            repeat_resp = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "m2_proj", "relative_path": "."},
                    "options": {"metrics": True},
                },
            )
            assert repeat_resp.status_code == 200
            assert repeat_resp.json()["cache_hit"] is True
            cached_graph = client.get(
                f"/api/v1/analyses/{repeat_resp.json()['analysis_id']}/graph"
            ).json()
            assert cached_graph["metadata"]["metrics_computed"] is True, (
                "Cached graph must retain metrics_computed=True"
            )

            results = {
                "id_no_m": id_no_m,
                "id_m": id_m,
                "node_count": len(nodes_m),
                "edge_count": len(edges_m),
                "metadata_metrics_computed_false": graph_no_m["metadata"][
                    "metrics_computed"
                ],
                "metadata_metrics_computed_true": graph_m["metadata"][
                    "metrics_computed"
                ],
                "metadata_metrics_computed_warm_cache": cached_graph["metadata"][
                    "metrics_computed"
                ],
                "module_service_metrics": mod_attrs,
                "sample_node_no_metrics_attrs": service_class_no_m.get("attributes"),
                "sample_node_metrics_attrs": service_class_node.get("attributes"),
                "sample_node_location": service_class_node.get("location"),
                "explanation_with_metrics": explanation_data,
                "explanation_without_metrics": explanation_no_m_data,
                "cache_hit_verified": True,
            }
    finally:
        app.state.analysis_service.shutdown()

    return results


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        res = run_m2_smoke(Path(td))
        print(json.dumps(res, indent=2))
