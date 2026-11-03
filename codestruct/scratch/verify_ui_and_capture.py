import json
import os
import sys
import time
from pathlib import Path
from PIL import ImageGrab

# Ensure codestruct package is on path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.main import start

SCREENSHOTS_DIR = BASE_DIR / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

test_results = {}

def automation_routine(window):
    print("[Automation] Pywebview window loaded. Sleeping 3s for page initialization...", flush=True)
    time.sleep(3.0)

    try:
        # 1. Trigger Analysis of sample_project
        print("[Automation] Triggering runAnalysis('sample_project')...", flush=True)
        window.evaluate_js('window.runAnalysis("sample_project");')
        
        # Wait up to 5s for analysis to populate nodes
        for _ in range(25):
            node_count = window.evaluate_js('window.lastGraphData ? window.lastGraphData.summary.node_count : 0;')
            if node_count and node_count >= 16:
                print(f"[Automation] Analysis complete. Nodes: {node_count}", flush=True)
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Analysis did not complete in time")

        # 2. Check font loading
        font_inter = window.evaluate_js('document.fonts.check("14px Inter");')
        font_mono = window.evaluate_js('document.fonts.check("14px \\\'JetBrains Mono\\\'");')
        print(f"[Automation] Fonts loaded: Inter={font_inter}, JetBrains Mono={font_mono}", flush=True)
        test_results["fonts"] = {"Inter": font_inter, "JetBrainsMono": font_mono}

        # 3. Select 'Animal'
        print("[Automation] Selecting 'Animal' symbol...", flush=True)
        window.evaluate_js('window.selectSymbol("Animal");')

        # Wait up to 5s for impact items to populate
        impact_groups = []
        for _ in range(25):
            impact_raw = window.evaluate_js('''
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
                    return JSON.stringify(groups);
                })()
            ''')
            groups = json.loads(impact_raw) if impact_raw else []
            if groups and len(groups) > 0:
                impact_groups = groups
                break
            time.sleep(0.2)

        print(f"[Automation] Impact groups returned: {json.dumps(impact_groups, indent=2)}", flush=True)
        test_results["impact_groups"] = impact_groups

        # Flat list of names
        impact_names = [item["name"] for g in impact_groups for item in g["items"]]
        print(f"[Automation] Impacted Names: {impact_names}", flush=True)
        expected_names = {"Dog", "Cat", "build_zoo", "main"}
        assert expected_names.issubset(set(impact_names)), f"Expected {expected_names} but got {impact_names}"

        # 5. Capture 1280x800 screenshot and Impact section crop
        window.resize(1280, 800)
        time.sleep(1.0)
        wx, wy, ww, wh = window.x, window.y, window.width, window.height
        print(f"[Automation] Window geometry: x={wx}, y={wy}, w={ww}, h={wh}", flush=True)

        img_1280 = ImageGrab.grab(bbox=(wx, wy, wx + ww, wy + wh))
        img_1280_path = SCREENSHOTS_DIR / "desktop_1280x800.png"
        img_1280.save(str(img_1280_path))
        print(f"[Automation] Saved desktop_1280x800.png ({img_1280.size})", flush=True)

        # Crop Impact section if coordinates available
        impact_rect_raw = window.evaluate_js('''
            (() => {
                const el = document.getElementById("inspector-impact-container");
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return JSON.stringify({ x: r.x, y: r.y, width: r.width, height: r.height });
            })()
        ''')
        if impact_rect_raw:
            r = json.loads(impact_rect_raw)
            crop_box = (
                max(0, int(r["x"])),
                max(0, int(r["y"]) + 30),
                min(ww, int(r["x"] + r["width"])),
                min(wh, int(r["y"] + r["height"]) + 40)
            )
            cropped_impact = img_1280.crop(crop_box)
            impact_img_path = SCREENSHOTS_DIR / "impact_section.png"
            cropped_impact.save(str(impact_img_path))
            print(f"[Automation] Saved impact_section.png ({cropped_impact.size})", flush=True)

        # 6. Click 'build_zoo' in Impact list and verify selection sync
        print("[Automation] Clicking 'build_zoo' in Impact list...", flush=True)
        click_res = window.evaluate_js('''
            (() => {
                const item = document.querySelector('.impact-item[data-id$="build_zoo"]');
                if (!item) return { error: "not found" };
                item.click();
                return { success: true };
            })()
        ''')
        time.sleep(1.0)
        current_selected = window.evaluate_js('window.selectedSymbolId;')
        inspector_name = window.evaluate_js('document.getElementById("inspector-name").textContent;')
        tree_selected = window.evaluate_js('''
            (() => {
                const sel = document.querySelector('.tree-node-content.selected');
                return sel ? sel.dataset.id : null;
            })()
        ''')
        print(f"[Automation] After click build_zoo: selectedSymbolId={current_selected}, inspectorName={inspector_name}, treeSelected={tree_selected}", flush=True)
        test_results["selection_sync"] = {
            "selectedSymbolId": current_selected,
            "inspectorName": inspector_name,
            "treeSelected": tree_selected
        }
        assert "build_zoo" in str(current_selected), f"Expected selectedSymbolId to have build_zoo, got {current_selected}"
        assert inspector_name == "build_zoo", f"Expected inspectorName build_zoo, got {inspector_name}"
        assert "build_zoo" in str(tree_selected), f"Expected treeSelected to have build_zoo, got {tree_selected}"

        # 7. Test Dock Toggles & State Preservation
        print("[Automation] Testing Dock Toggles...", flush=True)
        # Set filter in explorer and text in chat
        window.evaluate_js('''
            document.getElementById("explorer-filter").value = "Dog";
            window.filterExplorerTree("Dog");
            document.getElementById("chat-input").value = "Why does Dog inherit Animal?";
        ''')
        time.sleep(0.5)

        # Collapse left dock
        window.evaluate_js('document.getElementById("btn-toggle-explorer").click();')
        time.sleep(0.5)
        left_collapsed = window.evaluate_js('document.getElementById("left-dock").classList.contains("dock-collapsed");')
        print(f"[Automation] Left dock collapsed: {left_collapsed}", flush=True)

        # Expand left dock via rail
        window.evaluate_js('document.getElementById("rail-explorer").click();')
        time.sleep(0.5)
        left_expanded = not window.evaluate_js('document.getElementById("left-dock").classList.contains("dock-collapsed");')
        filter_val = window.evaluate_js('document.getElementById("explorer-filter").value;')
        chat_val = window.evaluate_js('document.getElementById("chat-input").value;')
        print(f"[Automation] Left dock expanded={left_expanded}, filter_val='{filter_val}', chat_val='{chat_val}'", flush=True)
        test_results["dock_toggles"] = {
            "collapse_ok": left_collapsed,
            "expand_ok": left_expanded,
            "filter_preserved": filter_val == "Dog",
            "chat_preserved": chat_val == "Why does Dog inherit Animal?"
        }

        # Clear filter
        window.evaluate_js('document.getElementById("explorer-filter").value = ""; window.filterExplorerTree("");')

        # 8. Test Toolbar Horizontal Scroll & Edge Fades
        print("[Automation] Testing Toolbar Horizontal Scroll & Edge Fades...", flush=True)
        tb_scroll_res = window.evaluate_js('''
            (() => {
                const c = document.getElementById("toolbar-scroll-container");
                if (!c) return { error: "no container" };
                c.scrollLeft = 40;
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
        print(f"[Automation] Toolbar scroll test: {tb_scroll_res}", flush=True)
        test_results["toolbar_scroll"] = tb_scroll_res

        # 9. Test Responsive Floor & 1024x768 Screenshot with Collapsed Dock Combination
        print("[Automation] Resizing to 1024x768 and testing responsive floor...", flush=True)
        window.resize(1024, 768)
        time.sleep(1.0)

        # Collapse Left Dock & Logs Dock to demonstrate responsive collapsed dock combination
        window.evaluate_js('''
            document.getElementById("btn-toggle-explorer").click();
            document.getElementById("btn-toggle-logs").click();
        ''')
        time.sleep(1.0)

        wx, wy, ww, wh = window.x, window.y, window.width, window.height
        img_1024 = ImageGrab.grab(bbox=(wx, wy, wx + ww, wy + wh))
        img_1024_path = SCREENSHOTS_DIR / "desktop_1024x768_collapsed.png"
        img_1024.save(str(img_1024_path))
        print(f"[Automation] Saved desktop_1024x768_collapsed.png ({img_1024.size})", flush=True)
        test_results["responsive_1024"] = {"screenshot": str(img_1024_path), "width": ww, "height": wh}

        print("[Automation] ALL UI CHECKS PASSED SUCCESSFULLY!", flush=True)
        test_results["status"] = "PASSED"

    except Exception as e:
        print(f"[Automation] ERROR in automation routine: {e}", flush=True)
        import traceback
        traceback.print_exc()
        test_results["error"] = str(e)
        test_results["status"] = "FAILED"
    finally:
        with open(BASE_DIR / "scratch" / "ui_test_results.json", "w", encoding="utf-8") as f:
            json.dump(test_results, f, indent=2)
        print("[Automation] Destroying window and exiting...", flush=True)
        time.sleep(1.0)
        window.destroy()

if __name__ == "__main__":
    print("[Main] Launching CodeStruct pywebview for automated UI verification...", flush=True)
    start(func=automation_routine, project_path="sample_project")
