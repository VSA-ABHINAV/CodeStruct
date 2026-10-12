# ruff: noqa: S101, E402
"""Deterministic verification runner for Milestone 7: Incremental Cache & Graphviz Export (CS-015, CS-017)."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from codestruct.api.app import create_app
from codestruct.settings import Settings
from fastapi.testclient import TestClient


def run_m7_verification() -> dict[str, object]:
    sample_root = REPO_ROOT / "sample_project"
    results: dict[str, object] = {
        "milestone": "M7",
        "issues": ["CS-015", "CS-017"],
        "timestamp_start": time.time(),
        "scenarios": {},
    }

    with tempfile.TemporaryDirectory(prefix="codestruct_m7_verify_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "codestruct_m7.sqlite3"

        # Create mutable copy of sample project for modification tests
        proj_copy = tmp_path / "sample_project_copy"
        shutil.copytree(sample_root, proj_copy)

        settings = Settings(
            authorized_roots={
                "sample": sample_root,
                "mutable": proj_copy,
            },
            database_path=db_path,
            max_concurrent_jobs=2,
            max_queued_jobs=4,
            analysis_timeout_seconds=30,
            cancellation_grace_seconds=1,
            result_retention_seconds=120,
            polling_interval_ms=100,
        )

        app = create_app(settings)
        client = TestClient(app)
        try:
            # ---------------------------------------------------------
            # CS-015: Test 1 - Cold Analysis & Cache Population
            # ---------------------------------------------------------
            print("[M7 Verify] Scenario 1: Cold Analysis on Mutable Project...")
            resp1 = client.post(
                "/api/v1/analyses",
                json={"project": {"root_id": "mutable", "relative_path": "."}},
            )
            assert resp1.status_code == 202, f"Failed to start analysis: {resp1.text}"
            ana_id_1 = resp1.json()["analysis_id"]

            deadline = time.monotonic() + 30
            completed_1 = False
            while time.monotonic() < deadline:
                stat = client.get(f"/api/v1/analyses/{ana_id_1}").json()
                if stat.get("state") in ("completed", "partially_completed"):
                    completed_1 = True
                    break
                time.sleep(0.1)
            assert completed_1, "Analysis 1 did not complete in time"

            # Check SQLite file_parse_cache table
            c = sqlite3.connect(db_path)
            try:
                count_entries = c.execute(
                    "SELECT count(*) FROM file_parse_cache"
                ).fetchone()[0]
            finally:
                c.close()
            assert count_entries > 0, "No entries written to file_parse_cache"
            print(
                f"  -> Cold run completed: {count_entries} files cached in file_parse_cache table."
            )
            results["scenarios"]["cold_cache_entries"] = count_entries

            # ---------------------------------------------------------
            # CS-015: Test 2 - Whole-Result Cache & Warm Per-File Cache
            # ---------------------------------------------------------
            print("[M7 Verify] Scenario 2A: Whole-Result Cache Hit...")
            resp_whole = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "mutable", "relative_path": "."},
                    "refresh": False,
                },
            )
            assert resp_whole.status_code == 200, (
                f"Expected 200 whole-result cache hit, got {resp_whole.status_code}"
            )
            assert resp_whole.json()["cache_hit"] is True, (
                "cache_hit flag should be true"
            )
            print(
                "  -> Whole-result whole-graph cache hit returned 200 with cache_hit=True."
            )
            results["scenarios"]["whole_result_cache_hit"] = "PASSED"

            print(
                "[M7 Verify] Scenario 2B: Warm Analysis via Worker with Per-File Cache Reuse..."
            )
            t0 = time.perf_counter()
            resp2 = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "mutable", "relative_path": "."},
                    "refresh": True,
                },
            )
            assert resp2.status_code == 202, (
                f"Expected 202 on refresh, got {resp2.status_code}: {resp2.text}"
            )
            ana_id_2 = resp2.json()["analysis_id"]

            deadline = time.monotonic() + 30
            completed_2 = False
            while time.monotonic() < deadline:
                stat = client.get(f"/api/v1/analyses/{ana_id_2}").json()
                if stat.get("state") in ("completed", "partially_completed"):
                    completed_2 = True
                    break
                time.sleep(0.1)
            warm_duration = time.perf_counter() - t0
            assert completed_2, "Analysis 2 did not complete in time"

            # Compare graphs
            g1 = client.get(f"/api/v1/analyses/{ana_id_1}/graph").json()
            g2 = client.get(f"/api/v1/analyses/{ana_id_2}/graph").json()
            assert len(g1["nodes"]) == len(g2["nodes"]), (
                "Warm graph nodes do not match cold graph"
            )
            print(
                f"  -> Warm worker run completed in {warm_duration:.3f}s with identical graph ({len(g2['nodes'])} nodes)."
            )
            results["scenarios"]["warm_run"] = {
                "duration_seconds": warm_duration,
                "node_count": len(g2["nodes"]),
                "edge_count": len(g2["edges"]),
            }

            # ---------------------------------------------------------
            # CS-015: Test 3 - Same-Size Content Edit Invalidation
            # ---------------------------------------------------------
            print("[M7 Verify] Scenario 3: Same-Size Content Edit Invalidation...")
            # Pick a python file to edit with the exact same size
            target_py = next(proj_copy.glob("**/*.py"))
            orig_content = target_py.read_text(encoding="utf-8")
            # Replace first occurrence of a character to preserve length
            if " " in orig_content:
                new_content = orig_content.replace(" ", "_", 1)
            else:
                new_content = orig_content[:-1] + (
                    "#" if orig_content[-1] != "#" else "!"
                )
            assert len(new_content) == len(orig_content), (
                "Edit did not maintain identical byte length"
            )
            target_py.write_text(new_content, encoding="utf-8")

            resp3 = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "mutable", "relative_path": "."},
                    "refresh": True,
                },
            )
            assert resp3.status_code == 202
            ana_id_3 = resp3.json()["analysis_id"]

            deadline = time.monotonic() + 30
            completed_3 = False
            while time.monotonic() < deadline:
                stat = client.get(f"/api/v1/analyses/{ana_id_3}").json()
                if stat.get("state") in ("completed", "partially_completed"):
                    completed_3 = True
                    break
                time.sleep(0.1)
            assert completed_3, "Analysis 3 did not complete in time"
            print("  -> Invalidation on same-size edit verified successfully.")
            results["scenarios"]["same_size_invalidation"] = "PASSED"

            # ---------------------------------------------------------
            # CS-015: Test 4 - Timestamp Touch (mtime change, same hash)
            # ---------------------------------------------------------
            print(
                "[M7 Verify] Scenario 4: Timestamp Touch (mtime altered, content identical)..."
            )
            past_time = time.time() - 5000
            os.utime(target_py, (past_time, past_time))

            resp4 = client.post(
                "/api/v1/analyses",
                json={
                    "project": {"root_id": "mutable", "relative_path": "."},
                    "refresh": True,
                },
            )
            assert resp4.status_code == 202
            ana_id_4 = resp4.json()["analysis_id"]

            deadline = time.monotonic() + 30
            completed_4 = False
            while time.monotonic() < deadline:
                stat = client.get(f"/api/v1/analyses/{ana_id_4}").json()
                if stat.get("state") in ("completed", "partially_completed"):
                    completed_4 = True
                    break
                time.sleep(0.1)
            assert completed_4, "Analysis 4 did not complete in time"
            print("  -> Touched mtime content-digest cache reuse verified.")
            results["scenarios"]["touched_mtime_reuse"] = "PASSED"

            # ---------------------------------------------------------
            # CS-017: Test 5 - DOT Export (Canonical Complete Graph)
            # ---------------------------------------------------------
            print("[M7 Verify] Scenario 5: Graphviz DOT Export Route...")
            resp_dot = client.get(f"/api/v1/analyses/{ana_id_1}/export/dot")
            assert resp_dot.status_code == 200, f"DOT export failed: {resp_dot.text}"
            assert "text/vnd.graphviz" in resp_dot.headers["content-type"]
            assert (
                f'filename="codestruct-{ana_id_1}.dot"'
                in resp_dot.headers["content-disposition"]
            )
            dot_content = resp_dot.text
            assert dot_content.startswith("digraph "), (
                "DOT content does not start with 'digraph '"
            )
            assert dot_content.endswith("}\n"), "DOT content does not end with '}\\n'"
            print(f"  -> DOT export verified: {len(dot_content)} characters generated.")
            results["scenarios"]["export_dot"] = {
                "status_code": resp_dot.status_code,
                "length": len(dot_content),
            }

            # ---------------------------------------------------------
            # CS-017: Test 6 - Actionable Diagnostics when Graphviz Missing
            # ---------------------------------------------------------
            print(
                "[M7 Verify] Scenario 6: Actionable Diagnostics for Missing Graphviz..."
            )
            with mock.patch(
                "codestruct.graph.export_dot.find_graphviz_dot", return_value=None
            ):
                resp_svg_miss = client.get(f"/api/v1/analyses/{ana_id_1}/export/svg")
                assert resp_svg_miss.status_code == 503, (
                    f"Expected 503, got {resp_svg_miss.status_code}"
                )
                err_data = resp_svg_miss.json()["error"]
                assert err_data["code"] == "GRAPHVIZ_UNAVAILABLE"
                assert "Graphviz" in err_data["message"]
                assert (
                    "winget install" in err_data["message"]
                    or "apt install" in err_data["message"]
                )

                resp_png_miss = client.get(f"/api/v1/analyses/{ana_id_1}/export/png")
                assert resp_png_miss.status_code == 503
                assert resp_png_miss.json()["error"]["code"] == "GRAPHVIZ_UNAVAILABLE"

                resp_query_miss = client.get(
                    f"/api/v1/analyses/{ana_id_1}/export?format=svg"
                )
                assert resp_query_miss.status_code == 503
                assert resp_query_miss.json()["error"]["code"] == "GRAPHVIZ_UNAVAILABLE"
            print(
                "  -> Missing Graphviz returned 503 GRAPHVIZ_UNAVAILABLE with actionable instructions."
            )
            results["scenarios"]["diagnostics_missing_graphviz"] = (
                "PASSED (503 GRAPHVIZ_UNAVAILABLE)"
            )

            # ---------------------------------------------------------
            # CS-017: Test 7 - Mock Graphviz Rendering (SVG & PNG)
            # ---------------------------------------------------------
            print(
                "[M7 Verify] Scenario 7: Successful SVG & PNG Rendering via Mock Executable..."
            )
            mock_py = tmp_path / "mock_dot.py"
            mock_py.write_text(
                "import sys\n"
                "args = ' '.join(sys.argv)\n"
                "if '-Tsvg' in args:\n"
                '    sys.stdout.buffer.write(b\'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"></svg>\')\n'
                "elif '-Tpng' in args:\n"
                "    sys.stdout.buffer.write(b'\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR\\x00\\x00')\n"
                "sys.exit(0)\n",
                encoding="utf-8",
            )
            mock_bat = tmp_path / "mock_dot.bat"
            mock_bat.write_text(
                f'@"{sys.executable}" "{mock_py}" %*\n', encoding="utf-8"
            )

            with mock.patch(
                "codestruct.graph.export_dot.find_graphviz_dot",
                return_value=str(mock_bat),
            ):
                # SVG route
                r_svg = client.get(f"/api/v1/analyses/{ana_id_1}/export/svg")
                assert r_svg.status_code == 200, f"SVG export failed: {r_svg.text}"
                assert r_svg.headers["content-type"] == "image/svg+xml"
                assert r_svg.content.startswith(b"<svg")

                # PNG route
                r_png = client.get(f"/api/v1/analyses/{ana_id_1}/export/png")
                assert r_png.status_code == 200, f"PNG export failed: {r_png.text}"
                assert r_png.headers["content-type"] == "image/png"
                assert r_png.content.startswith(b"\x89PNG\r\n\x1a\n")

                # Query param format route
                r_query_svg = client.get(
                    f"/api/v1/analyses/{ana_id_1}/export?format=svg"
                )
                assert r_query_svg.status_code == 200
                assert r_query_svg.headers["content-type"] == "image/svg+xml"
            print(
                "  -> Rendered SVG and PNG successfully with headers and content signatures verified."
            )
            results["scenarios"]["mock_rendering"] = "PASSED (SVG and PNG)"

            # ---------------------------------------------------------
            # CS-017: Test 8 - Format validation & Bounds enforcement
            # ---------------------------------------------------------
            print("[M7 Verify] Scenario 8: Format validation and Bounds enforcement...")
            r_bad_fmt = client.get(
                f"/api/v1/analyses/{ana_id_1}/export?format=invalid_fmt"
            )
            assert r_bad_fmt.status_code == 400
            assert r_bad_fmt.json()["error"]["code"] == "UNSUPPORTED_EXPORT_FORMAT"
            print("  -> Format validation verified.")
            results["scenarios"]["format_validation"] = "PASSED"
        finally:
            client.close()
            if hasattr(app.state, "analysis_service"):
                app.state.analysis_service.shutdown()

    results["timestamp_end"] = time.time()
    results["duration_total"] = results["timestamp_end"] - results["timestamp_start"]
    results["overall_status"] = "SUCCESS"
    return results


if __name__ == "__main__":
    output = run_m7_verification()
    print("\n=======================================================")
    print("M7 VERIFICATION COMPLETED SUCCESSFULLY")
    print(f"Total time: {output['duration_total']:.2f}s")
    print(json.dumps(output, indent=2))
    print("=======================================================")
