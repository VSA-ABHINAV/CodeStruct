with open('codestruct/frontend/static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

is_crlf = '\r\n' in content
norm = content.replace('\r\n', '\n')

old_func = """    function updateRightDockRail() {
        if (!rightDock || !inspectorPanel || !qwenPanel) return;
        const inspCollapsed = inspectorPanel.classList.contains("dock-collapsed");
        const qwenCollapsed = qwenPanel.classList.contains("dock-collapsed");
        if (inspCollapsed && qwenCollapsed) {
            rightDock.classList.add("dock-collapsed");
        } else {
            rightDock.classList.remove("dock-collapsed");
        }
    }"""

new_func = """    function updateRightDockRail() {
        if (!rightDock || !inspectorPanel || !qwenPanel) return;
        const inspCollapsed = inspectorPanel.classList.contains("dock-collapsed");
        const qwenCollapsed = qwenPanel.classList.contains("dock-collapsed");
        if (inspCollapsed && qwenCollapsed) {
            rightDock.classList.add("both-collapsed");
            rightDock.classList.add("dock-collapsed");
            rightDock.classList.remove("one-collapsed");
        } else if (inspCollapsed || qwenCollapsed) {
            rightDock.classList.add("one-collapsed");
            rightDock.classList.remove("both-collapsed");
            rightDock.classList.remove("dock-collapsed");
        } else {
            rightDock.classList.remove("both-collapsed");
            rightDock.classList.remove("one-collapsed");
            rightDock.classList.remove("dock-collapsed");
        }
    }"""

if old_func in norm:
    norm = norm.replace(old_func, new_func)
    print("updateRightDockRail replaced")
else:
    print("updateRightDockRail NOT found")

if is_crlf:
    norm = norm.replace('\n', '\r\n')

with open('codestruct/frontend/static/app.js', 'w', encoding='utf-8') as f:
    f.write(norm)

print("Finished updating app.js")
