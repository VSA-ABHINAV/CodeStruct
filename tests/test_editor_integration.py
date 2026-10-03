from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest import TestCase

from codestruct.analysis import AnalysisPolicy, scan_project
from codestruct.api.app import create_app
from codestruct.jobs.service import AnalysisService, ProjectSelectionError
from codestruct.settings import Settings
from fastapi.testclient import TestClient


class TestEditorIntegration(TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.temp_dir.name).resolve()

        # Create sample files
        self.script_a = self.base / "script_a.py"
        self.script_a.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        self.script_pyw = self.base / "gui_tool.pyw"
        self.script_pyw.write_text("class GuiApp:\n    pass\n", encoding="utf-8")

        self.sibling_file = self.base / "sibling.py"
        self.sibling_file.write_text(
            "def sibling_func():\n    pass\n", encoding="utf-8"
        )

        self.unsupported_file = self.base / "data.txt"
        self.unsupported_file.write_text("plain text", encoding="utf-8")

        # Subdirectory with duplicate basename
        self.sub_dir = self.base / "sub"
        self.sub_dir.mkdir()
        self.script_dup = self.sub_dir / "script_a.py"
        self.script_dup.write_text(
            "def duplicate_name():\n    return 42\n", encoding="utf-8"
        )

        # Syntax error file
        self.syntax_error_file = self.base / "broken.py"
        self.syntax_error_file.write_text("def broken(:\n    pass\n", encoding="utf-8")

        # Empty file
        self.empty_file = self.base / "empty.py"
        self.empty_file.write_text("", encoding="utf-8")

        # Configure settings with base as an authorized root and SQLite database for cache
        self.settings = Settings(
            authorized_roots={"test_root": self.base},
            database_path=self.base / "cache.sqlite3",
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.state.analysis_service.shutdown()
        self.temp_dir.cleanup()

    def test_editor_selection_success_py_and_pyw(self) -> None:
        # Test .py file
        resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.script_a)}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["capability_id"].startswith("cap_"))
        self.assertEqual(data["root_id"], data["capability_id"])
        self.assertEqual(data["relative_path"], "script_a.py")
        self.assertEqual(data["display_name"], "script_a.py")
        # Ensure absolute path is NOT leaked
        self.assertNotIn(str(self.base), str(data))

        # Test .pyw file
        resp_pyw = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.script_pyw)}
        )
        self.assertEqual(resp_pyw.status_code, 200)
        data_pyw = resp_pyw.json()
        self.assertEqual(data_pyw["relative_path"], "gui_tool.pyw")
        self.assertEqual(data_pyw["display_name"], "gui_tool.pyw")

    def test_editor_selection_path_with_spaces_and_non_ascii(self) -> None:
        spaced_dir = self.base / "my folder with spaces"
        spaced_dir.mkdir()
        spaced_file = spaced_dir / "my script with spaces.py"
        spaced_file.write_text("def spaced():\n    return 'spaces'\n", encoding="utf-8")

        resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(spaced_file)}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["relative_path"], "my script with spaces.py")

        sub = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": data["root_id"],
                    "relative_path": data["relative_path"],
                }
            },
        )
        self.assertIn(sub.status_code, (200, 202))

        # Non-ASCII path
        unicode_dir = self.base / "dossier_français"
        unicode_dir.mkdir()
        unicode_file = unicode_dir / "analyse_données.py"
        unicode_file.write_text("def calcul():\n    return 100\n", encoding="utf-8")

        resp_u = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(unicode_file)}
        )
        self.assertEqual(resp_u.status_code, 200)
        data_u = resp_u.json()
        self.assertEqual(data_u["relative_path"], "analyse_données.py")

        sub_u = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": data_u["root_id"],
                    "relative_path": data_u["relative_path"],
                }
            },
        )
        self.assertIn(sub_u.status_code, (200, 202))

    def test_editor_selection_rejects_unsupported_extensions(self) -> None:
        resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.unsupported_file)}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "UNSUPPORTED_EXTENSION")

    def test_editor_selection_rejects_directories_and_missing(self) -> None:
        # Directory
        resp_dir = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.base)}
        )
        self.assertEqual(resp_dir.status_code, 404)
        self.assertEqual(resp_dir.json()["error"]["code"], "PROJECT_NOT_FOUND")

        # Missing file
        missing = self.base / "does_not_exist.py"
        resp_missing = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(missing)}
        )
        self.assertEqual(resp_missing.status_code, 404)
        self.assertEqual(resp_missing.json()["error"]["code"], "PROJECT_NOT_FOUND")

    def test_editor_selection_rejects_traversal_and_malformed(self) -> None:
        resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": "foo/../bar.py"}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error"]["code"], "PROJECT_UNAUTHORIZED")

    def test_capability_expiry_and_reuse(self) -> None:
        service = AnalysisService(self.settings)
        # Register with short TTL
        cap = service.register_editor_file(self.script_a, ttl_seconds=0.1)
        self.assertIsNotNone(cap)
        # Re-register while active -> reuses capability
        cap_reuse = service.register_editor_file(self.script_a, ttl_seconds=60.0)
        self.assertIsNotNone(cap_reuse)

        # Let short cap expire
        expired_cap = service.register_editor_file(self.script_pyw, ttl_seconds=0.01)
        time.sleep(0.05)
        self.assertIsNone(service.get_editor_capability(expired_cap.capability_id))

        with self.assertRaises(ProjectSelectionError) as ctx:
            service.resolve_project(expired_cap.capability_id, "gui_tool.pyw")
        self.assertEqual(ctx.exception.code, "PROJECT_UNAUTHORIZED")

    def test_single_file_scan_does_not_touch_siblings(self) -> None:
        # When policy has single_file_name, scan_project MUST NOT include sibling files
        policy = AnalysisPolicy(single_file_name="script_a.py")
        scan = scan_project(self.base, policy)
        file_names = [f.relative_path for f in scan.source_files]
        self.assertEqual(file_names, ["script_a.py"])
        self.assertNotIn("sibling.py", file_names)
        self.assertNotIn("gui_tool.pyw", file_names)

    def test_analysis_submission_and_graph_with_capability(self) -> None:
        # Register file
        sel_resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.script_a)}
        )
        self.assertEqual(sel_resp.status_code, 200)
        cap = sel_resp.json()

        # Submit analysis using capability
        sub_resp = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap["root_id"],
                    "relative_path": cap["relative_path"],
                }
            },
        )
        self.assertIn(sub_resp.status_code, (200, 202))
        analysis_id = sub_resp.json()["analysis_id"]

        # Wait for terminal state
        for _ in range(50):
            status_resp = self.client.get(f"/api/v1/analyses/{analysis_id}")
            if status_resp.json()["terminal"]:
                break
            time.sleep(0.05)

        self.assertEqual(status_resp.json()["state"], "completed")

        # Retrieve graph
        graph_resp = self.client.get(f"/api/v1/analyses/{analysis_id}/graph")
        self.assertEqual(graph_resp.status_code, 200)
        graph = graph_resp.json()

        # Verify only nodes from script_a.py exist, no sibling.py
        paths = {
            node.get("location", {}).get("path")
            for node in graph["nodes"]
            if node.get("location")
        }
        self.assertIn("script_a.py", paths)
        self.assertNotIn("sibling.py", paths)

        # Verify absolute path is NOT in graph nodes or metadata
        self.assertNotIn(str(self.base), str(graph))

    def test_cache_hit_on_unchanged_and_invalidation_on_change(self) -> None:
        sel_resp1 = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.script_a)}
        )
        cap1 = sel_resp1.json()

        # First run
        sub_resp1 = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap1["root_id"],
                    "relative_path": cap1["relative_path"],
                }
            },
        )
        ana1 = sub_resp1.json()["analysis_id"]
        for _ in range(50):
            if self.client.get(f"/api/v1/analyses/{ana1}").json()["terminal"]:
                break
            time.sleep(0.05)

        # Second run without modifying script_a.py -> honest cache hit
        sel_resp2 = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.script_a)}
        )
        cap2 = sel_resp2.json()
        sub_resp2 = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap2["root_id"],
                    "relative_path": cap2["relative_path"],
                }
            },
        )
        self.assertTrue(sub_resp2.json()["cache_hit"])

        # Modify file -> cache invalidation
        self.script_a.write_text(
            "def hello():\n    return 'changed'\n", encoding="utf-8"
        )
        sel_resp3 = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.script_a)}
        )
        cap3 = sel_resp3.json()
        sub_resp3 = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap3["root_id"],
                    "relative_path": cap3["relative_path"],
                }
            },
        )
        # Should be fresh analysis (cache_hit is False)
        self.assertFalse(sub_resp3.json()["cache_hit"])
        ana3 = sub_resp3.json()["analysis_id"]
        for _ in range(50):
            if self.client.get(f"/api/v1/analyses/{ana3}").json()["terminal"]:
                break
            time.sleep(0.05)

    def test_duplicate_basename_in_separate_directories(self) -> None:
        # script_a.py in root vs script_a.py in sub/
        resp1 = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.script_a)}
        )
        resp2 = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.script_dup)}
        )
        cap1 = resp1.json()
        cap2 = resp2.json()

        # Different capabilities
        self.assertNotEqual(cap1["capability_id"], cap2["capability_id"])

        # Submit both and verify distinct results
        sub1 = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap1["root_id"],
                    "relative_path": cap1["relative_path"],
                }
            },
        )
        sub2 = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap2["root_id"],
                    "relative_path": cap2["relative_path"],
                }
            },
        )

        ana1 = sub1.json()["analysis_id"]
        ana2 = sub2.json()["analysis_id"]

        for _ in range(50):
            t1 = self.client.get(f"/api/v1/analyses/{ana1}").json()["terminal"]
            t2 = self.client.get(f"/api/v1/analyses/{ana2}").json()["terminal"]
            if t1 and t2:
                break
            time.sleep(0.05)

        g1 = self.client.get(f"/api/v1/analyses/{ana1}/graph").json()
        g2 = self.client.get(f"/api/v1/analyses/{ana2}/graph").json()

        names1 = {n["name"] for n in g1["nodes"]}
        names2 = {n["name"] for n in g2["nodes"]}

        self.assertIn("hello", names1)
        self.assertIn("duplicate_name", names2)
        self.assertNotIn("duplicate_name", names1)

    def test_syntax_error_file_produces_partial_result(self) -> None:
        sel_resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.syntax_error_file)}
        )
        cap = sel_resp.json()
        sub = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap["root_id"],
                    "relative_path": cap["relative_path"],
                }
            },
        )
        ana = sub.json()["analysis_id"]
        for _ in range(50):
            res = self.client.get(f"/api/v1/analyses/{ana}").json()
            if res["terminal"]:
                break
            time.sleep(0.05)

        self.assertEqual(res["state"], "partially_completed")
        self.assertTrue(res["partial"])

        # Diagnostics response
        diag = self.client.get(f"/api/v1/analyses/{ana}/diagnostics").json()
        codes = [item["code"] for item in diag["items"]]
        self.assertIn("FILE_SYNTAX_ERROR", codes)

    def test_empty_file_analyzes_safely(self) -> None:
        sel_resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(self.empty_file)}
        )
        cap = sel_resp.json()
        sub = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap["root_id"],
                    "relative_path": cap["relative_path"],
                }
            },
        )
        ana = sub.json()["analysis_id"]
        for _ in range(50):
            res = self.client.get(f"/api/v1/analyses/{ana}").json()
            if res["terminal"]:
                break
            time.sleep(0.05)
        self.assertEqual(res["state"], "completed")

    def test_no_source_execution(self) -> None:
        # Create a file that would create a side-effect canary file if executed
        canary = self.base / "canary.txt"
        side_effect_file = self.base / "side_effect.py"
        side_effect_file.write_text(
            f"open(r'{canary}', 'w').write('executed')\n", encoding="utf-8"
        )

        sel_resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(side_effect_file)}
        )
        cap = sel_resp.json()
        sub = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": cap["root_id"],
                    "relative_path": cap["relative_path"],
                }
            },
        )
        ana = sub.json()["analysis_id"]
        for _ in range(50):
            if self.client.get(f"/api/v1/analyses/{ana}").json()["terminal"]:
                break
            time.sleep(0.05)

        # Canary must NOT exist
        self.assertFalse(
            canary.exists(), "Source code was executed! Side effect canary exists."
        )

    def test_fabricated_capability_rejected(self) -> None:
        sub_resp = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "root_id": "cap_fabricated_fake_id_12345",
                    "relative_path": "fake.py",
                }
            },
        )
        self.assertEqual(sub_resp.status_code, 403)
        self.assertEqual(sub_resp.json()["error"]["code"], "PROJECT_UNAUTHORIZED")

    def test_regression_file_outside_authorized_roots_with_unrelated_root(self) -> None:
        # Settings authorize only one unrelated configured root
        unrelated_dir = self.base / "unrelated_configured_root"
        unrelated_dir.mkdir()
        unrelated_file = unrelated_dir / "demo.py"
        unrelated_file.write_text("def demo_root():\n    pass\n", encoding="utf-8")

        outside_dir = self.base / "outside_user_directory"
        outside_dir.mkdir()
        outside_target = outside_dir / "target_script.py"
        outside_target.write_text(
            "class Greeter:\n"
            "    def greet(self) -> str:\n"
            "        return 'hello'\n\n"
            "def run() -> None:\n"
            "    g = Greeter()\n"
            "    g.greet()\n",
            encoding="utf-8",
        )
        outside_sibling = outside_dir / "sibling_script.py"
        outside_sibling.write_text(
            "def sibling_should_not_exist():\n    pass\n", encoding="utf-8"
        )

        custom_settings = Settings(
            authorized_roots={"unrelated_project": unrelated_dir},
            database_path=self.base / "regression_cache.sqlite3",
        )
        custom_app = create_app(custom_settings)
        custom_client = TestClient(custom_app)
        try:
            # 1. POST /api/v1/editor/selection succeeds
            sel_resp = custom_client.post(
                "/api/v1/editor/selection", json={"file_path": str(outside_target)}
            )
            self.assertEqual(sel_resp.status_code, 200)
            cap = sel_resp.json()
            self.assertTrue(cap["capability_id"].startswith("cap_"))
            self.assertEqual(cap["relative_path"], "target_script.py")

            # 2. POST /api/v1/analyses using capability succeeds
            sub_resp = custom_client.post(
                "/api/v1/analyses",
                json={
                    "project": {
                        "root_id": cap["root_id"],
                        "relative_path": cap["relative_path"],
                    }
                },
            )
            self.assertIn(sub_resp.status_code, (200, 202))
            ana_id = sub_resp.json()["analysis_id"]

            # 3. Poll until terminal
            for _ in range(50):
                status_resp = custom_client.get(f"/api/v1/analyses/{ana_id}")
                if status_resp.json()["terminal"]:
                    break
                time.sleep(0.05)

            status_data = status_resp.json()
            # 4. Terminal state is completed, NOT partially_completed
            self.assertEqual(status_data["state"], "completed")
            self.assertFalse(status_data["partial"])

            # 5. Diagnostics do not contain UNAUTHORIZED_ROOT
            diag_resp = custom_client.get(f"/api/v1/analyses/{ana_id}/diagnostics")
            self.assertEqual(diag_resp.status_code, 200)
            diag_codes = [d["code"] for d in diag_resp.json().get("items", [])]
            self.assertNotIn("UNAUTHORIZED_ROOT", diag_codes)

            # 6. Graph contains selected file, module, classes, methods, functions
            graph_resp = custom_client.get(f"/api/v1/analyses/{ana_id}/graph")
            self.assertEqual(graph_resp.status_code, 200)
            graph = graph_resp.json()
            node_names = {n["name"] for n in graph.get("nodes", [])}
            self.assertIn("target_script.py", node_names)
            self.assertIn("target_script", node_names)
            self.assertIn("Greeter", node_names)
            self.assertIn("greet", node_names)
            self.assertIn("run", node_names)

            # 7. Graph does NOT contain sibling Python files
            self.assertNotIn("sibling_script.py", node_names)
            self.assertNotIn("sibling_should_not_exist", node_names)

            # 8. No absolute local path is exposed in API graph or diagnostics
            self.assertNotIn(str(outside_dir), str(graph))
            self.assertNotIn(str(outside_target), str(graph))
            self.assertNotIn(str(outside_dir), str(diag_resp.json()))
            self.assertNotIn(str(outside_target), str(diag_resp.json()))
        finally:
            custom_app.state.analysis_service.shutdown()

    def test_sample_project_acceptance_case(self) -> None:
        # Settings authorize only demo project
        demo_dir = self.base / "demo_root"
        demo_dir.mkdir()
        (demo_dir / "demo.py").write_text("class DemoService: pass\n", encoding="utf-8")

        outside_dir = self.base / "desktop_sample"
        outside_dir.mkdir()
        sample_file = outside_dir / "sample_project.py"
        sample_code = (
            "class Animal:\n"
            "    def __init__(self, name: str, sound: str):\n"
            "        self.name = name\n"
            "        self.sound = sound\n"
            "    def speak(self) -> str:\n"
            '        return f"{self.name} says {self.sound}"\n'
            "    def describe(self) -> str:\n"
            '        return f"I am an animal. {self.speak()}"\n\n'
            "class Dog(Animal):\n"
            "    def __init__(self, name: str):\n"
            '        super().__init__(name, sound="Woof")\n'
            "    def fetch(self) -> str:\n"
            '        return f"{self.name} fetches the ball"\n\n'
            "class Cat(Animal):\n"
            "    def __init__(self, name: str):\n"
            '        super().__init__(name, sound="Meow")\n'
            "    def scratch(self) -> str:\n"
            '        return f"{self.name} scratches the post"\n\n'
            "class Bird(Animal):\n"
            "    def __init__(self, name: str, can_fly: bool = True):\n"
            '        super().__init__(name, sound="Tweet")\n'
            "        self.can_fly = can_fly\n"
            "    def fly(self) -> str:\n"
            "        if self.can_fly:\n"
            '            return f"{self.name} flies away"\n'
            '        return f"{self.name} cannot fly"\n\n'
            "class Zoo:\n"
            "    def __init__(self, name: str):\n"
            "        self.name = name\n"
            "        self.animals: list[Animal] = []\n"
            "    def add_animal(self, animal: Animal) -> None:\n"
            "        self.animals.append(animal)\n"
            "    def all_speak(self) -> list[str]:\n"
            "        return [animal.speak() for animal in self.animals]\n"
            "    def summary(self) -> str:\n"
            '        lines = [f"Zoo: {self.name} ({len(self.animals)} animals)"]\n'
            "        for animal in self.animals:\n"
            '            lines.append("  - " + describe_animal(animal))\n'
            '        return "\\n".join(lines)\n\n'
            "def describe_animal(animal: Animal) -> str:\n"
            "    return animal.describe()\n\n"
            "def build_zoo() -> Zoo:\n"
            '    zoo = Zoo("Central Park Zoo")\n'
            '    zoo.add_animal(Dog("Rex"))\n'
            '    zoo.add_animal(Cat("Whiskers"))\n'
            '    zoo.add_animal(Bird("Tweety"))\n'
            '    zoo.add_animal(Bird("Pingu", can_fly=False))\n'
            "    return zoo\n\n"
            "def main() -> None:\n"
            "    zoo = build_zoo()\n"
            "    print(zoo.summary())\n"
            "    for line in zoo.all_speak():\n"
            "        print(line)\n\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        )
        sample_file.write_text(sample_code, encoding="utf-8")

        custom_settings = Settings(
            authorized_roots={"demo_project": demo_dir},
            database_path=self.base / "sample_cache.sqlite3",
        )
        custom_app = create_app(custom_settings)
        custom_client = TestClient(custom_app)
        try:
            sel_resp = custom_client.post(
                "/api/v1/editor/selection", json={"file_path": str(sample_file)}
            )
            self.assertEqual(sel_resp.status_code, 200)
            cap = sel_resp.json()

            sub_resp = custom_client.post(
                "/api/v1/analyses",
                json={
                    "project": {
                        "root_id": cap["root_id"],
                        "relative_path": cap["relative_path"],
                    }
                },
            )
            self.assertIn(sub_resp.status_code, (200, 202))
            ana_id = sub_resp.json()["analysis_id"]

            for _ in range(50):
                status_resp = custom_client.get(f"/api/v1/analyses/{ana_id}")
                if status_resp.json()["terminal"]:
                    break
                time.sleep(0.05)

            status_data = status_resp.json()
            self.assertEqual(status_data["state"], "completed")
            self.assertFalse(status_data["partial"])

            diag_resp = custom_client.get(f"/api/v1/analyses/{ana_id}/diagnostics")
            diag_codes = [d["code"] for d in diag_resp.json().get("items", [])]
            self.assertNotIn("UNAUTHORIZED_ROOT", diag_codes)

            graph_resp = custom_client.get(f"/api/v1/analyses/{ana_id}/graph")
            self.assertEqual(graph_resp.status_code, 200)
            graph = graph_resp.json()

            nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
            node_names = {n["name"]: n["kind"] for n in graph.get("nodes", [])}

            # Required Classes:
            for cls_name in ("Animal", "Dog", "Cat", "Bird", "Zoo"):
                self.assertIn(cls_name, node_names)
                self.assertEqual(node_names[cls_name], "class")

            # Required Free functions:
            for fn_name in ("describe_animal", "build_zoo", "main"):
                self.assertIn(fn_name, node_names)
                self.assertEqual(node_names[fn_name], "function")

            # Must represent actual sample, not demo_project
            self.assertNotIn("DemoService", node_names)
            self.assertNotIn("DataService", node_names)

            # Important relationships:
            edges = graph.get("edges", [])
            edge_tuples = []
            for e in edges:
                src_node = nodes_by_id.get(e["source_id"])
                tgt_node = nodes_by_id.get(e["target_id"])
                src_name = src_node["name"] if src_node else e["source_id"]
                tgt_name = tgt_node["name"] if tgt_node else e["target_id"]
                edge_tuples.append(
                    (
                        e["kind"],
                        src_name,
                        tgt_name,
                        e["resolution_status"],
                        e["confidence"],
                    )
                )

            # Dog inherits Animal
            self.assertTrue(
                any(
                    k == "inherits" and s == "Dog" and t == "Animal"
                    for k, s, t, _, _ in edge_tuples
                ),
                f"Dog inherits Animal not found in: {edge_tuples}",
            )
            # Cat inherits Animal
            self.assertTrue(
                any(
                    k == "inherits" and s == "Cat" and t == "Animal"
                    for k, s, t, _, _ in edge_tuples
                ),
                f"Cat inherits Animal not found in: {edge_tuples}",
            )
            # Bird inherits Animal
            self.assertTrue(
                any(
                    k == "inherits" and s == "Bird" and t == "Animal"
                    for k, s, t, _, _ in edge_tuples
                ),
                f"Bird inherits Animal not found in: {edge_tuples}",
            )
            # main calls build_zoo
            self.assertTrue(
                any(
                    k == "calls" and s == "main" and t == "build_zoo"
                    for k, s, t, _, _ in edge_tuples
                ),
                f"main calls build_zoo not found in: {edge_tuples}",
            )
            # build_zoo constructs Zoo, Dog, Cat, and Bird
            for constructed in ("Zoo", "Dog", "Cat", "Bird"):
                self.assertTrue(
                    any(
                        k == "constructs" and s == "build_zoo" and t == constructed
                        for k, s, t, _, _ in edge_tuples
                    ),
                    f"build_zoo constructs {constructed} not found in: {edge_tuples}",
                )
            # Animal.describe calls Animal.speak
            self.assertTrue(
                any(
                    k == "calls" and s == "describe" and t == "speak"
                    for k, s, t, _, _ in edge_tuples
                ),
                f"Animal.describe calls Animal.speak not found in: {edge_tuples}",
            )
            # Zoo.summary calls describe_animal
            self.assertTrue(
                any(
                    k == "calls" and s == "summary" and t == "describe_animal"
                    for k, s, t, _, _ in edge_tuples
                ),
                f"Zoo.summary calls describe_animal not found in: {edge_tuples}",
            )
        finally:
            custom_app.state.analysis_service.shutdown()

    def test_end_to_end_single_file_isolation_with_sibling_and_sample_project(
        self,
    ) -> None:
        project_dir = self.base / "isolated_workspace"
        project_dir.mkdir()
        selected_file = project_dir / "target_worker.py"
        selected_file.write_text(
            "class WorkerService:\n"
            "    def perform_work(self) -> str:\n"
            "        return 'done'\n",
            encoding="utf-8",
        )
        sibling_file = project_dir / "sibling_helper.py"
        sibling_file.write_text(
            "class SiblingHelper:\n    def sibling_leak(self) -> None:\n        pass\n",
            encoding="utf-8",
        )
        sample_like_file = self.base / "sample_project_fixture.py"
        sample_like_file.write_text(
            "class SampleFixtureService:\n"
            "    def sample_leak(self) -> None:\n"
            "        pass\n",
            encoding="utf-8",
        )

        # 1. Register only the selected Python file via POST /api/v1/editor/selection
        sel_resp = self.client.post(
            "/api/v1/editor/selection", json={"file_path": str(selected_file)}
        )
        self.assertEqual(sel_resp.status_code, 200)
        sel_data = sel_resp.json()
        cap_id = sel_data["capability_id"]
        rel_path = sel_data["relative_path"]
        self.assertTrue(cap_id.startswith("cap_"))
        self.assertEqual(rel_path, "target_worker.py")

        # 2. Submit analysis using capability_id and relative_path
        sub_resp = self.client.post(
            "/api/v1/analyses",
            json={
                "project": {
                    "capability_id": cap_id,
                    "relative_path": rel_path,
                }
            },
        )
        self.assertIn(sub_resp.status_code, (200, 202))
        analysis_id = sub_resp.json()["analysis_id"]

        # 3. Poll until completed
        for _ in range(50):
            job_status = self.client.get(f"/api/v1/analyses/{analysis_id}").json()
            if job_status["terminal"]:
                break
            time.sleep(0.05)

        self.assertEqual(job_status["state"], "completed")
        self.assertFalse(job_status["partial"])

        # 4. Retrieve graph
        graph_resp = self.client.get(f"/api/v1/analyses/{analysis_id}/graph")
        self.assertEqual(graph_resp.status_code, 200)
        graph = graph_resp.json()

        # Assert graph contains selected file's nodes
        node_names = {n["name"] for n in graph.get("nodes", [])}
        self.assertIn("target_worker.py", node_names)
        self.assertIn("target_worker", node_names)
        self.assertIn("WorkerService", node_names)
        self.assertIn("perform_work", node_names)

        # Assert it contains NO nodes from sibling or sample-project files
        self.assertNotIn("sibling_helper.py", node_names)
        self.assertNotIn("sibling_helper", node_names)
        self.assertNotIn("SiblingHelper", node_names)
        self.assertNotIn("sibling_leak", node_names)
        self.assertNotIn("sample_project_fixture.py", node_names)
        self.assertNotIn("SampleFixtureService", node_names)
        self.assertNotIn("sample_leak", node_names)

        # Assert serialized graph does not contain absolute temporary directory or selected absolute path
        serialized_graph = str(graph)
        self.assertNotIn(str(project_dir), serialized_graph)
        self.assertNotIn(str(selected_file), serialized_graph)
        self.assertNotIn(str(self.base), serialized_graph)
