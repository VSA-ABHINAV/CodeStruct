import asyncio
import json
import subprocess
import threading
import time
from pathlib import Path
import httpx
import websockets
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.main import app
import uvicorn

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

async def test():
    port = 9224
    proc = subprocess.Popen([
        CHROME_EXE,
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={BASE_DIR / 'scratch' / 'temp_chrome'}",
        "--window-size=1280,800",
        "--disable-gpu",
        "--disable-extensions",
        "about:blank"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        ws_url = None
        for _ in range(30):
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/json/list")
                if r.status_code == 200:
                    targets = [t for t in r.json() if t.get("type") == "page"]
                    if targets:
                        ws_url = targets[0]["webSocketDebuggerUrl"]
                        break
            except Exception:
                pass
            await asyncio.sleep(0.2)

        ws = await websockets.connect(ws_url)
        msg_id = 0
        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == msg_id:
                    return resp.get("result", {})

        async def eval_js(expr):
            r = await send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
            return r.get("result", {}).get("value")

        await send("Page.navigate", {"url": "http://127.0.0.1:8000"})
        await asyncio.sleep(2.0)

        # Let's inspect initial state
        initial = await eval_js('''
            (() => {
                const insp = document.getElementById("inspector-panel");
                const qwen = document.getElementById("qwen-panel");
                const right = document.getElementById("right-dock");
                const btnInsp = document.getElementById("btn-toggle-inspector");
                const btnQwen = document.getElementById("btn-toggle-qwen");
                const railInsp = document.getElementById("rail-inspector");
                const railQwen = document.getElementById("rail-qwen");

                return {
                    rightRect: right.getBoundingClientRect(),
                    inspRect: insp.getBoundingClientRect(),
                    qwenRect: qwen.getBoundingClientRect(),
                    btnInspRect: btnInsp ? btnInsp.getBoundingClientRect() : null,
                    btnQwenRect: btnQwen ? btnQwen.getBoundingClientRect() : null,
                    railInspDisplay: railInsp ? window.getComputedStyle(railInsp).display : null,
                    railQwenDisplay: railQwen ? window.getComputedStyle(railQwen).display : null
                };
            })()
        ''')
        print("Initial state:", json.dumps(initial, indent=2))

        # Click btn-toggle-inspector
        await eval_js('document.getElementById("btn-toggle-inspector").click()')
        await asyncio.sleep(0.5)

        after_insp = await eval_js('''
            (() => {
                const insp = document.getElementById("inspector-panel");
                const qwen = document.getElementById("qwen-panel");
                const right = document.getElementById("right-dock");
                const btnInsp = document.getElementById("btn-toggle-inspector");
                const railInsp = document.getElementById("rail-inspector");

                return {
                    inspClasses: insp.className,
                    inspRect: insp.getBoundingClientRect(),
                    btnInspRect: btnInsp ? btnInsp.getBoundingClientRect() : null,
                    railInspDisplay: railInsp ? window.getComputedStyle(railInsp).display : null,
                    railInspVisible: railInsp ? railInsp.offsetWidth > 0 && railInsp.offsetHeight > 0 : false
                };
            })()
        ''')
        print("After click btn-toggle-inspector:", json.dumps(after_insp, indent=2))

        # Click btn-toggle-qwen
        await eval_js('document.getElementById("btn-toggle-qwen").click()')
        await asyncio.sleep(0.5)

        after_both = await eval_js('''
            (() => {
                const insp = document.getElementById("inspector-panel");
                const qwen = document.getElementById("qwen-panel");
                const right = document.getElementById("right-dock");
                const railInsp = document.getElementById("rail-inspector");
                const railQwen = document.getElementById("rail-qwen");
                const btnInsp = document.getElementById("btn-toggle-inspector");
                const btnQwen = document.getElementById("btn-toggle-qwen");

                return {
                    rightClasses: right.className,
                    rightRect: right.getBoundingClientRect(),
                    inspDisplay: window.getComputedStyle(insp).display,
                    qwenDisplay: window.getComputedStyle(qwen).display,
                    railInspDisplay: railInsp ? window.getComputedStyle(railInsp).display : null,
                    railQwenDisplay: railQwen ? window.getComputedStyle(railQwen).display : null,
                    btnInspVisible: btnInsp ? btnInsp.offsetWidth > 0 : false,
                    btnQwenVisible: btnQwen ? btnQwen.offsetWidth > 0 : false,
                    innerHtml: right.innerHTML
                };
            })()
        ''')
        print("After click both:", json.dumps(after_both, indent=2))

        await ws.close()
    finally:
        proc.terminate()

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(1.5)
    asyncio.run(test())
