import asyncio
import base64
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import httpx
import websockets

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.main import app
import uvicorn

SCREENSHOTS_DIR = BASE_DIR / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
ROOT_SCREENSHOTS_DIR = ROOT_DIR / "docs" / "screenshots"
ROOT_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
user_data = BASE_DIR / "scratch" / "chrome_user_data_f2"

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

    async def screenshot(self, path, clip=None):
        params = {"format": "png"}
        if clip:
            params["clip"] = clip
        res = await self.send("Page.captureScreenshot", params)
        data = base64.b64decode(res["data"])
        with open(path, "wb") as f:
            f.write(data)
        # Also mirror to root docs/screenshots
        try:
            rel = Path(path).name
            with open(ROOT_SCREENSHOTS_DIR / rel, "wb") as f_root:
                f_root.write(data)
        except Exception:
            pass
        print(f"[CDP] Saved screenshot: {path} ({len(data)} bytes)", flush=True)

    async def close(self):
        if self.ws:
            await self.ws.close()

results = {}

async def run_automation():
    port = 9225
    proc = subprocess.Popen([
        CHROME_EXE,
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data}",
        "--window-size=1280,800",
        "--hide-scrollbars",
        "--disable-gpu",
        "--disable-extensions",
        "about:blank"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        ws_url = None
        for _ in range(40):
            try:
                r = httpx.get(f"http://127.0.0.1:8000/json/list", timeout=1.0)
            except Exception:
                pass
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/json/list", timeout=1.0)
                if r.status_code == 200:
                    targets = [t for t in r.json() if t.get("type") == "page"]
                    if targets:
                        ws_url = targets[0]["webSocketDebuggerUrl"]
                        break
            except Exception:
                pass
            await asyncio.sleep(0.2)

        if not ws_url:
            raise RuntimeError("Could not connect to Chrome debugging port")

        print(f"[CDP] Connected to Chrome: {ws_url}", flush=True)
        cdp = CDPClient(ws_url)
        await cdp.connect()

        await cdp.send("Page.enable")
        await cdp.send("Runtime.enable")
        await cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1280,
            "height": 800,
            "deviceScaleFactor": 1,
            "mobile": False
        })

        print("[CDP] Navigating to http://127.0.0.1:8000...", flush=True)
        await cdp.send("Page.navigate", {"url": "http://127.0.0.1:8000"})
        await asyncio.sleep(2.0)

        # 1. Run analysis on sample_project
        print("[CDP] Analyzing sample_project...", flush=True)
        await cdp.eval_js('window.runAnalysis("sample_project")', await_promise=True)
        await asyncio.sleep(1.0)

        # 2. Select Animal & enter draft Qwen message
        await cdp.eval_js('window.selectSymbol("Animal")', await_promise=False)
        await cdp.eval_js('document.getElementById("chat-input").value = "Why does Animal have subclasses?"', await_promise=False)
        await asyncio.sleep(0.5)

        # ----------------------------------------------------
        # TEST 1: Inspector Dock Collapse & Re-Expand via Rail
        # ----------------------------------------------------
        print("\n--- Test 1: Inspector Dock Collapse & Re-Expand ---", flush=True)
        # Collapse Inspector
        await cdp.eval_js('document.getElementById("btn-toggle-inspector").click()', await_promise=False)
        await asyncio.sleep(0.5)

        insp_collapsed_check = await cdp.eval_js('''
            (() => {
                const insp = document.getElementById("inspector-panel");
                const rail = document.getElementById("rail-inspector");
                const btn = document.getElementById("btn-toggle-inspector");
                const label = rail ? rail.querySelector(".dock-rail-label").textContent.trim() : null;
                const rect = rail ? rail.getBoundingClientRect() : null;
                const inspRect = insp ? insp.getBoundingClientRect() : null;
                const bodyVisible = insp && insp.querySelector(".inspector-body") ? window.getComputedStyle(insp.querySelector(".inspector-body")).display !== "none" : false;

                return {
                    isCollapsed: insp ? insp.classList.contains("dock-collapsed") : false,
                    railDisplay: rail ? window.getComputedStyle(rail).display : null,
                    railWidth: rect ? rect.width : 0,
                    railHeight: rect ? rect.height : 0,
                    label: label,
                    inspWidth: inspRect ? inspRect.width : 0,
                    bodyVisible: bodyVisible
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Inspector Collapsed: {json.dumps(insp_collapsed_check, indent=2)}", flush=True)
        results["inspector_collapsed"] = insp_collapsed_check
        assert insp_collapsed_check["isCollapsed"] is True, "Inspector should have dock-collapsed class"
        assert insp_collapsed_check["railDisplay"] == "flex", "Inspector rail should have display: flex"
        assert insp_collapsed_check["railWidth"] == 40, f"Inspector rail width should be 40, got {insp_collapsed_check['railWidth']}"
        assert insp_collapsed_check["label"] == "INSPECTOR", "Inspector rail label should be INSPECTOR"
        assert insp_collapsed_check["bodyVisible"] is False, "Inspector body should be hidden"

        # Re-expand Inspector by clicking the rail
        print("[CDP] Clicking #rail-inspector to re-expand...", flush=True)
        await cdp.eval_js('document.getElementById("rail-inspector").click()', await_promise=False)
        await asyncio.sleep(0.5)

        insp_expanded_check = await cdp.eval_js('''
            (() => {
                const insp = document.getElementById("inspector-panel");
                const name = document.getElementById("inspector-name") ? document.getElementById("inspector-name").textContent.trim() : null;
                const rect = insp ? insp.getBoundingClientRect() : null;
                const bodyVisible = insp && insp.querySelector(".inspector-body") ? window.getComputedStyle(insp.querySelector(".inspector-body")).display !== "none" : false;

                return {
                    isCollapsed: insp ? insp.classList.contains("dock-collapsed") : false,
                    inspWidth: rect ? rect.width : 0,
                    inspHeight: rect ? rect.height : 0,
                    bodyVisible: bodyVisible,
                    selectedName: name
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Inspector Expanded: {json.dumps(insp_expanded_check, indent=2)}", flush=True)
        results["inspector_expanded"] = insp_expanded_check
        assert insp_expanded_check["isCollapsed"] is False, "Inspector should NOT have dock-collapsed class"
        assert insp_expanded_check["bodyVisible"] is True, "Inspector body should be visible again"
        assert insp_expanded_check["inspWidth"] > 200, "Inspector width should be restored"
        assert insp_expanded_check["selectedName"] == "Animal", "Inspector selected symbol 'Animal' should be preserved"

        # ----------------------------------------------------
        # TEST 2: Qwen Dock Collapse & Re-Expand via Rail
        # ----------------------------------------------------
        print("\n--- Test 2: Qwen Dock Collapse & Re-Expand ---", flush=True)
        # Collapse Qwen
        await cdp.eval_js('document.getElementById("btn-toggle-qwen").click()', await_promise=False)
        await asyncio.sleep(0.5)

        qwen_collapsed_check = await cdp.eval_js('''
            (() => {
                const qwen = document.getElementById("qwen-panel");
                const rail = document.getElementById("rail-qwen");
                const label = rail ? rail.querySelector(".dock-rail-label").textContent.trim() : null;
                const rect = rail ? rail.getBoundingClientRect() : null;
                const qwenRect = qwen ? qwen.getBoundingClientRect() : null;
                const historyVisible = qwen && qwen.querySelector(".chat-history") ? window.getComputedStyle(qwen.querySelector(".chat-history")).display !== "none" : false;
                const inputBarVisible = document.getElementById("chat-input-bar") ? window.getComputedStyle(document.getElementById("chat-input-bar")).display !== "none" : false;

                return {
                    isCollapsed: qwen ? qwen.classList.contains("dock-collapsed") : false,
                    railDisplay: rail ? window.getComputedStyle(rail).display : null,
                    railWidth: rect ? rect.width : 0,
                    railHeight: rect ? rect.height : 0,
                    label: label,
                    qwenWidth: qwenRect ? qwenRect.width : 0,
                    historyVisible: historyVisible,
                    inputBarVisible: inputBarVisible
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Qwen Collapsed: {json.dumps(qwen_collapsed_check, indent=2)}", flush=True)
        results["qwen_collapsed"] = qwen_collapsed_check
        assert qwen_collapsed_check["isCollapsed"] is True, "Qwen should have dock-collapsed class"
        assert qwen_collapsed_check["railDisplay"] == "flex", "Qwen rail should have display: flex"
        assert qwen_collapsed_check["railWidth"] == 40, f"Qwen rail width should be 40, got {qwen_collapsed_check['railWidth']}"
        assert qwen_collapsed_check["label"] == "QWEN", "Qwen rail label should be QWEN"
        assert qwen_collapsed_check["historyVisible"] is False, "Qwen chat history should be hidden"
        assert qwen_collapsed_check["inputBarVisible"] is False, "Qwen input bar should be hidden"

        # Re-expand Qwen by clicking the rail
        print("[CDP] Clicking #rail-qwen to re-expand...", flush=True)
        await cdp.eval_js('document.getElementById("rail-qwen").click()', await_promise=False)
        await asyncio.sleep(0.5)

        qwen_expanded_check = await cdp.eval_js('''
            (() => {
                const qwen = document.getElementById("qwen-panel");
                const rect = qwen ? qwen.getBoundingClientRect() : null;
                const historyVisible = qwen && qwen.querySelector(".chat-history") ? window.getComputedStyle(qwen.querySelector(".chat-history")).display !== "none" : false;
                const draftVal = document.getElementById("chat-input") ? document.getElementById("chat-input").value : null;

                return {
                    isCollapsed: qwen ? qwen.classList.contains("dock-collapsed") : false,
                    qwenWidth: rect ? rect.width : 0,
                    historyVisible: historyVisible,
                    draftInput: draftVal
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Qwen Expanded: {json.dumps(qwen_expanded_check, indent=2)}", flush=True)
        results["qwen_expanded"] = qwen_expanded_check
        assert qwen_expanded_check["isCollapsed"] is False, "Qwen should NOT have dock-collapsed class"
        assert qwen_expanded_check["historyVisible"] is True, "Qwen history should be visible again"
        assert qwen_expanded_check["qwenWidth"] > 200, "Qwen width should be restored"
        assert qwen_expanded_check["draftInput"] == "Why does Animal have subclasses?", f"Draft input was lost: {qwen_expanded_check['draftInput']}"

        # ----------------------------------------------------
        # TEST 3: All Four Docks Collapsed Simultaneously
        # ----------------------------------------------------
        print("\n--- Test 3: All Four Docks Collapsed Simultaneously ---", flush=True)
        await cdp.eval_js('''
            (() => {
                document.getElementById("btn-toggle-explorer").click();
                document.getElementById("btn-toggle-logs").click();
                document.getElementById("btn-toggle-inspector").click();
                document.getElementById("btn-toggle-qwen").click();
            })()
        ''', await_promise=False)
        await asyncio.sleep(1.0)

        all_four_check = await cdp.eval_js('''
            (() => {
                const left = document.getElementById("left-dock");
                const logs = document.getElementById("log-strip");
                const insp = document.getElementById("inspector-panel");
                const qwen = document.getElementById("qwen-panel");
                const right = document.getElementById("right-dock");
                const railExplorer = document.getElementById("rail-explorer");
                const railInsp = document.getElementById("rail-inspector");
                const railQwen = document.getElementById("rail-qwen");
                const stripLogs = document.getElementById("strip-logs");

                return {
                    leftWidth: left ? left.getBoundingClientRect().width : 0,
                    logsHeight: logs ? logs.getBoundingClientRect().height : 0,
                    rightWidth: right ? right.getBoundingClientRect().width : 0,
                    inspWidth: insp ? insp.getBoundingClientRect().width : 0,
                    qwenWidth: qwen ? qwen.getBoundingClientRect().width : 0,
                    railExplorerDisplay: railExplorer ? window.getComputedStyle(railExplorer).display : null,
                    railInspDisplay: railInsp ? window.getComputedStyle(railInsp).display : null,
                    railQwenDisplay: railQwen ? window.getComputedStyle(railQwen).display : null,
                    stripLogsDisplay: stripLogs ? window.getComputedStyle(stripLogs).display : null,
                    allCollapsed: left.classList.contains("dock-collapsed") &&
                                  logs.classList.contains("dock-collapsed") &&
                                  insp.classList.contains("dock-collapsed") &&
                                  qwen.classList.contains("dock-collapsed")
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] All Four Collapsed: {json.dumps(all_four_check, indent=2)}", flush=True)
        results["all_four_collapsed"] = all_four_check

        assert all_four_check["allCollapsed"] is True, "All four docks should have dock-collapsed class"
        assert all_four_check["leftWidth"] == 40, f"Left dock width should be 40, got {all_four_check['leftWidth']}"
        assert all_four_check["logsHeight"] == 32, f"Log strip height should be 32, got {all_four_check['logsHeight']}"
        assert all_four_check["inspWidth"] == 40, f"Inspector width should be 40, got {all_four_check['inspWidth']}"
        assert all_four_check["qwenWidth"] == 40, f"Qwen width should be 40, got {all_four_check['qwenWidth']}"
        assert all_four_check["railExplorerDisplay"] == "flex", "Explorer rail should be flex"
        assert all_four_check["railInspDisplay"] == "flex", "Inspector rail should be flex"
        assert all_four_check["railQwenDisplay"] == "flex", "Qwen rail should be flex"
        assert all_four_check["stripLogsDisplay"] == "flex", "Logs strip should be flex"

        # Capture screenshot showing all four docks in collapsed state
        screenshot_all_four = SCREENSHOTS_DIR / "all_four_docks_collapsed.png"
        await cdp.screenshot(str(screenshot_all_four))
        print(f"[CDP] Successfully captured screenshot: {screenshot_all_four}", flush=True)

        # ----------------------------------------------------
        # TEST 4: Re-expand all four docks and verify full restoration
        # ----------------------------------------------------
        print("\n--- Test 4: Re-expanding all four docks ---", flush=True)
        await cdp.eval_js('document.getElementById("rail-explorer").click()', await_promise=False)
        await cdp.eval_js('document.getElementById("strip-logs").click()', await_promise=False)
        await cdp.eval_js('document.getElementById("rail-inspector").click()', await_promise=False)
        await cdp.eval_js('document.getElementById("rail-qwen").click()', await_promise=False)
        await asyncio.sleep(1.0)

        all_restored_check = await cdp.eval_js('''
            (() => {
                const left = document.getElementById("left-dock");
                const logs = document.getElementById("log-strip");
                const insp = document.getElementById("inspector-panel");
                const qwen = document.getElementById("qwen-panel");
                const right = document.getElementById("right-dock");
                const name = document.getElementById("inspector-name") ? document.getElementById("inspector-name").textContent.trim() : null;
                const draft = document.getElementById("chat-input") ? document.getElementById("chat-input").value : null;

                return {
                    leftWidth: left ? left.getBoundingClientRect().width : 0,
                    logsHeight: logs ? logs.getBoundingClientRect().height : 0,
                    rightWidth: right ? right.getBoundingClientRect().width : 0,
                    selectedName: name,
                    draftInput: draft,
                    anyCollapsed: left.classList.contains("dock-collapsed") ||
                                  logs.classList.contains("dock-collapsed") ||
                                  insp.classList.contains("dock-collapsed") ||
                                  qwen.classList.contains("dock-collapsed")
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] All Restored: {json.dumps(all_restored_check, indent=2)}", flush=True)
        results["all_restored"] = all_restored_check
        assert all_restored_check["anyCollapsed"] is False, "No docks should be collapsed"
        assert all_restored_check["selectedName"] == "Animal", "Inspector selection must be preserved"
        assert all_restored_check["draftInput"] == "Why does Animal have subclasses?", "Qwen draft must be preserved"

        with open(BASE_DIR / "scratch" / "followup2_results.json", "w") as f:
            json.dump(results, f, indent=2)

        print("\n[CDP] Follow-Up 2 Verification PASSED 100%!", flush=True)

    finally:
        await cdp.close()
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(run_automation())

