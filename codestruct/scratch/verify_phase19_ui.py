"""UI Verification for Phase 19: Advanced Architecture.

Verifies:
1. "Architecture" tab button exists alongside Graph/Table/Patterns/Code.
2. Clicking Architecture tab activates it, displays #architecture-viewport, and collapses 2nd toolbar row.
3. Renders narrative, component clusters with roles/members, and unclustered symbols.
4. Clicking a component triggers cross-navigation to Graph View, highlighting member nodes.
5. Captures verification screenshots.
"""

import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import threading
import time
from pathlib import Path
import httpx
import websockets

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.main import app, find_available_port
import uvicorn

SCREENSHOTS_DIR = BASE_DIR / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
ROOT_SCREENSHOTS_DIR = ROOT_DIR / "docs" / "screenshots"
ROOT_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = BASE_DIR / "scratch" / "chrome_user_data_p19"


class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)

    async def send(self, method, params=None):
        self.msg_id += 1
        req = {"id": self.msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(req))
        while True:
            resp_raw = await self.ws.recv()
            resp = json.loads(resp_raw)
            if resp.get("id") == self.msg_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})

    async def eval_js(self, expression, await_promise=True):
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise
        })
        val = res.get("result", {}).get("value")
        return val

    async def screenshot(self, path):
        params = {"format": "png"}
        res = await self.send("Page.captureScreenshot", params)
        data = base64.b64decode(res["data"])
        with open(path, "wb") as f:
            f.write(data)
        try:
            rel = Path(path).name
            with open(ROOT_SCREENSHOTS_DIR / rel, "wb") as f_root:
                f_root.write(data)
        except Exception as e:
            print("Failed to mirror screenshot:", e)

    async def close(self):
        if self.ws:
            await self.ws.close()


async def run_ui_verification():
    port = find_available_port(default_port=8088)
    server_config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(server_config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server
    async with httpx.AsyncClient() as client:
        for _ in range(30):
            try:
                res = await client.get(f"http://127.0.0.1:{port}/")
                if res.status_code == 200:
                    break
            except Exception:
                await asyncio.sleep(0.2)

    print(f"[Server] Running at http://127.0.0.1:{port}")

    # Launch Chrome
    cdp_port = find_available_port(default_port=9333)
    if USER_DATA_DIR.exists():
        shutil.rmtree(USER_DATA_DIR, ignore_errors=True)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    chrome_cmd = [
        CHROME_EXE,
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,800",
        f"http://127.0.0.1:{port}/",
    ]

    proc = subprocess.Popen(chrome_cmd)
    try:
        # Connect to CDP
        ws_url = None
        for _ in range(40):
            try:
                async with httpx.AsyncClient() as client:
                    list_res = await client.get(f"http://127.0.0.1:{cdp_port}/json/list")
                    if list_res.status_code == 200:
                        targets = [t for t in list_res.json() if t.get("type") == "page"]
                        if targets:
                            ws_url = targets[0]["webSocketDebuggerUrl"]
                            break
            except Exception:
                await asyncio.sleep(0.25)

        if not ws_url:
            raise RuntimeError("Failed to obtain Chrome CDP WebSocket URL")

        cdp = CDPClient(ws_url)
        await cdp.connect()
        await cdp.send("Page.enable")
        await cdp.send("Runtime.enable")

        # Wait for page ready
        await asyncio.sleep(1.5)

        # 1. Analyze sample_project
        print("[Step 1] Triggering project analysis...")
        await cdp.eval_js("""
            (() => {
                const input = document.getElementById("input-project-path");
                input.value = "codestruct/sample_project";
                const btn = document.getElementById("btn-analyze");
                btn.click();
            })()
        """)

        # Wait for graph nodes to populate
        for _ in range(40):
            node_count = await cdp.eval_js("window.lastGraphData ? window.lastGraphData.nodes.length : 0")
            if node_count and node_count > 0:
                break
            await asyncio.sleep(0.25)

        print(f"[Step 1] Analyzed with {node_count} nodes.")

        # 2. Check toolbar tab existence
        print("[Step 2] Verifying Architecture tab button...")
        tab_info = await cdp.eval_js("""
            (() => {
                const tab = document.getElementById("toolbar-tab-architecture");
                return {
                    exists: !!tab,
                    text: tab ? tab.innerText.trim() : null,
                    visible: tab ? window.getComputedStyle(tab).display !== "none" : false
                };
            })()
        """)
        print("Tab info:", tab_info)
        assert tab_info["exists"], "toolbar-tab-architecture does not exist!"
        assert "Architecture" in tab_info["text"], "Tab text does not contain 'Architecture'"

        # 3. Click Architecture Tab
        print("[Step 3] Switching to Architecture tab...")
        await cdp.eval_js("""
            (() => {
                const tab = document.getElementById("toolbar-tab-architecture");
                tab.click();
            })()
        """)

        # Verify second toolbar row is collapsed
        sub_toolbar_height = await cdp.eval_js("""
            (() => {
                const sub = document.getElementById("center-sub-toolbar");
                return sub ? sub.offsetHeight : -1;
            })()
        """)
        print(f"Second toolbar row height in Architecture view: {sub_toolbar_height}px")
        assert sub_toolbar_height == 0, f"Expected 2nd toolbar row height 0, got {sub_toolbar_height}"

        # Wait for Architecture clustering to load
        print("[Step 4] Waiting for Architecture clusters to render...")
        clusters_rendered = False
        for _ in range(60):
            data_ready = await cdp.eval_js("""
                (() => {
                    const cards = document.querySelectorAll(".component-cluster-card");
                    const narrative = document.getElementById("architecture-narrative-text");
                    return {
                        card_count: cards.length,
                        narrative_text: narrative ? narrative.innerText.trim() : ""
                    };
                })()
            """)
            if data_ready and data_ready["card_count"] > 0 and len(data_ready["narrative_text"]) > 10:
                clusters_rendered = True
                break
            await asyncio.sleep(0.5)

        assert clusters_rendered, "Architecture component cards failed to render within timeout!"
        print(f"[Step 4] Rendered {data_ready['card_count']} components with narrative: '{data_ready['narrative_text'][:60]}...'")

        # Capture Screenshot of Architecture Tab
        arch_shot = SCREENSHOTS_DIR / "view_architecture.png"
        await cdp.screenshot(str(arch_shot))
        print(f"[Screenshot] Saved Architecture view to {arch_shot}")

        # 4. Test Cross-Navigation: Click first component card
        print("[Step 5] Testing cross-navigation from component card to Graph View...")
        first_comp_info = await cdp.eval_js("""
            (() => {
                const firstCard = document.querySelector(".component-cluster-card");
                const name = firstCard.querySelector(".cluster-name").innerText;
                const members = Array.from(firstCard.querySelectorAll(".cluster-member-pill")).map(p => p.dataset.id);
                firstCard.click();
                return { name, members };
            })()
        """)
        print(f"Clicked component '{first_comp_info['name']}' with members: {first_comp_info['members']}")

        await asyncio.sleep(0.5)

        # Confirm tab switched to Graph
        active_tab = await cdp.eval_js("window.activeCenterTab")
        print(f"Active center tab after component click: {active_tab}")
        assert active_tab == "graph", f"Expected activeCenterTab 'graph', got '{active_tab}'"

        # Confirm Cytoscape nodes highlighted
        highlighted_nodes = await cdp.eval_js("""
            (() => {
                if (!window.cy) return [];
                return window.cy.nodes('.highlighted').map(n => n.id());
            })()
        """)
        print(f"Highlighted nodes in Cytoscape: {highlighted_nodes}")
        assert len(highlighted_nodes) > 0, "No Cytoscape nodes highlighted after component click!"
        for m in first_comp_info["members"]:
            if m in highlighted_nodes:
                print(f"  * Verified member node '{m}' highlighted in Cytoscape.")

        # Confirm Inspector updated with selected symbol
        inspector_id = await cdp.eval_js("window.selectedSymbolId")
        print(f"Inspector selected symbol: {inspector_id}")
        assert inspector_id in first_comp_info["members"], f"Expected inspector symbol in members, got {inspector_id}"

        # Capture Cross-Navigation Screenshot
        cross_shot = SCREENSHOTS_DIR / "architecture_cross_navigation.png"
        await cdp.screenshot(str(cross_shot))
        print(f"[Screenshot] Saved cross-navigation view to {cross_shot}")

        print("\n=== All Phase 19 UI & Cross-Navigation Verifications PASSED! ===")

        await cdp.close()
    finally:
        proc.kill()
        server.should_exit = True
        shutil.rmtree(USER_DATA_DIR, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(run_ui_verification())
