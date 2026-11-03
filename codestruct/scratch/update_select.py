with open('codestruct/frontend/static/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

target = """function selectSymbol(nodeId, source = "unknown") {
    if (!nodeId) return;
    window.selectedSymbolId = nodeId;"""

replacement = """function selectSymbol(nodeId, source = "unknown") {
    if (!nodeId) return;
    let targetId = nodeId;
    if (window.lastGraphData && window.lastGraphData.nodes) {
        const found = window.lastGraphData.nodes.find(n => n.id === nodeId || n.name === nodeId || n.id.endsWith("." + nodeId));
        if (found) targetId = found.id;
    }
    nodeId = targetId;
    window.selectedSymbolId = nodeId;"""

assert target in text, "target not in text"
text = text.replace(target, replacement, 1)

with open('codestruct/frontend/static/app.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated selectSymbol successfully!")

