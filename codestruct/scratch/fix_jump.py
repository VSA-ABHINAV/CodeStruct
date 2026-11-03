with open('codestruct/frontend/static/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

bad_block = """    if (elLineInfo) {
        elLineInfo.textContent = `Lines ${lineno}\ufffd${endLineno} (ctx ${reqStart}\ufffd${reqEnd})`;
    }
    const tbFileContext = document.getElementById('toolbar-file-context');
    const tbLineContext = document.getElementById('toolbar-line-context');
    if (tbFileContext) {
        tbFileContext.textContent = ${filePath} : ;
        tbFileContext.title = symbol.id;
    }
    if (tbLineContext) {
        tbLineContext.textContent = Lines -;"""

good_block = """    if (elLineInfo) {
        elLineInfo.textContent = `Lines ${lineno}–${endLineno} (ctx ${reqStart}–${reqEnd})`;
    }
    const tbFileContext = document.getElementById("toolbar-file-context");
    const tbLineContext = document.getElementById("toolbar-line-context");
    if (tbFileContext) {
        tbFileContext.textContent = `${filePath} : ${symbol.name}`;
        tbFileContext.title = symbol.id;
    }
    if (tbLineContext) {
        tbLineContext.textContent = `Lines ${lineno}–${endLineno}`;
    }"""

idx = text.find("const tbFileContext = document.getElementById('toolbar-file-context');")
assert idx != -1, "tbFileContext not found"

start_idx = text.rfind("if (elLineInfo) {", 0, idx)
end_idx = text.find("const codePlaceholder =", idx)

text = text[:start_idx] + good_block + "\n\n    " + text[end_idx:]

with open('codestruct/frontend/static/app.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed jumpToSource successfully!")
