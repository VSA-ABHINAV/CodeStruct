"""
Register test project with CodeStruct backend and poll analysis completion.
Outputs the analysis_id and viewer URL.
"""
import json
import os
from pathlib import Path
import time
import urllib.request

test_dir = Path("D:/REP/Codestruct/Codestruct/scratch/rich_analysis_fixture").resolve()
test_dir.mkdir(parents=True, exist_ok=True)

# 1. Write rich sample files with normal and unresolved/external symbols
(test_dir / "app.py").write_text(
    "from services.data_processor import Processor\n"
    "import nonexistent_module\n\n"
    "class Application:\n"
    "    def __init__(self, name: str = 'CodeStruct'):\n"
    "        self.name = name\n"
    "        self.processor = Processor()\n\n"
    "    def run(self) -> bool:\n"
    "        res = self.processor.execute()\n"
    "        nonexistent_module.missing_function(res)\n"
    "        return res\n\n"
    "def bootstrap():\n"
    "    app = Application()\n"
    "    return app.run()\n",
    encoding="utf-8"
)

(test_dir / "services").mkdir(exist_ok=True)
(test_dir / "services" / "data_processor.py").write_text(
    "class BaseWorker:\n"
    "    def setup(self):\n"
    "        pass\n\n"
    "class Processor(BaseWorker):\n"
    "    def __init__(self, rate: int = 10):\n"
    "        self.rate = rate\n\n"
    "    def execute(self) -> bool:\n"
    "        self.setup()\n"
    "        return True\n",
    encoding="utf-8"
)

# 2. Register folder with backend
reg_url = "http://127.0.0.1:8000/api/v1/host/register-folder"
payload = json.dumps({"path": str(test_dir)}).encode("utf-8")
req = urllib.request.Request(reg_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=10.0) as resp:
    data = json.loads(resp.read().decode("utf-8"))

analysis_id = data["analysis_id"]
root_id = data["root_id"]
print(f"Registered! analysis_id={analysis_id}, root_id={root_id}")

# 3. Poll analysis completion
for _ in range(30):
    status_url = f"http://127.0.0.1:8000/api/v1/analyses/{analysis_id}"
    req = urllib.request.Request(status_url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        adata = json.loads(resp.read().decode("utf-8"))
    if adata.get("terminal"):
        print(f"Analysis terminal state: {adata.get('state')}")
        break
    time.sleep(0.5)

# 4. Fetch graph to verify nodes and unresolved symbols
graph_url = f"http://127.0.0.1:8000/api/v1/analyses/{analysis_id}/graph"
with urllib.request.urlopen(graph_url) as resp:
    gdata = json.loads(resp.read().decode("utf-8"))

nodes = gdata.get("nodes", [])
edges = gdata.get("edges", [])
print(f"Graph loaded: {len(nodes)} nodes, {len(edges)} edges")

unresolved = [n for n in nodes if n.get("kind") == "unresolved_symbol" or n.get("is_external")]
print(f"Unresolved/external nodes: {[n.get('label') for n in unresolved]}")

viewer_url = f"http://127.0.0.1:5173/?embed=thonny&analysisId={analysis_id}&projectId={root_id}&sessionToken={root_id}"
print(f"VIEWER_URL: {viewer_url}")

# Save details to json file for subagent or tests
info = {
    "analysis_id": analysis_id,
    "root_id": root_id,
    "viewer_url": viewer_url,
    "nodes": nodes,
    "edges": edges,
    "unresolved": unresolved,
}
Path("D:/REP/Codestruct/Codestruct/scratch/test_analysis_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
print("Saved analysis info to scratch/test_analysis_info.json")
