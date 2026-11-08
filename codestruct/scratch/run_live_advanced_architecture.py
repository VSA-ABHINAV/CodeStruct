"""Live Qualitative Run (Unmocked) for Phase 19.

Runs /api/architecture/advanced live against sample_project with qwen2.5-coder:3b.
Prints exact input summary, LLM output, validation results, and final validated architecture.
"""

import json
import logging
import sys
import time
from pathlib import Path

# Setup logging to see validation messages
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

pkg_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pkg_dir))

from backend.main import app
from fastapi.testclient import TestClient

sample_dir = pkg_dir / "sample_project"

print(f"=== Phase 19 Live Qualitative Run (Unmocked) ===")
print(f"Target project: {sample_dir}")

with TestClient(app) as client:
    # 1. Analyze sample_project
    print("\n1. Calling POST /api/analyze...")
    t0 = time.time()
    resp_analyze = client.post("/api/analyze", json={"project_path": str(sample_dir)})
    print(f"Analyze status: {resp_analyze.status_code} ({time.time() - t0:.2f}s)")
    if resp_analyze.status_code != 200:
        print("Analysis failed:", resp_analyze.text)
        sys.exit(1)

    # 2. Call POST /api/architecture/advanced (live, unmocked)
    print("\n2. Calling POST /api/architecture/advanced (live unmocked with qwen2.5-coder:3b)...")
    t1 = time.time()
    resp_arch = client.post("/api/architecture/advanced", json={"force_refresh": True})
    elapsed = time.time() - t1
    print(f"Advanced Architecture status: {resp_arch.status_code} ({elapsed:.2f}s)")

    if resp_arch.status_code != 200:
        print("Live run failed:", resp_arch.text)
        sys.exit(1)

    result = resp_arch.json()
    print("\n=== Validated Architecture Result ===")
    print(json.dumps(result, indent=2))

    print("\n=== Clustering Assessment ===")
    components = result.get("components", [])
    print(f"Component count: {len(components)}")
    for c in components:
        print(f"\n- Component: {c.get('name')} (ID: {c.get('component_id')})")
        print(f"  Role: {c.get('role')}")
        print(f"  Members ({len(c.get('member_symbol_ids', []))}): {c.get('member_symbol_ids')}")
        print(f"  Rationale: {c.get('rationale')}")

    unclustered = result.get("unclustered_symbol_ids", [])
    print(f"\nUnclustered symbols ({len(unclustered)}): {unclustered}")
    print(f"\nNarrative:\n{result.get('narrative')}")

