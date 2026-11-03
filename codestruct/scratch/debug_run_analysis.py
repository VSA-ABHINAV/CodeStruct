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
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.main import app
import uvicorn

SCREENSHOTS_DIR = BASE_DIR / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
user_data = BASE_DIR / "scratch" / "chrome_user_data"

test_results = {}

class SimpleCDP:
    def __init__(self, ws):
        self.ws = ws
        self.id_counter = 0

    async def call(self, method, params=None):
        self.id_counter += 1
        cid = self.id_counter
        req = {"id": cid, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(req))
        while True:
            raw = await self.ws.recv()
            resp = json.loads(raw)
            if "method" in resp:
                if "exception" in resp["method"].lower() or "log" in resp["method"].lower() or "error" in resp["method"].lower():
                    print(f"[CDP EVENT] {resp['method']}: {resp['params']}", flush=True)
            if resp.get("id") == cid:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})

    async def eval(self, expr, await_promise=False):
        res = await self.call("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise
        })
        print(f"[CDP EVAL] {expr[:40]} -> {res}", flush=True)
        return res.get("result", {}).get("value")

    async def screenshot(self, path, clip=None):
        params = {"format": "png"}
        if clip:
            params["clip"] = clip
        res = await self.call("Page.captureScreenshot", params)
        data = base64.b64decode(res["data"])
        with open(path, "wb") as f:
            f.write(data)
        print(f"[CDP] Saved screenshot: {path} ({len(data)} bytes)", flush=True)

async def run_automation():
    # Wait for Chrome debug port
    ws_url = None
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9222/json/list", timeout=1.0)
            if r.status_code == 200:
                for target in r.json():
                    if target.get("type") == "page" and "webSocketDebuggerUrl" in target:
                        ws_url = target["webSocketDebuggerUrl"]
                        break
                if ws_url:
                    break
        except Exception:
            pass
        await asyncio.sleep(0.2)

    if not ws_url:
        raise RuntimeError("Could not connect to Chrome debug port")

    ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)
    cdp = SimpleCDP(ws)

    try:
        await cdp.call("Page.enable")
        await cdp.call("Runtime.enable")
        await cdp.call("Log.enable")
        await cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1280,
            "height": 800,
            "deviceScaleFactor": 1,
            "mobile": False
        })
        print("[CDP] Navigating to http://127.0.0.1:8000...", flush=True)
        await cdp.call("Page.navigate", {"url": "http://127.0.0.1:8000"})
        await asyncio.sleep(2.0)

        curr_url = await cdp.eval('window.location.href')
        doc_title = await cdp.eval('document.title')
        print(f"[CDP] Current URL: {curr_url}, Title: {doc_title}", flush=True)
        await cdp.eval('window.runAnalysis("sample_project")', await_promise=True)
        await asyncio.sleep(2.0)
        nodes_len = await cdp.eval('window.lastGraphData ? window.lastGraphData.nodes.length : 0')
        print(f"[CDP] Analysis complete: {nodes_len} nodes loaded", flush=True)
        assert nodes_len == 16, f"Expected 16 nodes, got {nodes_len}"

        # 2. Check font loading
        font_inter = await cdp.eval('document.fonts.check("14px Inter")')
        font_mono = await cdp.eval('document.fonts.check("14px \'JetBrains Mono\'")')
        print(f"[CDP] Fonts loaded: Inter={font_inter}, JetBrains Mono={font_mono}", flush=True)
        test_results["fonts"] = {"Inter": font_inter, "JetBrainsMono": font_mono}
        assert font_inter is True, "Inter font failed to load"
        assert font_mono is True, "JetBrains Mono font failed to load"

        # 3. Select Animal
        print("[CDP] Selecting 'Animal'...", flush=True)
        await cdp.eval('window.selectSymbol("Animal")')

        # Wait up to 5s for impact groups to populate
        impact_parsed = []
        for _ in range(25):
            await asyncio.sleep(0.2)
            parsed = await cdp.eval('''
                (() => {
                    const groups = Array.from(document.querySelectorAll('.impact-depth-group')).map(g => {
                        const depth = g.querySelector('.depth-badge') ? g.querySelector('.depth-badge').textContent.trim() : '';
                        const items = Array.from(g.querySelectorAll('.impact-item')).map(li => ({
                            id: li.dataset.id,
                            name: li.querySelector('.impact-name') ? li.querySelector('.impact-name').textContent.trim() : '',
                            edge: li.querySelector('.impact-edge-badge') ? li.querySelector('.impact-edge-badge').textContent.trim() : ''
                        }));
                        return { depth, items };
                    });
                    return groups;
                })()
            ''')
            if parsed and len(parsed) > 0:
                impact_parsed = parsed
                break

        print(f"[CDP] Parsed impact groups: {json.dumps(impact_parsed, indent=2)}", flush=True)
        test_results["impact_groups"] = impact_parsed

        impact_names = [item["name"] for g in impact_parsed for item in g["items"]]
        print(f"[CDP] Impact names: {impact_names}", flush=True)
        expected_names = {"Dog", "Cat", "build_zoo", "main"}
        assert expected_names.issubset(set(impact_names)), f"Expected {expected_names} but got {impact_names}"

        # 5. Capture 1280x800 Screenshot
        img_1280_path = SCREENSHOTS_DIR / "desktop_1280x800.png"
        await cdp.screenshot(str(img_1280_path))

        # 6. Capture Impact section crop screenshot
        rect = await cdp.eval('''
            (() => {
                const el = document.getElementById("inspector-impact-container");
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return { x: r.x, y: r.y, width: r.width, height: r.height, scale: 1 };
            })()
        ''')
        if rect:
            impact_img_path = SCREENSHOTS_DIR / "impact_section.png"
            await cdp.screenshot(str(impact_img_path), clip=rect)

        # 7. Click 'build_zoo' in Impact list and verify selection sync
        print("[CDP] Clicking 'build_zoo' in Impact list...", flush=True)
        await cdp.eval('''
            (() => {
                const item = document.querySelector('.impact-item[data-id$="build_zoo"]');
                if (item) item.click();
            })()
        ''')
        await asyncio.sleep(1.0)
        current_selected = await cdp.eval('window.selectedSymbolId')
        inspector_name = await cdp.eval('document.getElementById("inspector-name").textContent')
        tree_selected = await cdp.eval('''
            (() => {
                const sel = document.querySelector('.tree-item.selected');
                return sel ? sel.dataset.id : null;
            })()
        ''')
        print(f"[CDP] After click build_zoo: selectedSymbolId={current_selected}, inspectorName={inspector_name}, treeSelected={tree_selected}", flush=True)
        test_results["selection_sync"] = {
            "selectedSymbolId": current_selected,
            "inspectorName": inspector_name,
            "treeSelected": tree_selected
        }
        assert "build_zoo" in str(current_selected), f"Expected selectedSymbolId build_zoo, got {current_selected}"
        assert inspector_name == "build_zoo", f"Expected inspectorName build_zoo, got {inspector_name}"
        assert "build_zoo" in str(tree_selected), f"Expected treeSelected build_zoo, got {tree_selected}"

        # 8. Test Dock Toggles & State Preservation
        print("[CDP] Testing Dock Toggles & State Preservation...", flush=True)
        await cdp.eval('''
            document.getElementById("explorer-filter").value = "Dog";
            window.filterExplorerTree("Dog");
            document.getElementById("chat-input").value = "Why does Dog inherit Animal?";
        ''')
        await asyncio.sleep(0.5)

        # Collapse left dock
        await cdp.eval('document.getElementById("btn-toggle-explorer").click()')
        await asyncio.sleep(0.5)
        left_collapsed = await cdp.eval('document.getElementById("left-dock").classList.contains("dock-collapsed")')

        # Expand left dock via rail
        await cdp.eval('document.getElementById("rail-explorer").click()')
        await asyncio.sleep(0.5)
        left_expanded = not (await cdp.eval('document.getElementById("left-dock").classList.contains("dock-collapsed")'))
        filter_val = await cdp.eval('document.getElementById("explorer-filter").value')
        chat_val = await cdp.eval('document.getElementById("chat-input").value')
        print(f"[CDP] Dock toggles: collapsed={left_collapsed}, expanded={left_expanded}, filter='{filter_val}', chat='{chat_val}'", flush=True)
        test_results["dock_toggles"] = {
            "collapse_ok": left_collapsed,
            "expand_ok": left_expanded,
            "filter_preserved": filter_val == "Dog",
            "chat_preserved": chat_val == "Why does Dog inherit Animal?"
        }
        assert left_collapsed is True
        assert left_expanded is True
        assert filter_val == "Dog"
        assert chat_val == "Why does Dog inherit Animal?"

        # Clear filter
        await cdp.eval('document.getElementById("explorer-filter").value = ""; window.filterExplorerTree("");')

        # 9. Test Toolbar Horizontal Scroll & Edge Fades
        print("[CDP] Testing Toolbar Horizontal Scroll & Edge Fades...", flush=True)
        tb_scroll_res = await cdp.eval('''
            (() => {
                const c = document.getElementById("toolbar-scroll-container");
                if (!c) return { error: "no container" };
                c.scrollLeft = 50;
                c.dispatchEvent(new Event("scroll"));
                const fadeLeft = document.getElementById("toolbar-fade-left");
                const fadeRight = document.getElementById("toolbar-fade-right");
                return {
                    scrollLeft: c.scrollLeft,
                    scrollWidth: c.scrollWidth,
                    clientWidth: c.clientWidth,
                    fadeLeftVisible: fadeLeft ? fadeLeft.classList.contains("visible") : false,
                    fadeRightVisible: fadeRight ? fadeRight.classList.contains("visible") : false
                };
            })()
        ''')
        print(f"[CDP] Toolbar scroll test: {tb_scroll_res}", flush=True)
        test_results["toolbar_scroll"] = tb_scroll_res

        # 10. Responsive Floor & 1024x768 Screenshot with Collapsed Dock Combination
        print("[CDP] Resizing to 1024x768 and testing responsive floor...", flush=True)
        await cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1024,
            "height": 768,
            "deviceScaleFactor": 1,
            "mobile": False
        })
        await asyncio.sleep(0.5)

        # Collapse Left Dock & Logs Dock to demonstrate responsive collapsed dock combination
        await cdp.eval('''
            document.getElementById("btn-toggle-explorer").click();
            document.getElementById("btn-toggle-logs").click();
        ''')
        await asyncio.sleep(1.0)

        img_1024_path = SCREENSHOTS_DIR / "desktop_1024x768_collapsed.png"
        await cdp.screenshot(str(img_1024_path))
        print(f"[CDP] Saved desktop_1024x768_collapsed.png", flush=True)
        test_results["responsive_1024"] = {"screenshot": str(img_1024_path), "width": 1024, "height": 768}

        print("[CDP] ALL CHECKS COMPLETED AND VERIFIED!", flush=True)
        test_results["status"] = "PASSED"

    finally:
        await ws.close()
        with open(BASE_DIR / "scratch" / "cdp_test_results.json", "w", encoding="utf-8") as f:
            json.dump(test_results, f, indent=2)

def main():
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    time.sleep(1.2)

    proc = subprocess.Popen([
        CHROME_EXE,
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={user_data}",
        "--disable-extensions",
        "--hide-scrollbars",
        "--disable-gpu",
        "about:blank"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        asyncio.run(run_automation())
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)
        server.should_exit = True
        th.join(timeout=2.0)

if __name__ == "__main__":
    main()
