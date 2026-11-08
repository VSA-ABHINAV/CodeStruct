import re
from pathlib import Path

app_js_path = Path("codestruct/frontend/static/app.js")
content = app_js_path.read_text(encoding="utf-8")

# 1. Update switchCenterTab
old_switch = """    const subToolbar = document.getElementById("center-sub-toolbar");
    const tbGraph = document.getElementById("toolbar-tab-graph");
    const tbTable = document.getElementById("toolbar-tab-table");
    const tbPatterns = document.getElementById("toolbar-tab-patterns");
    const tbCode = document.getElementById("toolbar-tab-code");
    const graphControls = document.getElementById("graph-header-controls");
    const graphViewport = document.getElementById("graph-viewport");
    const codeViewport = document.getElementById("code-viewport");
    const tableViewport = document.getElementById("table-viewport");
    const patternsViewport = document.getElementById("patterns-viewport");

    // Clear active tab states on top toolbar
    if (tbGraph) tbGraph.classList.remove("active");
    if (tbTable) tbTable.classList.remove("active");
    if (tbPatterns) tbPatterns.classList.remove("active");
    if (tbCode) tbCode.classList.remove("active");

    // Hide all viewports & sub-toolbar by default (collapses to zero height for non-graph views)
    if (subToolbar) subToolbar.style.display = "none";
    if (graphControls) graphControls.style.display = "none";
    if (graphViewport) graphViewport.style.display = "none";
    if (codeViewport) codeViewport.style.display = "none";
    if (tableViewport) tableViewport.style.display = "none";
    if (patternsViewport) patternsViewport.style.display = "none";

    if (tabName === "code") {
        if (tbCode) tbCode.classList.add("active");
        if (codeViewport) codeViewport.style.display = "flex";
    } else if (tabName === "table") {
        if (tbTable) tbTable.classList.add("active");
        if (tableViewport) tableViewport.style.display = "flex";
        renderTableView(window.lastGraphData ? window.lastGraphData.nodes : []);
    } else if (tabName === "patterns") {
        if (tbPatterns) tbPatterns.classList.add("active");
        if (patternsViewport) patternsViewport.style.display = "flex";
        loadPatterns();
    } else {"""

new_switch = """    const subToolbar = document.getElementById("center-sub-toolbar");
    const tbGraph = document.getElementById("toolbar-tab-graph");
    const tbTable = document.getElementById("toolbar-tab-table");
    const tbPatterns = document.getElementById("toolbar-tab-patterns");
    const tbCode = document.getElementById("toolbar-tab-code");
    const tbArch = document.getElementById("toolbar-tab-architecture");
    const graphControls = document.getElementById("graph-header-controls");
    const graphViewport = document.getElementById("graph-viewport");
    const codeViewport = document.getElementById("code-viewport");
    const tableViewport = document.getElementById("table-viewport");
    const patternsViewport = document.getElementById("patterns-viewport");
    const archViewport = document.getElementById("architecture-viewport");

    // Clear active tab states on top toolbar
    if (tbGraph) tbGraph.classList.remove("active");
    if (tbTable) tbTable.classList.remove("active");
    if (tbPatterns) tbPatterns.classList.remove("active");
    if (tbCode) tbCode.classList.remove("active");
    if (tbArch) tbArch.classList.remove("active");

    // Hide all viewports & sub-toolbar by default (collapses to zero height for non-graph views)
    if (subToolbar) subToolbar.style.display = "none";
    if (graphControls) graphControls.style.display = "none";
    if (graphViewport) graphViewport.style.display = "none";
    if (codeViewport) codeViewport.style.display = "none";
    if (tableViewport) tableViewport.style.display = "none";
    if (patternsViewport) patternsViewport.style.display = "none";
    if (archViewport) archViewport.style.display = "none";

    if (tabName === "code") {
        if (tbCode) tbCode.classList.add("active");
        if (codeViewport) codeViewport.style.display = "flex";
    } else if (tabName === "table") {
        if (tbTable) tbTable.classList.add("active");
        if (tableViewport) tableViewport.style.display = "flex";
        renderTableView(window.lastGraphData ? window.lastGraphData.nodes : []);
    } else if (tabName === "patterns") {
        if (tbPatterns) tbPatterns.classList.add("active");
        if (patternsViewport) patternsViewport.style.display = "flex";
        loadPatterns();
    } else if (tabName === "architecture") {
        if (tbArch) tbArch.classList.add("active");
        if (archViewport) archViewport.style.display = "flex";
        loadArchitecture();
    } else {"""

# Replace CRLF-normalized
content = content.replace("\r\n", "\n")
assert old_switch in content, "old_switch not found"
content = content.replace(old_switch, new_switch)

# 2. Update selectSymbol to sync with architecture view
old_select_sync = """    // 2c. Sync Patterns View (Phase 13)
    document.querySelectorAll("#patterns-list .pattern-card.selected").forEach(card => card.classList.remove("selected"));
    const patternCard = document.querySelector(`#patterns-list .pattern-card[data-id="${nodeId}"]`);
    if (patternCard) {
        patternCard.classList.add("selected");
        patternCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }"""

new_select_sync = """    // 2c. Sync Patterns View (Phase 13)
    document.querySelectorAll("#patterns-list .pattern-card.selected").forEach(card => card.classList.remove("selected"));
    const patternCard = document.querySelector(`#patterns-list .pattern-card[data-id="${nodeId}"]`);
    if (patternCard) {
        patternCard.classList.add("selected");
        patternCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // 2d. Sync Architecture View (Phase 19)
    document.querySelectorAll(".component-cluster-card.selected").forEach(card => card.classList.remove("selected"));
    document.querySelectorAll(".cluster-member-pill.selected").forEach(pill => pill.classList.remove("selected"));
    const memberPills = document.querySelectorAll(`.cluster-member-pill[data-id="${nodeId}"]`);
    memberPills.forEach(pill => {
        pill.classList.add("selected");
        const parentCard = pill.closest(".component-cluster-card");
        if (parentCard) parentCard.classList.add("selected");
    });"""

assert old_select_sync in content, "old_select_sync not found"
content = content.replace(old_select_sync, new_select_sync)

# 3. Add loadArchitecture and renderArchitectureView after renderPatternsView
arch_functions = """
/**
 * Advanced Architecture Loader and Controller (Phase 19).
 */
let architectureAbortController = null;

async function loadArchitecture(forceRefresh = false) {
    const placeholder = document.getElementById("architecture-placeholder");
    const container = document.getElementById("architecture-container");
    const loadingBox = document.getElementById("architecture-loading");
    const errorBox = document.getElementById("architecture-error");
    const errorMsg = document.getElementById("architecture-error-message");
    const loadingTitle = document.getElementById("architecture-loading-title");
    const loadingStatus = document.getElementById("architecture-loading-status");

    if (!window.lastGraphData) {
        if (placeholder) placeholder.style.display = "flex";
        if (container) container.style.display = "none";
        if (loadingBox) loadingBox.style.display = "none";
        if (errorBox) errorBox.style.display = "none";
        return;
    }

    if (!forceRefresh && window.lastArchitectureData) {
        if (placeholder) placeholder.style.display = "none";
        if (loadingBox) loadingBox.style.display = "none";
        if (errorBox) errorBox.style.display = "none";
        if (container) container.style.display = "flex";
        renderArchitectureView(window.lastArchitectureData);
        return;
    }

    if (architectureAbortController) {
        architectureAbortController.abort();
    }
    architectureAbortController = new AbortController();

    if (placeholder) placeholder.style.display = "none";
    if (container) container.style.display = "none";
    if (errorBox) errorBox.style.display = "none";
    if (loadingBox) loadingBox.style.display = "flex";

    if (loadingTitle) loadingTitle.textContent = "Synthesizing Architecture...";
    if (loadingStatus) loadingStatus.textContent = "Clustering symbols and generating architectural narrative via Ollama (qwen2.5-coder:3b)...";

    // 15s timer for "taking longer than expected"
    const timeoutNoticeTimer = setTimeout(() => {
        if (loadingStatus) {
            loadingStatus.textContent = "Taking longer than expected (LLM synthesis in progress, please wait up to 30s)...";
        }
    }, 15000);

    // 32s overall client timeout
    const hardTimeoutTimer = setTimeout(() => {
        if (architectureAbortController) {
            architectureAbortController.abort();
        }
    }, 32000);

    try {
        const response = await fetch("/api/architecture/advanced", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ force_refresh: forceRefresh }),
            signal: architectureAbortController.signal,
        });

        clearTimeout(timeoutNoticeTimer);
        clearTimeout(hardTimeoutTimer);

        if (!response.ok) {
            let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errJson = await response.json();
                if (errJson.detail) errorDetail = errJson.detail;
            } catch (_) {}
            throw new Error(errorDetail);
        }

        const data = await response.json();
        window.lastArchitectureData = data;

        if (loadingBox) loadingBox.style.display = "none";
        if (errorBox) errorBox.style.display = "none";
        if (container) container.style.display = "flex";

        renderArchitectureView(data);
        appendLog(`[Architecture] Successfully clustered ${data.components.length} components.`);
    } catch (err) {
        clearTimeout(timeoutNoticeTimer);
        clearTimeout(hardTimeoutTimer);

        console.error("[CodeStruct] Failed to load architecture:", err);
        appendLog(`[Error] Architecture clustering failed: ${err.message}`);

        if (loadingBox) loadingBox.style.display = "none";
        if (container) container.style.display = "none";
        if (errorBox) {
            errorBox.style.display = "flex";
            if (errorMsg) {
                errorMsg.textContent = err.name === "AbortError" 
                    ? "Request timed out after 30 seconds. Please ensure Ollama is running and responsive."
                    : err.message;
            }
        }
    }
}

function renderArchitectureView(data) {
    if (!data) return;

    const narrativeEl = document.getElementById("architecture-narrative-text");
    const clusterCountEl = document.getElementById("architecture-cluster-count");
    const unclusteredCountEl = document.getElementById("architecture-unclustered-count");
    const componentsGrid = document.getElementById("architecture-components-grid");
    const unclusteredSection = document.getElementById("architecture-unclustered-section");
    const unclusteredList = document.getElementById("architecture-unclustered-list");

    const components = data.components || [];
    const unclustered = data.unclustered_symbol_ids || [];

    if (clusterCountEl) clusterCountEl.textContent = `${components.length} Component${components.length === 1 ? '' : 's'}`;
    if (unclusteredCountEl) unclusteredCountEl.textContent = `${unclustered.length} Unclustered`;
    if (narrativeEl) narrativeEl.textContent = data.narrative || "No narrative generated.";

    if (componentsGrid) {
        componentsGrid.innerHTML = "";
        components.forEach((comp) => {
            const card = document.createElement("div");
            card.className = "component-cluster-card";
            card.dataset.id = comp.component_id;

            const memberTags = (comp.member_symbol_ids || []).map(mid => {
                const shortName = mid.split(".").pop();
                return `<span class="cluster-member-pill" data-id="${escapeHtml(mid)}" title="${escapeHtml(mid)}">${escapeHtml(shortName)}</span>`;
            }).join("");

            card.innerHTML = `
                <div class="cluster-card-header">
                    <span class="cluster-name">${escapeHtml(comp.name)}</span>
                    <span class="cluster-role-pill">${escapeHtml(comp.role)}</span>
                </div>
                <div class="cluster-rationale">${escapeHtml(comp.rationale)}</div>
                <div class="cluster-members-section">
                    <span class="cluster-members-label">Members (${comp.member_symbol_ids.length})</span>
                    <div class="cluster-member-tags">${memberTags}</div>
                </div>
                <div class="cluster-card-actions">
                    <button class="cluster-action-btn" type="button" title="Highlight in Graph View">View in Graph ↗</button>
                </div>
            `;

            card.querySelectorAll(".cluster-member-pill").forEach(pill => {
                pill.addEventListener("click", (e) => {
                    e.stopPropagation();
                    const sid = pill.dataset.id;
                    highlightComponentInGraph(comp, sid);
                });
            });

            card.addEventListener("click", () => {
                highlightComponentInGraph(comp);
            });

            componentsGrid.appendChild(card);
        });
    }

    if (unclusteredSection && unclusteredList) {
        if (unclustered.length > 0) {
            unclusteredSection.style.display = "flex";
            unclusteredList.innerHTML = unclustered.map(uid => {
                const shortName = uid.split(".").pop();
                return `<span class="unclustered-pill" data-id="${escapeHtml(uid)}" title="${escapeHtml(uid)}">${escapeHtml(shortName)}</span>`;
            }).join("");

            unclusteredList.querySelectorAll(".unclustered-pill").forEach(pill => {
                pill.addEventListener("click", () => {
                    selectSymbol(pill.dataset.id, "architecture_unclustered");
                });
            });
        } else {
            unclusteredSection.style.display = "none";
        }
    }
}

function highlightComponentInGraph(comp, targetSymbolId = null) {
    switchCenterTab("graph");

    if (!window.cy) return;

    window.cy.elements().unselect();
    window.cy.elements().removeClass("highlighted");

    const memberIds = comp.member_symbol_ids || [];
    const elementsToHighlight = [];

    memberIds.forEach(id => {
        const el = window.cy.$id(id);
        if (el && el.length > 0) {
            elementsToHighlight.push(el);
            el.addClass("highlighted");
        }
    });

    if (elementsToHighlight.length > 0) {
        const collection = window.cy.collection(elementsToHighlight);
        window.cy.animate({
            fit: { eles: collection, padding: 60 },
            duration: 300
        });
    }

    const primaryId = targetSymbolId || (memberIds.length > 0 ? memberIds[0] : null);
    if (primaryId) {
        selectSymbol(primaryId, `component:${comp.name}`);
    }
}
"""

anchor_patterns = "function renderPatternsView(patterns) {"
# Find end of renderPatternsView
idx_patterns = content.find(anchor_patterns)
assert idx_patterns != -1, "renderPatternsView not found"
# Find closing brace of renderPatternsView
idx_end_patterns = content.find("\n}\n", idx_patterns)
assert idx_end_patterns != -1, "end of renderPatternsView not found"

content = content[:idx_end_patterns + 3] + arch_functions + content[idx_end_patterns + 3:]

# 4. Update tbMap to include architecture tab
old_tb_map = """        { id: "toolbar-tab-graph", name: "graph" },
        { id: "toolbar-tab-table", name: "table" },
        { id: "toolbar-tab-patterns", name: "patterns" },
        { id: "toolbar-tab-code", name: "code" }"""

new_tb_map = """        { id: "toolbar-tab-graph", name: "graph" },
        { id: "toolbar-tab-table", name: "table" },
        { id: "toolbar-tab-patterns", name: "patterns" },
        { id: "toolbar-tab-code", name: "code" },
        { id: "toolbar-tab-architecture", name: "architecture" }"""

assert old_tb_map in content, "old_tb_map not found"
content = content.replace(old_tb_map, new_tb_map)

# 5. Wire retry and refresh buttons in initApp
old_init_buttons = """    const btnOpenProject = document.getElementById("btn-open-project");"""
new_init_buttons = """    const btnArchRetry = document.getElementById("btn-architecture-retry");
    if (btnArchRetry) {
        btnArchRetry.addEventListener("click", () => {
            loadArchitecture(true);
        });
    }

    const btnArchRefresh = document.getElementById("btn-architecture-refresh");
    if (btnArchRefresh) {
        btnArchRefresh.addEventListener("click", () => {
            loadArchitecture(true);
        });
    }

    const btnOpenProject = document.getElementById("btn-open-project");"""

assert old_init_buttons in content, "old_init_buttons not found"
content = content.replace(old_init_buttons, new_init_buttons)

# 6. Reset lastArchitectureData on new analysis
old_run_analysis_reset = """        const data = await response.json();
        window.lastGraphData = data;"""
new_run_analysis_reset = """        const data = await response.json();
        window.lastGraphData = data;
        window.lastArchitectureData = null;"""

assert old_run_analysis_reset in content, "old_run_analysis_reset not found"
content = content.replace(old_run_analysis_reset, new_run_analysis_reset)

# Write back with CRLF
content_crlf = content.replace("\n", "\r\n")
app_js_path.write_text(content_crlf, encoding="utf-8")
print("app.js successfully updated with Phase 19 architecture features!")
