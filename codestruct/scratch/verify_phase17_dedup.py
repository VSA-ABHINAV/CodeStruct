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
user_data = BASE_DIR / "scratch" / "chrome_user_data_dedup"

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
        # Also copy to root screenshots dir if distinct
        try:
            rel = Path(path).name
            root_copy = ROOT_SCREENSHOTS_DIR / rel
            with open(root_copy, "wb") as f_root:
                f_root.write(data)
        except Exception:
            pass
        print(f"[CDP] Saved screenshot: {path} ({len(data)} bytes)", flush=True)

    async def close(self):
        if self.ws:
            await self.ws.close()

results = {}

async def run_automation():
    port = 9223
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
        analysis_res = await cdp.eval_js('window.runAnalysis("sample_project")', await_promise=True)
        print(f"[CDP] Analysis result: {analysis_res.get('summary') if analysis_res else None}", flush=True)
        await asyncio.sleep(1.0)

        # Select a symbol (e.g. Animal) so that context and inspector are populated
        await cdp.eval_js('window.selectSymbol("Animal")', await_promise=False)
        await asyncio.sleep(0.8)

        # ----------------------------------------------------
        # TEST 1: Graph View
        # ----------------------------------------------------
        print("\n--- Verifying View 1: Graph View ---", flush=True)
        await cdp.eval_js('window.switchCenterTab("graph")', await_promise=False)
        await asyncio.sleep(0.5)

        graph_check = await cdp.eval_js('''
            (() => {
                const subToolbar = document.getElementById("center-sub-toolbar");
                const graphControls = document.getElementById("graph-header-controls");
                const oldCenterTabs = document.querySelector(".center-tabs");
                const oldCodeHeader = document.getElementById("code-header-controls");
                const rect = subToolbar ? subToolbar.getBoundingClientRect() : null;
                const kindFilters = document.getElementById("kind-filters");
                const filterCheckboxes = kindFilters ? kindFilters.querySelectorAll("input[type=checkbox]").length : 0;
                const zoomBtns = document.querySelectorAll(".graph-controls button").length;
                
                // Count how many view tab switchers exist on the entire page
                const topTabs = document.querySelectorAll(".toolbar-tab-group button").length;
                const totalTabSwitchers = document.querySelectorAll("#tab-graph, #tab-table, #tab-patterns, #tab-code").length;

                return {
                    subToolbarDisplay: subToolbar ? window.getComputedStyle(subToolbar).display : null,
                    subToolbarHeight: rect ? rect.height : null,
                    graphControlsDisplay: graphControls ? window.getComputedStyle(graphControls).display : null,
                    oldCenterTabsPresent: !!oldCenterTabs,
                    oldCodeHeaderPresent: !!oldCodeHeader,
                    filterCheckboxesCount: filterCheckboxes,
                    zoomControlsCount: zoomBtns,
                    topTabsCount: topTabs,
                    duplicateOldTabsCount: totalTabSwitchers
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Graph View Check: {json.dumps(graph_check, indent=2)}", flush=True)
        results["graph_view"] = graph_check

        # Capture Graph View screenshot
        graph_screenshot = SCREENSHOTS_DIR / "view_graph.png"
        await cdp.screenshot(str(graph_screenshot))

        # Test filter and zoom controls functionality
        filter_toggle_test = await cdp.eval_js('''
            (() => {
                const cb = document.getElementById("filter-class");
                if (!cb) return { error: "filter-class checkbox not found" };
                const initialChecked = cb.checked;
                // Uncheck class
                cb.click();
                const afterClickChecked = cb.checked;
                // Re-check class
                cb.click();
                const restoredChecked = cb.checked;
                
                // Click zoom in and fit
                const zoomIn = document.getElementById("btn-zoom-in");
                const btnFit = document.getElementById("btn-fit");
                const initialZoom = window.cy ? window.cy.zoom() : 1;
                if (zoomIn) zoomIn.click();
                const zoomed = window.cy ? window.cy.zoom() : 1;
                if (btnFit) btnFit.click();
                const fittedZoom = window.cy ? window.cy.zoom() : 1;

                return {
                    initialChecked,
                    afterClickChecked,
                    restoredChecked,
                    initialZoom,
                    zoomed,
                    fittedZoom
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Filter & Zoom test: {filter_toggle_test}", flush=True)
        results["filter_zoom_test"] = filter_toggle_test

        # ----------------------------------------------------
        # TEST 2: Table View
        # ----------------------------------------------------
        print("\n--- Verifying View 2: Table View ---", flush=True)
        await cdp.eval_js('window.switchCenterTab("table")', await_promise=False)
        await asyncio.sleep(0.8)

        table_check = await cdp.eval_js('''
            (() => {
                const subToolbar = document.getElementById("center-sub-toolbar");
                const tableViewport = document.getElementById("table-viewport");
                const rect = subToolbar ? subToolbar.getBoundingClientRect() : null;
                const rows = document.querySelectorAll("#symbols-table-body tr").length;
                const oldCenterTabs = document.querySelector(".center-tabs");
                const oldCodeHeader = document.getElementById("code-header-controls");

                return {
                    subToolbarDisplay: subToolbar ? window.getComputedStyle(subToolbar).display : null,
                    subToolbarHeight: rect ? rect.height : null,
                    tableViewportDisplay: tableViewport ? window.getComputedStyle(tableViewport).display : null,
                    symbolRowsCount: rows,
                    oldCenterTabsPresent: !!oldCenterTabs,
                    oldCodeHeaderPresent: !!oldCodeHeader
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Table View Check: {json.dumps(table_check, indent=2)}", flush=True)
        results["table_view"] = table_check

        # Capture Table View screenshot
        table_screenshot = SCREENSHOTS_DIR / "view_table.png"
        await cdp.screenshot(str(table_screenshot))

        # ----------------------------------------------------
        # TEST 3: Patterns View
        # ----------------------------------------------------
        print("\n--- Verifying View 3: Patterns View ---", flush=True)
        await cdp.eval_js('window.switchCenterTab("patterns")', await_promise=False)
        await asyncio.sleep(0.8)

        patterns_check = await cdp.eval_js('''
            (() => {
                const subToolbar = document.getElementById("center-sub-toolbar");
                const patternsViewport = document.getElementById("patterns-viewport");
                const rect = subToolbar ? subToolbar.getBoundingClientRect() : null;
                const oldCenterTabs = document.querySelector(".center-tabs");
                const oldCodeHeader = document.getElementById("code-header-controls");

                return {
                    subToolbarDisplay: subToolbar ? window.getComputedStyle(subToolbar).display : null,
                    subToolbarHeight: rect ? rect.height : null,
                    patternsViewportDisplay: patternsViewport ? window.getComputedStyle(patternsViewport).display : null,
                    oldCenterTabsPresent: !!oldCenterTabs,
                    oldCodeHeaderPresent: !!oldCodeHeader
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Patterns View Check: {json.dumps(patterns_check, indent=2)}", flush=True)
        results["patterns_view"] = patterns_check

        # Capture Patterns View screenshot
        patterns_screenshot = SCREENSHOTS_DIR / "view_patterns.png"
        await cdp.screenshot(str(patterns_screenshot))

        # ----------------------------------------------------
        # TEST 4: Code Viewer
        # ----------------------------------------------------
        print("\n--- Verifying View 4: Code Viewer ---", flush=True)
        # Select 'Animal' and jump to source
        await cdp.eval_js('window.jumpToSource("Animal")', await_promise=True)
        await asyncio.sleep(1.0)

        code_check = await cdp.eval_js('''
            (() => {
                const subToolbar = document.getElementById("center-sub-toolbar");
                const codeViewport = document.getElementById("code-viewport");
                const rect = subToolbar ? subToolbar.getBoundingClientRect() : null;
                const oldCenterTabs = document.querySelector(".center-tabs");
                const oldCodeHeader = document.getElementById("code-header-controls");
                const topFileCtx = document.getElementById("toolbar-file-context");
                const topLineCtx = document.getElementById("toolbar-line-context");
                const topOpenBtn = document.getElementById("toolbar-btn-open-editor");
                const topReadOnly = document.querySelector(".toolbar-readonly-pill");

                return {
                    subToolbarDisplay: subToolbar ? window.getComputedStyle(subToolbar).display : null,
                    subToolbarHeight: rect ? rect.height : null,
                    codeViewportDisplay: codeViewport ? window.getComputedStyle(codeViewport).display : null,
                    oldCenterTabsPresent: !!oldCenterTabs,
                    oldCodeHeaderPresent: !!oldCodeHeader,
                    topFileContextText: topFileCtx ? topFileCtx.textContent.trim() : null,
                    topLineContextText: topLineCtx ? topLineCtx.textContent.trim() : null,
                    topOpenEditorVisible: topOpenBtn ? window.getComputedStyle(topOpenBtn).display !== "none" : false,
                    topReadOnlyVisible: topReadOnly ? window.getComputedStyle(topReadOnly).display !== "none" : false
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Code View Check: {json.dumps(code_check, indent=2)}", flush=True)
        results["code_view"] = code_check

        # Capture Code View screenshot
        code_screenshot = SCREENSHOTS_DIR / "view_code.png"
        await cdp.screenshot(str(code_screenshot))

        # ----------------------------------------------------
        # TEST 5: Reflow & Dock Collapse Check
        # ----------------------------------------------------
        print("\n--- Verifying Dock Collapse & Reflow ---", flush=True)
        await cdp.eval_js('window.switchCenterTab("graph")', await_promise=False)
        await asyncio.sleep(0.5)

        reflow_check = await cdp.eval_js('''
            (() => {
                const leftDock = document.getElementById("left-dock");
                const btnToggle = document.getElementById("btn-toggle-explorer");
                const initialWidth = leftDock.getBoundingClientRect().width;
                
                // Collapse dock
                if (btnToggle) btnToggle.click();
                const collapsedWidth = leftDock.getBoundingClientRect().width;
                const isCollapsed = leftDock.classList.contains("collapsed");
                
                // Expand dock back
                if (btnToggle) btnToggle.click();
                const restoredWidth = leftDock.getBoundingClientRect().width;
                const isRestored = !leftDock.classList.contains("collapsed");

                return {
                    initialWidth,
                    collapsedWidth,
                    isCollapsed,
                    restoredWidth,
                    isRestored
                };
            })()
        ''', await_promise=False)
        print(f"[CDP] Dock Reflow Check: {json.dumps(reflow_check, indent=2)}", flush=True)
        results["dock_reflow"] = reflow_check

        # Save test results JSON
        with open(BASE_DIR / "scratch" / "phase17_dedup_results.json", "w") as f:
            json.dump(results, f, indent=2)

        print("\n[CDP] Phase 17 Follow-Up verification completed successfully!", flush=True)

    finally:
        await cdp.close()
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(2.0)
    asyncio.run(run_automation())
