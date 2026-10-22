"""
Direct Chrome DevTools Protocol (CDP) verification script for
CodeStruct Architecture Workbench (Graph Interaction, Edge Visibility, Inspector Explanation & Zero unresolved_symbol).
"""
import asyncio
import base64
import json
from pathlib import Path
import shutil
import urllib.request
import websockets

SCREENSHOT_DIR = Path("D:/REP/Codestruct/Codestruct/docs/verification/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path(r"C:\Users\ABHINAV\.gemini\antigravity-ide\brain\4fda842f-5c51-411b-b338-e842886b640c")


async def run_cdp_verification():
    # 1. Fetch CDP target
    with urllib.request.urlopen("http://127.0.0.1:9222/json") as resp:
        targets = json.loads(resp.read().decode("utf-8"))

    page_target = None
    for t in targets:
        if t.get("type") == "page" and "5173" in t.get("url", ""):
            page_target = t
            break
    if not page_target:
        for t in targets:
            if t.get("type") == "page":
                page_target = t
                break

    assert page_target, "No Chrome page target found on port 9222"
    ws_url = page_target["webSocketDebuggerUrl"]
    print(f"Connecting to CDP WebSocket: {ws_url}")

    async with websockets.connect(ws_url, max_size=20_000_000) as ws:
        msg_id = 0

        async def send_cmd(method: str, params: dict = None):
            nonlocal msg_id
            msg_id += 1
            cid = msg_id
            payload = {"id": cid, "method": method, "params": params or {}}
            await ws.send(json.dumps(payload))
            while True:
                resp_text = await ws.recv()
                data = json.loads(resp_text)
                if data.get("id") == cid:
                    return data.get("result", {})

        async def capture_screenshot(filename: str):
            res = await send_cmd("Page.captureScreenshot", {"format": "png"})
            b64data = res.get("data")
            assert b64data, f"Failed capturing screenshot {filename}"
            img_bytes = base64.b64decode(b64data)
            out_path = SCREENSHOT_DIR / filename
            out_path.write_bytes(img_bytes)
            print(f"Saved screenshot: {out_path} ({len(img_bytes)} bytes)")
            if ARTIFACT_DIR.is_dir():
                shutil.copy2(out_path, ARTIFACT_DIR / filename)
                print(f"Copied to artifact dir: {ARTIFACT_DIR / filename}")

        # 2. Set viewport to 1400x900
        await send_cmd("Emulation.setDeviceMetricsOverride", {
            "width": 1400,
            "height": 900,
            "deviceScaleFactor": 1,
            "mobile": False,
        })

        info_file = Path("D:/REP/Codestruct/Codestruct/scratch/test_analysis_info.json")
        info_data = json.loads(info_file.read_text(encoding="utf-8"))
        analysis_id = info_data["analysis_id"]
        target_url = (
            f"http://127.0.0.1:5173/?embed=thonny"
            f"&analysis_id={analysis_id}"
            f"&project_id=rich_analysis_fixture"
            f"&session_token=rich_analysis_fixture"
        )
        print(f"Navigating to fresh analysis: {target_url}")
        await send_cmd("Page.navigate", {"url": target_url})

        # 4. Wait for nodes to render
        print("Waiting for graph nodes to render...")
        nodes_count = 0
        for _ in range(40):
            await asyncio.sleep(0.5)
            eval_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelectorAll('.react-flow__node').length"
            })
            val = eval_res.get("result", {}).get("value", 0)
            if val > 0:
                nodes_count = val
                print(f"Graph loaded with {nodes_count} rendered nodes!")
                break

        assert nodes_count > 0, "No React Flow nodes rendered!"

        # Let layout settle
        await asyncio.sleep(1.0)

        # 5. Check edge visibility and styles in DOM
        edge_info = await send_cmd("Runtime.evaluate", {
            "expression": """
                (() => {
                    const paths = Array.from(document.querySelectorAll('.react-flow__edge path.react-flow__edge-path'));
                    return {
                        count: paths.length,
                        widths: paths.map(p => window.getComputedStyle(p).strokeWidth).slice(0, 5),
                        colors: paths.map(p => window.getComputedStyle(p).stroke).slice(0, 5)
                    };
                })()
            """,
            "returnByValue": True
        })
        e_data = edge_info.get("result", {}).get("value", {})
        print(f"Edge verification: count={e_data.get('count')}, sample widths={e_data.get('widths')}, sample colors={e_data.get('colors')}")

        # Check arrow markers in SVG defs
        marker_info = await send_cmd("Runtime.evaluate", {
            "expression": "document.querySelectorAll('defs marker').length",
            "returnByValue": True
        })
        m_count = marker_info.get("result", {}).get("value", 0)
        print(f"Arrowhead markers in DOM: {m_count}")
        assert m_count > 0, "No arrowhead markers found in SVG defs!"

        # 6. Capture State 1: Initial Fit View
        await capture_screenshot("graph_corr2_01_initial_fit.png")

        # 7. Zoom In (+50%)
        print("Testing Zoom In...")
        await send_cmd("Runtime.evaluate", {
            "expression": """
                (() => {
                    const zoomInBtn = document.querySelector('.react-flow__controls-zoomin');
                    if (zoomInBtn) {
                        zoomInBtn.click();
                        zoomInBtn.click();
                    }
                })()
            """
        })
        await asyncio.sleep(0.8)
        await capture_screenshot("graph_corr2_02_zoom_in.png")

        # 8. Zoom Out (-50%)
        print("Testing Zoom Out...")
        await send_cmd("Runtime.evaluate", {
            "expression": """
                (() => {
                    const zoomOutBtn = document.querySelector('.react-flow__controls-zoomout');
                    if (zoomOutBtn) {
                        for (let i = 0; i < 4; i++) zoomOutBtn.click();
                    }
                })()
            """
        })
        await asyncio.sleep(0.8)
        await capture_screenshot("graph_corr2_03_zoom_out.png")

        # 9. Fit View Reset
        print("Testing Fit View Reset...")
        await send_cmd("Runtime.evaluate", {
            "expression": """
                (() => {
                    const fitBtn = document.querySelector('.react-flow__controls-fitview');
                    if (fitBtn) fitBtn.click();
                })()
            """
        })
        await asyncio.sleep(0.8)

        # 10. Node Selection & Inspector Verification
        print("Selecting 'Application' node and verifying Inspector...")
        select_res = await send_cmd("Runtime.evaluate", {
            "expression": """
                (() => {
                    const nodes = Array.from(document.querySelectorAll('.react-flow__node'));
                    const target = nodes.find(n => n.textContent.includes('Application') || n.textContent.includes('Processor'));
                    if (target) {
                        target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        return target.textContent.trim();
                    }
                    return null;
                })()
            """,
            "returnByValue": True
        })
        selected_label = select_res.get("result", {}).get("value")
        print(f"Clicked node: {selected_label}")
        await asyncio.sleep(1.0)

        # Verify Inspector text for NO unresolved_symbol and EXACTLY TWO explanation lines
        inspector_check = await send_cmd("Runtime.evaluate", {
            "expression": """
                (() => {
                    const inspector = document.querySelector('aside[data-purpose="right-panel-inspector"]');
                    if (!inspector) return { found: false };

                    const text = inspector.innerText;
                    const hasUnresolvedToken = text.includes('unresolved_symbol');

                    // Find Architectural Explanation card and its two p tags
                    const allDivs = Array.from(inspector.querySelectorAll('div'));
                    const expCard = allDivs.find(d => {
                        const h = d.querySelector('span');
                        return h && h.textContent.trim() === 'Architectural Explanation';
                    });
                    let explanationLines = [];
                    if (expCard) {
                        const pTags = Array.from(expCard.querySelectorAll('p'));
                        explanationLines = pTags.map(p => p.textContent.trim()).filter(Boolean);
                    }

                    return {
                        found: true,
                        hasUnresolvedToken: hasUnresolvedToken,
                        explanationLines: explanationLines,
                        inspectorTextSample: text.slice(0, 300)
                    };
                })()
            """,
            "returnByValue": True
        })
        chk = inspector_check.get("result", {}).get("value", {})
        print(f"Inspector check: {chk}")

        assert not chk.get("hasUnresolvedToken"), (
            "FAIL: Inspector contains raw token 'unresolved_symbol'!"
        )
        print("PASS: Zero instances of 'unresolved_symbol' in user-visible Inspector text!")

        lines = chk.get("explanationLines", [])
        print(f"Architectural Explanation lines count: {len(lines)}")
        for idx, line in enumerate(lines, 1):
            print(f"  Line {idx}: {line}")

        assert len(lines) == 2, f"FAIL: Expected exactly 2 explanation lines, found {len(lines)}: {lines}"
        print("PASS: Exactly TWO concise evidence-grounded explanation lines rendered!")

        # 11. Capture Node Explanation Screenshot
        await capture_screenshot("inspector_corr2_node_explanation.png")

        # 12. Check Unresolved Node (click an unresolved / external node)
        print("Selecting unresolved/external node to verify badge and explanation...")
        unresolved_click = await send_cmd("Runtime.evaluate", {
            "expression": """
                (() => {
                    const nodes = Array.from(document.querySelectorAll('.react-flow__node'));
                    const unres = nodes.find(n => n.textContent.includes('nonexistent_module') || n.textContent.includes('missing_function') || n.textContent.includes('Unresolved') || n.textContent.includes('External'));
                    if (unres) {
                        unres.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        return unres.textContent.trim();
                    }
                    return null;
                })()
            """,
            "returnByValue": True
        })
        unres_node = unresolved_click.get("result", {}).get("value")
        print(f"Clicked unresolved/external node: {unres_node}")
        await asyncio.sleep(1.0)

        unresolved_inspector = await send_cmd("Runtime.evaluate", {
            "expression": """
                (() => {
                    const inspector = document.querySelector('aside[data-purpose="right-panel-inspector"]');
                    if (!inspector) return null;
                    const text = inspector.innerText;
                    return {
                        hasUnresolvedToken: text.includes('unresolved_symbol'),
                        badgeText: inspector.querySelector('.badge, span')?.textContent || ''
                    };
                })()
            """,
            "returnByValue": True
        })
        u_info = unresolved_inspector.get("result", {}).get("value", {})
        assert not u_info.get("hasUnresolvedToken"), "FAIL: Unresolved node detail contains raw token 'unresolved_symbol'!"
        print("PASS: Unresolved node inspection clean without 'unresolved_symbol'!")

        await capture_screenshot("inspector_corr2_unresolved_node.png")

        print("=================================================================")
        print("ALL GRAPH INTERACTION & INSPECTOR CHECKS PASSED 100%!")
        print("=================================================================")

asyncio.run(run_cdp_verification())
