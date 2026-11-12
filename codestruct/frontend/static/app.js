/**
 * CodeStruct — Frontend Application Logic (Phase 6)
 * Graph Visualization + Explorer Tree + Inspector Panel with API Integration
 */

// Global State
window.cy = null;
window.lastGraphData = null;
window.currentProjectPath = "sample_project";
window.selectedSymbolId = null;
window.currentSymbolDetail = null;
window.activeCenterTab = "graph";
window.currentSourceView = null;

/**
 * Append message to the bottom status & log output area.
 */
function appendLog(message) {
    const logOutput = document.getElementById("log-output");
    if (!logOutput) return;
    const time = new Date().toLocaleTimeString();
    const entry = `[${time}] ${message}`;
    logOutput.textContent = logOutput.textContent ? `${logOutput.textContent}\n${entry}` : entry;
    const logBody = document.getElementById("log-body");
    if (logBody) logBody.scrollTop = logBody.scrollHeight;

    const stripLogLatest = document.getElementById("strip-log-latest");
    if (stripLogLatest) stripLogLatest.textContent = message;
}

/**
 * Update the bottom status bar with summary counts and status text.
 */
function updateStatusBar(summary, statusText = "Ready") {
    const statusMsg = document.getElementById("status-message");
    const statusStats = document.getElementById("status-stats");
    if (statusMsg) statusMsg.textContent = statusText;
    if (statusStats && summary) {
        statusStats.textContent = `${summary.node_count || 0} nodes / ${summary.edge_count || 0} edges`;
    }
}

/**
 * Apply the 4 kind filter checkboxes (module, class, function, method) to Cytoscape nodes.
 */
function applyFilters() {
    if (!window.cy) return;
    const kinds = ["module", "class", "function", "method"];
    kinds.forEach(kind => {
        const checkbox = document.getElementById(`filter-${kind}`);
        const isChecked = checkbox ? checkbox.checked : true;
        const matchingNodes = window.cy.nodes(`[kind = "${kind}"]`);
        if (isChecked) {
            matchingNodes.style("display", "element");
        } else {
            matchingNodes.style("display", "none");
        }
    });
}

/**
 * Fetch and render Symbol Details in the Inspector panel (Phase 6).
 */
async function loadSymbolDetail(nodeId) {
    if (!nodeId) return;

    const placeholder = document.getElementById("inspector-placeholder");
    const detailsContainer = document.getElementById("inspector-details");
    if (placeholder) placeholder.style.display = "none";
    if (detailsContainer) detailsContainer.style.display = "flex";

    // Immediate clear to avoid any stale data
    const elName = document.getElementById("inspector-name");
    const elKind = document.getElementById("inspector-kind");
    const elFile = document.getElementById("inspector-file");
    const elLines = document.getElementById("inspector-lines");
    const elFanIn = document.getElementById("inspector-fan-in");
    const elFanOut = document.getElementById("inspector-fan-out");
    const elInstability = document.getElementById("inspector-instability");
    const elDoc = document.getElementById("inspector-docstring");
    const elDocBox = document.getElementById("inspector-docstring-container");
    const elInList = document.getElementById("inspector-incoming-list");
    const elOutList = document.getElementById("inspector-outgoing-list");
    const elCountIn = document.getElementById("count-incoming");
    const elCountOut = document.getElementById("count-outgoing");

    if (elName) elName.textContent = "Loading...";
    if (elFile) elFile.textContent = "-";
    if (elLines) elLines.textContent = "-";
    if (elFanIn) elFanIn.textContent = "-";
    if (elFanOut) elFanOut.textContent = "-";
    if (elInstability) elInstability.textContent = "-";
    if (elDoc) elDoc.textContent = "";
    if (elInList) elInList.innerHTML = "<li class='rel-empty'>Loading...</li>";
    if (elOutList) elOutList.innerHTML = "<li class='rel-empty'>Loading...</li>";

    try {
        const response = await fetch(`/api/symbol/${encodeURIComponent(nodeId)}`);
        if (!response.ok) {
            let detail = `Symbol not found (${response.status})`;
            try {
                const errData = await response.json();
                if (errData && errData.detail) detail = errData.detail;
            } catch (_) {}

            appendLog(`[Warning] Symbol lookup failed: ${detail}`);

            // Render friendly non-broken message in Inspector (Phase 9)
            if (elName) elName.textContent = "Symbol Not Found";
            if (elKind) {
                elKind.textContent = "unknown";
                elKind.className = "inspector-kind-badge badge-kind-unknown";
            }
            if (elFile) elFile.textContent = "-";
            if (elLines) elLines.textContent = "-";
            if (elFanIn) elFanIn.textContent = "0";
            if (elFanOut) elFanOut.textContent = "0";
            if (elInstability) elInstability.textContent = "0.00";
            if (elDocBox && elDoc) {
                elDoc.textContent = `The symbol "${nodeId}" could not be found in the current analysis.`;
                elDocBox.style.display = "flex";
            }
            if (elInList) elInList.innerHTML = "<li class='rel-empty'>None</li>";
            if (elOutList) elOutList.innerHTML = "<li class='rel-empty'>None</li>";
            if (elCountIn) elCountIn.textContent = "0";
            if (elCountOut) elCountOut.textContent = "0";

            return null;
        }
        const data = await response.json();

        // Discard if selection changed during network fetch
        if (window.selectedSymbolId !== nodeId) {
            return;
        }

        window.currentSymbolDetail = data;

        // Populate Metadata
        if (elName) elName.textContent = data.name;
        if (elKind) {
            elKind.textContent = data.kind;
            elKind.className = `inspector-kind-badge badge-kind-${data.kind}`;
        }
        if (elFile) elFile.textContent = data.file_path;
        if (elLines) elLines.textContent = `${data.lineno}–${data.end_lineno}`;
        if (elFanIn) elFanIn.textContent = String(data.fan_in);
        if (elFanOut) elFanOut.textContent = String(data.fan_out);
        if (elInstability) {
            elInstability.textContent = (data.instability !== undefined && data.instability !== null)
                ? Number(data.instability).toFixed(2)
                : "0.00";
        }

        // Docstring
        if (elDocBox && elDoc) {
            if (data.docstring && data.docstring.trim()) {
                elDoc.textContent = data.docstring.trim();
                elDocBox.style.display = "flex";
            } else {
                elDoc.textContent = "No docstring provided.";
                elDocBox.style.display = "flex";
            }
        }

        // Incoming list
        if (elCountIn) elCountIn.textContent = String((data.incoming || []).length);
        if (elInList) {
            elInList.innerHTML = "";
            if (data.incoming && data.incoming.length > 0) {
                data.incoming.forEach(edge => {
                    const li = document.createElement("li");
                    li.className = "rel-item";
                    li.dataset.id = edge.id;
                    li.title = `Click to inspect ${edge.id}`;
                    li.innerHTML = `
                        <span class="rel-name">${edge.name}</span>
                        <span class="rel-type type-${edge.type}">${edge.type}</span>
                    `;
                    li.addEventListener("click", () => {
                        selectSymbol(edge.id, "inspector");
                    });
                    elInList.appendChild(li);
                });
            } else {
                elInList.innerHTML = "<li class='rel-empty'>None</li>";
            }
        }

        // Outgoing list
        if (elCountOut) elCountOut.textContent = String((data.outgoing || []).length);
        if (elOutList) {
            elOutList.innerHTML = "";
            if (data.outgoing && data.outgoing.length > 0) {
                data.outgoing.forEach(edge => {
                    const li = document.createElement("li");
                    li.className = "rel-item";
                    li.dataset.id = edge.id;
                    li.title = `Click to inspect ${edge.id}`;
                    li.innerHTML = `
                        <span class="rel-name">${edge.name}</span>
                        <span class="rel-type type-${edge.type}">${edge.type}</span>
                    `;
                    li.addEventListener("click", () => {
                        selectSymbol(edge.id, "inspector");
                    });
                    elOutList.appendChild(li);
                });
            } else {
                elOutList.innerHTML = "<li class='rel-empty'>None</li>";
            }
        }

        // Load Change Impact (Phase 15)
        loadSymbolImpact(nodeId);

        return data;
    } catch (err) {
        console.error("[CodeStruct] Failed to load symbol detail:", err);
        appendLog(`[Error] Inspector fetch failed: ${err.message}`);
        if (elName) elName.textContent = "Error loading symbol";
    }
}

/**
 * Load Change Impact BFS results for the selected symbol and render grouped by depth (Phase 15).
 */
async function loadSymbolImpact(symbolId) {
    const elResults = document.getElementById("inspector-impact-results");
    const elEmpty = document.getElementById("inspector-impact-empty");
    const elCount = document.getElementById("count-impact");

    if (!elResults) return;
    elResults.innerHTML = "<div class='rel-empty'>Calculating impact...</div>";
    if (elEmpty) elEmpty.style.display = "none";
    if (elCount) elCount.textContent = "0";

    try {
        const resp = await fetch(`/api/impact/${encodeURIComponent(symbolId)}?max_depth=5`);
        if (!resp.ok) {
            elResults.innerHTML = "<div class='rel-empty'>Impact unavailable</div>";
            return;
        }
        const data = await resp.json();
        const impacted = data.impacted || [];
        if (elCount) elCount.textContent = String(impacted.length);

        if (impacted.length === 0) {
            elResults.innerHTML = "";
            if (elEmpty) elEmpty.style.display = "block";
            return;
        }

        if (elEmpty) elEmpty.style.display = "none";
        elResults.innerHTML = "";

        // Group by depth
        const groups = {};
        impacted.forEach(item => {
            const d = item.depth || 1;
            if (!groups[d]) groups[d] = [];
            groups[d].push(item);
        });

        const sortedDepths = Object.keys(groups).map(Number).sort((a, b) => a - b);
        sortedDepths.forEach(depth => {
            const groupDiv = document.createElement("div");
            groupDiv.className = "impact-depth-group";
            groupDiv.innerHTML = `
                <div class="impact-depth-header">
                    <span class="depth-badge">Depth ${depth}</span>
                    <span class="depth-count">${groups[depth].length} symbol${groups[depth].length > 1 ? 's' : ''}</span>
                </div>
                <ul class="impact-list"></ul>
            `;
            const listEl = groupDiv.querySelector(".impact-list");
            groups[depth].forEach(item => {
                const li = document.createElement("li");
                li.className = "impact-item";
                li.dataset.id = item.id;
                li.title = `Click to inspect ${item.id} (Depth ${item.depth} via ${item.via_edge_type})`;
                li.innerHTML = `
                    <span class="impact-name">${item.name}</span>
                    <span class="impact-edge-badge badge-${item.via_edge_type}">${item.via_edge_type}</span>
                `;
                li.addEventListener("click", (e) => {
                    e.stopPropagation();
                    selectSymbol(item.id, "impact");
                });
                listEl.appendChild(li);
            });
            elResults.appendChild(groupDiv);
        });
    } catch (err) {
        console.error("[CodeStruct] Failed to load impact:", err);
        elResults.innerHTML = "<div class='rel-empty'>Error calculating impact</div>";
    }
}

/**
 * Switch the center panel between "graph", "table", "patterns", and "code" tabs (Phase 7, 12 & 13).
 */
function switchCenterTab(tabName) {
    window.activeCenterTab = tabName;

    const subToolbar = document.getElementById("center-sub-toolbar");
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
    } else {
        // default: "graph"
        if (tbGraph) tbGraph.classList.add("active");
        if (subToolbar) subToolbar.style.display = "flex";
        if (graphControls) graphControls.style.display = "flex";
        if (graphViewport) graphViewport.style.display = "block";
        if (window.cy) {
            window.cy.resize();
        }
    }
}

/**
 * Jump to syntax-highlighted source code for a symbol (Phase 7).
 * Fetches source with ±5 context lines, highlights exact symbol lines, and auto-scrolls.
 */
async function jumpToSource(target) {
    let symbol = target;

    // If target is a symbol ID string, resolve it
    if (typeof target === "string") {
        if (window.currentSymbolDetail && window.currentSymbolDetail.id === target) {
            symbol = window.currentSymbolDetail;
        } else {
            try {
                const res = await fetch(`/api/symbol/${encodeURIComponent(target)}`);
                if (res.ok) {
                    symbol = await res.json();
                } else {
                    throw new Error(`Symbol ${target} not found`);
                }
            } catch (err) {
                appendLog(`[Error] Could not find symbol to jump: ${err.message}`);
                return;
            }
        }
    }

    if (!symbol || !symbol.file_path) {
        appendLog("[Warn] Jump to source: No valid symbol selected.");
        return;
    }

    // Switch to Code Viewer tab
    switchCenterTab("code");

    const filePath = symbol.file_path;
    const lineno = symbol.lineno;
    const endLineno = symbol.end_lineno || symbol.lineno;

    // Pad surrounding context by ±5 lines
    const pad = 5;
    const reqStart = Math.max(1, lineno - pad);
    const reqEnd = endLineno + pad;

    // Update Header Meta
    const elFilePath = document.getElementById("code-file-path");
    const elLineInfo = document.getElementById("code-line-info");
    if (elFilePath) {
        elFilePath.textContent = `${filePath} : ${symbol.name}`;
        elFilePath.title = symbol.id;
    }
        if (elLineInfo) {
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
    }

    const codePlaceholder = document.getElementById("code-placeholder");
    const codeContainer = document.getElementById("code-container");
    const codeContent = document.getElementById("code-content");

    if (codePlaceholder) codePlaceholder.style.display = "none";
    if (codeContainer) codeContainer.style.display = "block";
    if (codeContent) codeContent.innerHTML = "<div class='code-loading'>Loading source...</div>";

    try {
        const url = `/api/source?file_path=${encodeURIComponent(filePath)}&start=${reqStart}&end=${reqEnd}`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();

        // Render Pygments HTML
        codeContent.innerHTML = data.html;

        // Apply highlight class to exact symbol line range
        for (let l = lineno; l <= endLineno; l++) {
            const lineEl = document.getElementById(`line-${l}`);
            if (lineEl) {
                lineEl.classList.add("source-line-highlighted");
            }
        }

        // Auto-scroll so the symbol's start line is visible
        const startLineEl = document.getElementById(`line-${lineno}`);
        if (startLineEl) {
            startLineEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        window.currentSourceView = {
            symbolId: symbol.id,
            filePath: filePath,
            lineno: lineno,
            endLineno: endLineno,
            reqStart: reqStart,
            reqEnd: reqEnd,
        };

        appendLog(`Jumped to source: ${symbol.id} (${filePath}:${lineno}–${endLineno})`);
        return window.currentSourceView;
    } catch (err) {
        console.error("[CodeStruct] Failed to load source:", err);
        appendLog(`[Error] Failed to load source: ${err.message}`);
        if (codeContent) {
            codeContent.innerHTML = `<div class="code-error">Error loading source: ${err.message}</div>`;
        }
    }
}

/**
 * Safely escape string for insertion into HTML.
 */
function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Open a file in the user's external default editor (Phase 12).
 */
async function openInEditor(filePath) {
    if (!filePath) {
        appendLog("[Warn] No file selected to open in editor.");
        return;
    }
    appendLog(`[Editor] Opening ${filePath}...`);
    try {
        const response = await fetch("/api/open_in_editor", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file_path: filePath })
        });
        const data = await response.json();
        if (response.ok && data.launched) {
            appendLog(`[Editor] Launched external editor for ${data.file_path}`);
        } else {
            const err = data.detail || "Failed to open file";
            appendLog(`[Error] Editor launch failed: ${err}`);
        }
    } catch (err) {
        appendLog(`[Error] Failed to open in editor: ${err.message}`);
    }
}

// State for Table View (Phase 12)
window.tableSortColumn = "name";
window.tableSortAscending = true;

/**
 * Render the symbols table in Table View (Phase 12).
 */
function renderTableView(nodes) {
    const tablePlaceholder = document.getElementById("table-placeholder");
    const tableContainer = document.getElementById("table-container");
    const tbody = document.getElementById("symbols-table-body");
    if (!tbody) return;

    const list = nodes || (window.lastGraphData ? window.lastGraphData.nodes : []) || [];
    if (list.length === 0) {
        if (tablePlaceholder) tablePlaceholder.style.display = "flex";
        if (tableContainer) tableContainer.style.display = "none";
        tbody.innerHTML = "";
        return;
    }

    if (tablePlaceholder) tablePlaceholder.style.display = "none";
    if (tableContainer) tableContainer.style.display = "block";

    // Sort nodes copy
    const sorted = [...list].sort((a, b) => {
        let valA = a[window.tableSortColumn];
        let valB = b[window.tableSortColumn];

        if (valA === undefined || valA === null) valA = "";
        if (valB === undefined || valB === null) valB = "";

        if (typeof valA === "number" && typeof valB === "number") {
            return window.tableSortAscending ? valA - valB : valB - valA;
        }

        const comp = String(valA).localeCompare(String(valB), undefined, { numeric: true, sensitivity: "base" });
        return window.tableSortAscending ? comp : -comp;
    });

    // Update header sort indicators
    document.querySelectorAll("#symbols-table th.sortable").forEach(th => {
        const col = th.dataset.col;
        const indicator = th.querySelector(".sort-indicator");
        th.classList.remove("sort-asc", "sort-desc");
        if (col === window.tableSortColumn) {
            th.classList.add(window.tableSortAscending ? "sort-asc" : "sort-desc");
            if (indicator) indicator.textContent = window.tableSortAscending ? " ▲" : " ▼";
        } else {
            if (indicator) indicator.textContent = "";
        }
    });

    tbody.innerHTML = "";
    sorted.forEach(node => {
        const tr = document.createElement("tr");
        tr.dataset.id = node.id;
        tr.dataset.name = node.name;
        if (node.id === window.selectedSymbolId) {
            tr.classList.add("selected");
        }

        tr.innerHTML = `
            <td class="col-name">${escapeHtml(node.name)}</td>
            <td class="col-kind"><span class="inspector-kind-badge badge-kind-${node.kind}">${node.kind}</span></td>
            <td class="col-module">${escapeHtml(node.module || "-")}</td>
            <td class="col-file">${escapeHtml(node.file_path || "-")}</td>
            <td class="col-line">${node.lineno != null ? node.lineno : "-"}</td>
            <td class="col-line">${node.end_lineno != null ? node.end_lineno : "-"}</td>
        `;

        tr.addEventListener("click", () => {
            selectSymbol(node.id, "table");
        });

        tbody.appendChild(tr);
    });

    // Apply any active explorer filter
    const filterInput = document.getElementById("explorer-filter");
    if (filterInput && filterInput.value.trim()) {
        const q = filterInput.value.trim().toLowerCase();
        tbody.querySelectorAll("tr").forEach(tr => {
            const name = (tr.dataset.name || "").toLowerCase();
            const id = (tr.dataset.id || "").toLowerCase();
            tr.style.display = (name.includes(q) || id.includes(q)) ? "" : "none";
        });
    }
}

/**
 * Load detected patterns from the backend for the currently analyzed project (Phase 13).
 */
async function loadPatterns() {
    const placeholder = document.getElementById("patterns-placeholder");
    const container = document.getElementById("patterns-container");
    const emptyBox = document.getElementById("patterns-empty");
    const listEl = document.getElementById("patterns-list");

    if (!window.lastGraphData) {
        if (placeholder) placeholder.style.display = "flex";
        if (container) container.style.display = "none";
        return [];
    }

    if (placeholder) placeholder.style.display = "none";
    if (container) container.style.display = "flex";

    try {
        const response = await fetch("/api/patterns");
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();
        const patterns = data.patterns || [];
        window.lastPatterns = patterns;
        renderPatternsView(patterns);
        return patterns;
    } catch (err) {
        console.error("[CodeStruct] Failed to load patterns:", err);
        appendLog(`[Error] Failed to load design patterns: ${err.message}`);
        if (emptyBox) {
            emptyBox.style.display = "flex";
            const sub = emptyBox.querySelector(".placeholder-subtext");
            if (sub) sub.textContent = `Error loading patterns: ${err.message}`;
        }
        if (listEl) listEl.innerHTML = "";
        return [];
    }
}

/**
 * Render the list of detected design patterns (Phase 13).
 */
function renderPatternsView(patterns) {
    const emptyBox = document.getElementById("patterns-empty");
    const listEl = document.getElementById("patterns-list");
    if (!listEl) return;

    listEl.innerHTML = "";

    if (!patterns || patterns.length === 0) {
        if (emptyBox) emptyBox.style.display = "flex";
        listEl.style.display = "none";
        return;
    }

    if (emptyBox) emptyBox.style.display = "none";
    listEl.style.display = "flex";

    patterns.forEach(item => {
        const card = document.createElement("div");
        card.className = "pattern-card";
        card.dataset.id = item.symbol_id;

        if (item.symbol_id === window.selectedSymbolId) {
            card.classList.add("selected");
        }

        const shortName = item.symbol_id.split(".").pop();

        card.innerHTML = `
            <div class="pattern-card-header">
                <span class="pattern-badge badge-${escapeHtml(item.pattern)}">${escapeHtml(item.pattern)}</span>
                <span class="pattern-symbol-name">${escapeHtml(shortName)}</span>
                <span class="pattern-symbol-id">(${escapeHtml(item.symbol_id)})</span>
            </div>
            <div class="pattern-evidence">
                <span class="evidence-label">Evidence:</span>
                <span class="evidence-text">${escapeHtml(item.evidence)}</span>
            </div>
        `;

        card.addEventListener("click", () => {
            selectSymbol(item.symbol_id, "patterns");
        });

        listEl.appendChild(card);
    });
}

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
    if (loadingStatus) loadingStatus.textContent = "Clustering symbols and generating architectural narrative via configured LLM...";

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
        const archSelect = document.getElementById("architecture-model-select");
        const selectedModelId = archSelect && archSelect.value ? archSelect.value : null;
        const response = await fetch("/api/architecture/advanced", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ force_refresh: forceRefresh, model_id: selectedModelId }),
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

/**
 * Select a symbol bidirectionally: highlight tree item, highlight/center graph node, and populate Inspector.
 */
function selectSymbol(nodeId, source = "unknown") {
    if (!nodeId) return;
    let targetId = nodeId;
    if (window.lastGraphData && window.lastGraphData.nodes) {
        const found = window.lastGraphData.nodes.find(n => n.id === nodeId || n.name === nodeId || n.id.endsWith("." + nodeId));
        if (found) targetId = found.id;
    }
    nodeId = targetId;
    window.selectedSymbolId = nodeId;

    // 1. Sync Explorer Tree
    document.querySelectorAll(".tree-item.selected").forEach(el => el.classList.remove("selected"));
    const treeItem = document.querySelector(`.tree-item[data-id="${nodeId}"]`);
    if (treeItem) {
        treeItem.classList.add("selected");
        treeItem.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // 2. Sync Cytoscape Graph
    if (window.cy) {
        window.cy.elements().unselect();
        window.cy.elements().removeClass("highlighted");
        const cyNode = window.cy.$id(nodeId);
        if (cyNode && cyNode.length > 0) {
            cyNode.select();
            cyNode.addClass("highlighted");
            window.cy.animate({
                center: { eles: cyNode },
                duration: 250
            });
        }
    }

    // 2b. Sync Table View (Phase 12)
    document.querySelectorAll("#symbols-table-body tr.selected").forEach(row => row.classList.remove("selected"));
    const tableRow = document.querySelector(`#symbols-table-body tr[data-id="${nodeId}"]`);
    if (tableRow) {
        tableRow.classList.add("selected");
        tableRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // 2c. Sync Patterns View (Phase 13)
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
    });

    // 3. Populate Inspector Panel (Phase 6)
    loadSymbolDetail(nodeId);

    appendLog(`Selected [${source}]: ${nodeId}`);
}

/**
 * Build and populate the Explorer tree from Graph JSON data (Phase 5).
 */
function populateExplorerTree(graphData) {
    const placeholder = document.getElementById("explorer-placeholder");
    const treeRoot = document.getElementById("tree-root");
    if (!treeRoot) return;

    const nodes = graphData.nodes || [];
    if (nodes.length === 0) {
        if (placeholder) {
            placeholder.style.display = "flex";
            const pText = placeholder.querySelector(".placeholder-text");
            const pSub = placeholder.querySelector(".placeholder-subtext");
            if (pText) pText.textContent = "No symbols found";
            if (pSub) {
                pSub.textContent = (graphData.errors && graphData.errors.length > 0)
                    ? graphData.errors[0].message
                    : "The analyzed project contains no Python files.";
            }
        }
        treeRoot.style.display = "none";
        treeRoot.innerHTML = "";
        return;
    }

    if (placeholder) {
        placeholder.style.display = "none";
    }
    treeRoot.style.display = "flex";
    treeRoot.innerHTML = "";

    // Group nodes by file_path
    const filesMap = new Map();
    nodes.forEach(n => {
        const fileKey = n.file_path || "unknown";
        if (!filesMap.has(fileKey)) {
            filesMap.set(fileKey, []);
        }
        filesMap.get(fileKey).push(n);
    });

    filesMap.forEach((fileNodes, filePath) => {
        const fileGroup = document.createElement("div");
        fileGroup.className = "tree-file-group";

        // File Header
        const fileHeader = document.createElement("div");
        fileHeader.className = "tree-file-header";
        fileHeader.innerHTML = `<span class="tree-file-icon">📄</span> <span class="tree-label">${filePath}</span>`;
        fileGroup.appendChild(fileHeader);

        // Find module node
        const moduleNode = fileNodes.find(n => n.kind === "module");
        const moduleContainer = document.createElement("div");
        moduleContainer.className = "tree-module-container";

        if (moduleNode) {
            const modItem = createTreeItemElement(moduleNode, 0);
            moduleContainer.appendChild(modItem);
        }

        // Classes within module
        const classes = fileNodes.filter(n => n.kind === "class");
        classes.forEach(clsNode => {
            const classGroup = document.createElement("div");
            classGroup.className = "tree-node-group";
            classGroup.dataset.owner = clsNode.id;

            const clsItem = createTreeItemElement(clsNode, 1);
            classGroup.appendChild(clsItem);

            // Methods inside this class
            const methods = fileNodes.filter(n => n.kind === "method" && n.parent_id === clsNode.id);
            if (methods.length > 0) {
                const methodsContainer = document.createElement("div");
                methodsContainer.className = "tree-children";
                methods.forEach(methodNode => {
                    const methodItem = createTreeItemElement(methodNode, 2);
                    methodsContainer.appendChild(methodItem);
                });
                classGroup.appendChild(methodsContainer);
            }

            moduleContainer.appendChild(classGroup);
        });

        // Top-level functions within module
        const functions = fileNodes.filter(n => n.kind === "function");
        functions.forEach(funcNode => {
            const funcItem = createTreeItemElement(funcNode, 1);
            moduleContainer.appendChild(funcItem);
        });

        fileGroup.appendChild(moduleContainer);
        treeRoot.appendChild(fileGroup);
    });
}

/**
 * Helper to create a single tree item element.
 */
function createTreeItemElement(node, indentLevel) {
    const el = document.createElement("div");
    el.className = `tree-item tree-indent-${indentLevel}`;
    el.dataset.id = node.id;
    el.dataset.name = node.name;
    el.dataset.kind = node.kind;

    const kindAbbr = {
        module: "mod",
        class: "cls",
        function: "fn",
        method: "met"
    }[node.kind] || node.kind.slice(0, 3);

    el.innerHTML = `
        <span class="tree-badge badge-kind-${node.kind}">${kindAbbr}</span>
        <span class="tree-label" title="${node.id}">${node.name}</span>
    `;

    el.addEventListener("click", (e) => {
        e.stopPropagation();
        selectSymbol(node.id, "tree");
    });

    return el;
}

/**
 * Filter Explorer tree items by substring match on symbol name (Phase 5).
 */
function filterExplorerTree(query) {
    const q = (query || "").trim().toLowerCase();
    const treeRoot = document.getElementById("tree-root");
    if (!treeRoot) return;

    const allItems = treeRoot.querySelectorAll(".tree-item");
    const allGroups = treeRoot.querySelectorAll(".tree-node-group, .tree-file-group, .tree-children");
    const tableRows = document.querySelectorAll("#symbols-table-body tr");

    if (!q) {
        allItems.forEach(item => { item.style.display = ""; });
        allGroups.forEach(grp => { grp.style.display = ""; });
        tableRows.forEach(tr => { tr.style.display = ""; });
        return;
    }

    tableRows.forEach(tr => {
        const name = (tr.dataset.name || "").toLowerCase();
        const id = (tr.dataset.id || "").toLowerCase();
        tr.style.display = (name.includes(q) || id.includes(q)) ? "" : "none";
    });

    allItems.forEach(item => { item.style.display = "none"; });

    allItems.forEach(item => {
        const name = (item.dataset.name || "").toLowerCase();
        if (name.includes(q)) {
            item.style.display = "flex";

            const parentGroup = item.closest(".tree-node-group");
            if (item.dataset.kind === "class" && parentGroup) {
                parentGroup.querySelectorAll(".tree-item").forEach(child => {
                    child.style.display = "flex";
                });
            }

            let cur = item.parentElement;
            while (cur && cur !== treeRoot) {
                if (cur.classList.contains("tree-node-group") ||
                    cur.classList.contains("tree-file-group") ||
                    cur.classList.contains("tree-children") ||
                    cur.classList.contains("tree-module-container")) {
                    cur.style.display = "";
                }
                cur = cur.parentElement;
            }
        }
    });

    treeRoot.querySelectorAll(".tree-node-group").forEach(grp => {
        const visibleChildren = grp.querySelectorAll(".tree-item:not([style*='display: none'])");
        if (visibleChildren.length === 0) {
            grp.style.display = "none";
        }
    });
}

/**
 * Render Graph JSON data into the Cytoscape graph canvas.
 */
function renderGraph(graphData) {
    const cyContainer = document.getElementById("cy");
    const placeholder = document.getElementById("graph-placeholder");
    if (!cyContainer) return;

    if (!graphData.nodes || graphData.nodes.length === 0) {
        if (placeholder) {
            placeholder.style.display = "flex";
            const heading = placeholder.querySelector(".placeholder-heading");
            const subtext = placeholder.querySelector(".placeholder-subtext");
            if (heading) heading.textContent = "No Symbols Found";
            if (subtext) {
                const warnMsg = (graphData.errors && graphData.errors.length > 0)
                    ? graphData.errors[0].message
                    : "No Python files or symbols were found in the analyzed project.";
                subtext.textContent = warnMsg;
            }
        }
        if (window.cy) {
            try {
                window.cy.destroy();
                window.cy = null;
            } catch (e) {
                console.warn("Error destroying previous cy instance:", e);
            }
        }
        return;
    }

    if (placeholder) {
        placeholder.style.display = "none";
    }

    const cyElements = [];

    // Nodes
    (graphData.nodes || []).forEach(node => {
        cyElements.push({
            group: "nodes",
            data: {
                id: node.id,
                label: node.name,
                kind: node.kind,
                module: node.module,
                file_path: node.file_path,
                lineno: node.lineno,
                end_lineno: node.end_lineno,
                parent_id: node.parent_id,
                docstring: node.docstring
            }
        });
    });

    // Edges
    (graphData.edges || []).forEach((edge, idx) => {
        cyElements.push({
            group: "edges",
            data: {
                id: `e_${idx}_${edge.source}_${edge.target}_${edge.type}`,
                source: edge.source,
                target: edge.target,
                type: edge.type,
                label: edge.type
            }
        });
    });

    if (window.cy) {
        try {
            window.cy.destroy();
        } catch (e) {
            console.warn("Error destroying previous cy instance:", e);
        }
    }

    window.cy = cytoscape({
        container: cyContainer,
        elements: cyElements,
        style: [
            {
                selector: "node",
                style: {
                    "shape": "round-rectangle",
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "color": "#ffffff",
                    "font-size": "11px",
                    "font-family": "Segoe UI, sans-serif",
                    "font-weight": 600,
                    "padding": "6px",
                    "width": "label",
                    "height": "28px",
                    "border-width": 1.5,
                    "border-color": "#ffffff",
                    "text-outline-color": "#111827",
                    "text-outline-width": 1
                }
            },
            {
                selector: "node[kind = 'module']",
                style: {
                    "background-color": "#8b5cf6",
                    "border-color": "#a78bfa",
                    "height": "32px"
                }
            },
            {
                selector: "node[kind = 'class']",
                style: {
                    "background-color": "#3b82f6",
                    "border-color": "#60a5fa",
                    "height": "30px"
                }
            },
            {
                selector: "node[kind = 'function']",
                style: {
                    "background-color": "#10b981",
                    "border-color": "#34d399",
                    "height": "28px"
                }
            },
            {
                selector: "node[kind = 'method']",
                style: {
                    "background-color": "#f59e0b",
                    "border-color": "#fbbf24",
                    "height": "26px"
                }
            },
            {
                selector: "node.highlighted, node:selected",
                style: {
                    "border-width": 3.5,
                    "border-color": "#facc15",
                    "text-outline-color": "#000000",
                    "text-outline-width": 2,
                    "z-index": 999
                }
            },
            {
                selector: "edge",
                style: {
                    "curve-style": "bezier",
                    "target-arrow-shape": "triangle",
                    "arrow-scale": 0.9,
                    "width": 1.5,
                    "label": "data(label)",
                    "font-size": "9px",
                    "font-family": "Cascadia Code, Consolas, monospace",
                    "text-rotation": "autorotate",
                    "text-margin-y": -7,
                    "line-color": "#64748b",
                    "target-arrow-color": "#64748b",
                    "color": "#94a3b8"
                }
            },
            {
                selector: "edge[type = 'inherits']",
                style: {
                    "line-color": "#a855f7",
                    "target-arrow-color": "#a855f7",
                    "color": "#c084fc",
                    "width": 2
                }
            },
            {
                selector: "edge[type = 'defines']",
                style: {
                    "line-color": "#475569",
                    "target-arrow-color": "#475569",
                    "color": "#94a3b8"
                }
            },
            {
                selector: "edge[type = 'constructs']",
                style: {
                    "line-color": "#ec4899",
                    "target-arrow-color": "#ec4899",
                    "color": "#f472b6"
                }
            },
            {
                selector: "edge[type = 'calls']",
                style: {
                    "line-color": "#06b6d4",
                    "target-arrow-color": "#06b6d4",
                    "color": "#22d3ee"
                }
            }
        ],
        layout: {
            name: "cose",
            animate: false,
            fit: true,
            padding: 30,
            componentSpacing: 50,
            nodeRepulsion: 450000,
            idealEdgeLength: 70,
            edgeElasticity: 100
        },
        wheelSensitivity: 0.25
    });

    window.cy.on("tap", "node", (evt) => {
        const nodeId = evt.target.id();
        selectSymbol(nodeId, "graph");
    });

    applyFilters();
}

/**
 * Execute analysis against the backend for a given project path (Phase 9 & 11).
 */
async function runAnalysis(projectPath = "sample_project") {
    // If empty or whitespace, default to "sample_project" (Phase 11)
    const rawPath = typeof projectPath === "string" ? projectPath.trim() : "";
    const effectivePath = rawPath || "sample_project";

    window.currentProjectPath = effectivePath;

    // Synchronize input field value if present
    const pathInput = document.getElementById("input-project-path");
    if (pathInput && pathInput.value !== effectivePath) {
        pathInput.value = effectivePath;
    }

    // Reset previous selection state to avoid stale references
    window.selectedSymbolId = null;
    window.currentSymbolDetail = null;
    window.currentSourceView = null;
    const inspectorPlaceholder = document.getElementById("inspector-placeholder");
    const inspectorDetails = document.getElementById("inspector-details");
    if (inspectorPlaceholder) inspectorPlaceholder.style.display = "flex";
    if (inspectorDetails) inspectorDetails.style.display = "none";
    const elInstability = document.getElementById("inspector-instability");
    if (elInstability) elInstability.textContent = "0.00";

    appendLog(`Starting static analysis for "${effectivePath}"...`);
    updateStatusBar({ node_count: 0, edge_count: 0 }, `Analyzing ${effectivePath}...`);

    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project_path: effectivePath })
        });

        if (!response.ok) {
            let detail = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errData = await response.json();
                if (errData && errData.detail) detail = errData.detail;
            } catch (_) {}

            appendLog(`[Error] Analysis failed: ${detail}`);
            updateStatusBar({ node_count: 0, edge_count: 0 }, `Analysis error: ${detail}`);

            // Ensure graph placeholder displays clean error message rather than a stack trace
            const graphPlaceholder = document.getElementById("graph-placeholder");
            if (graphPlaceholder) {
                graphPlaceholder.style.display = "flex";
                const heading = graphPlaceholder.querySelector(".placeholder-heading");
                const subtext = graphPlaceholder.querySelector(".placeholder-subtext");
                if (heading) heading.textContent = "Analysis Failed";
                if (subtext) subtext.textContent = detail;
            }
            if (window.cy) {
                try {
                    window.cy.destroy();
                    window.cy = null;
                } catch (_) {}
            }
            renderTableView([]);
            renderPatternsView([]);
            return null;
        }

        const data = await response.json();
        window.lastGraphData = data;
        window.lastArchitectureData = null;

        // Surface parse errors/warnings as warnings in bottom log panel (Phase 9 & 11)
        if (data.errors && data.errors.length > 0) {
            data.errors.forEach(err => {
                appendLog(`[Warning] ${err.file_path}: ${err.message}`);
            });
            const warnSuffix = ` (${data.errors.length} warning${data.errors.length > 1 ? "s" : ""})`;
            updateStatusBar(data.summary, `Analyzed ${effectivePath}${warnSuffix}`);
        } else {
            updateStatusBar(data.summary, `Analyzed ${effectivePath}`);
        }

        // Render Graph
        renderGraph(data);

        // Populate Left Explorer Tree (Phase 5)
        populateExplorerTree(data);

        // Populate Table View (Phase 12)
        renderTableView(data.nodes);

        // Populate Patterns View (Phase 13)
        loadPatterns();

        appendLog(`Analysis complete: ${data.summary.node_count} nodes, ${data.summary.edge_count} edges.`);

        return data;
    } catch (err) {
        console.error("[CodeStruct] Analysis failed:", err);
        appendLog(`[Error] Analysis failed: ${err.message}`);
        updateStatusBar({ node_count: 0, edge_count: 0 }, "Analysis error");
        return null;
    }
}

/**
 * Update the Qwen Assistant connection status badge (Phase 8).
 * @param {"connected" | "disconnected" | "idle" | "loading"} status
 */
function updateChatConnectionStatus(status) {
    const badge = document.getElementById("chat-status-badge");
    const text = document.getElementById("chat-status-text");
    if (!badge || !text) return;

    badge.className = `chat-status-badge status-${status}`;
    if (status === "connected") {
        text.textContent = "Connected";
        badge.title = "Connected to local Ollama (qwen2.5-coder:3b)";
    } else if (status === "disconnected") {
        text.textContent = "Disconnected";
        badge.title = "Ollama unreachable or error returned";
    } else if (status === "loading") {
        text.textContent = "Thinking...";
        badge.title = "Awaiting response from Ollama...";
    } else {
        text.textContent = "Ready";
        badge.title = "Ollama connection idle";
    }
}

/**
 * Send user message to Qwen Assistant with injected symbol context (Phase 8).
 */
async function sendChatMessage(customText = null) {
    const inputEl = document.getElementById("chat-input");
    const sendBtn = document.getElementById("btn-chat-send");
    const chatContainer = document.getElementById("chat-messages");
    const placeholder = document.getElementById("chat-placeholder");

    const message = customText !== null ? customText.trim() : (inputEl ? inputEl.value.trim() : "");
    if (!message) return;

    if (inputEl) inputEl.value = "";

    // Hide empty placeholder
    if (placeholder) placeholder.style.display = "none";

    // 1. Render User Message Bubble
    const userMsgEl = document.createElement("div");
    userMsgEl.className = "chat-msg chat-msg-user";

    const symbolContextId = window.selectedSymbolId;
    if (symbolContextId) {
        const tag = document.createElement("span");
        tag.className = "chat-context-tag";
        tag.textContent = `[Context: ${symbolContextId}]`;
        userMsgEl.appendChild(tag);
    }

    const userTextSpan = document.createElement("div");
    userTextSpan.textContent = message;
    userMsgEl.appendChild(userTextSpan);
    chatContainer.appendChild(userMsgEl);

    // 2. Render Temporary Assistant Loading Bubble
    const loadingMsgEl = document.createElement("div");
    loadingMsgEl.className = "chat-msg chat-msg-assistant loading";
    loadingMsgEl.textContent = "Thinking...";
    chatContainer.appendChild(loadingMsgEl);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Set UI to loading state
    updateChatConnectionStatus("loading");
    if (inputEl) inputEl.disabled = true;
    if (sendBtn) sendBtn.disabled = true;

    try {
        const chatSelect = document.getElementById("chat-model-select");
        const selectedModelId = chatSelect && chatSelect.value ? chatSelect.value : null;
        const payload = {
            message: message,
            context_symbol_id: symbolContextId || null,
            model_id: selectedModelId
        };

        const res = await fetch("/api/llm/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            throw new Error(`Server returned HTTP ${res.status}`);
        }

        const data = await res.json();
        const reply = data.reply || "";

        // Check for error indicator from qwen_client
        if (reply.startsWith("[Error]")) {
            loadingMsgEl.className = "chat-msg chat-msg-error";
            loadingMsgEl.textContent = reply;
            updateChatConnectionStatus("disconnected");
            appendLog(`[Chat Error] ${reply}`);
        } else {
            loadingMsgEl.className = "chat-msg chat-msg-assistant";
            loadingMsgEl.textContent = reply;
            updateChatConnectionStatus("connected");
            appendLog(`[Chat] Assistant replied for ${symbolContextId || "general"}`);
        }
    } catch (err) {
        console.error("[CodeStruct] Chat error:", err);
        loadingMsgEl.className = "chat-msg chat-msg-error";
        loadingMsgEl.textContent = `[Error] ${err.message}`;
        updateChatConnectionStatus("disconnected");
        appendLog(`[Chat Exception] ${err.message}`);
    } finally {
        if (inputEl) {
            inputEl.disabled = false;
            inputEl.focus();
        }
        if (sendBtn) sendBtn.disabled = false;
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

/**
 * Validate Ollama availability at startup and update the Qwen panel indicator immediately (Phase 9).
 */
async function checkOllamaStartupStatus() {
    try {
        const res = await fetch("/api/qwen/status");
        if (res.ok) {
            const data = await res.json();
            if (data.status === "connected") {
                updateChatConnectionStatus("connected");
                appendLog(`[AI] Ollama service connected (${data.model}).`);
            } else {
                updateChatConnectionStatus("disconnected");
                appendLog("[AI Warning] Ollama is disconnected. Start Ollama ('ollama serve') to enable AI assistance.");
            }
        } else {
            updateChatConnectionStatus("disconnected");
        }
    } catch (err) {
        updateChatConnectionStatus("disconnected");
        appendLog(`[AI Warning] Ollama check failed: ${err.message}`);
    }
}

// --------------------------------------------------------------------------
// Initialization & Event Wiring
// --------------------------------------------------------------------------


/**
 * Initialize 4 dock toggle buttons and rails (Phase 17).
 * - Left Dock (Explorer): #btn-toggle-explorer & #rail-explorer
 * - Inspector Dock: #btn-toggle-inspector & #rail-inspector
 * - Qwen Dock: #btn-toggle-qwen & #rail-qwen
 * - Bottom Log Strip: #btn-toggle-logs & #strip-logs
 * Collapsing preserves all inner state (Qwen chat history, Explorer filters/selection, etc.).
 */
function initDockToggles() {
    const leftDock = document.getElementById("left-dock");
    const rightDock = document.getElementById("right-dock");
    const inspectorPanel = document.getElementById("inspector-panel");
    const qwenPanel = document.getElementById("qwen-panel");
    const logStrip = document.getElementById("log-strip");

    function resizeGraph() {
        if (window.cy) {
            window.cy.resize();
            window.cy.fit(null, 30);
        }
    }

    function updateRightDockRail() {
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
    }

    // 1. Explorer Dock
    const btnToggleExplorer = document.getElementById("btn-toggle-explorer");
    const railExplorer = document.getElementById("rail-explorer");
    if (btnToggleExplorer && leftDock) {
        btnToggleExplorer.addEventListener("click", () => {
            leftDock.classList.toggle("dock-collapsed");
            resizeGraph();
        });
    }
    if (railExplorer && leftDock) {
        railExplorer.addEventListener("click", () => {
            leftDock.classList.remove("dock-collapsed");
            resizeGraph();
        });
    }

    // 2. Inspector Dock
    const btnToggleInspector = document.getElementById("btn-toggle-inspector");
    const railInspector = document.getElementById("rail-inspector");
    if (btnToggleInspector && inspectorPanel) {
        btnToggleInspector.addEventListener("click", () => {
            inspectorPanel.classList.toggle("dock-collapsed");
            updateRightDockRail();
            resizeGraph();
        });
    }
    if (railInspector && inspectorPanel) {
        railInspector.addEventListener("click", () => {
            inspectorPanel.classList.remove("dock-collapsed");
            updateRightDockRail();
            resizeGraph();
        });
    }

    // 3. Qwen Dock
    const btnToggleQwen = document.getElementById("btn-toggle-qwen");
    const railQwen = document.getElementById("rail-qwen");
    if (btnToggleQwen && qwenPanel) {
        btnToggleQwen.addEventListener("click", () => {
            qwenPanel.classList.toggle("dock-collapsed");
            updateRightDockRail();
            resizeGraph();
        });
    }
    if (railQwen && qwenPanel) {
        railQwen.addEventListener("click", () => {
            qwenPanel.classList.remove("dock-collapsed");
            updateRightDockRail();
            resizeGraph();
        });
    }

    // 4. Log Strip
    const btnToggleLogs = document.getElementById("btn-toggle-logs");
    const stripLogs = document.getElementById("strip-logs");
    if (btnToggleLogs && logStrip) {
        btnToggleLogs.addEventListener("click", () => {
            logStrip.classList.toggle("dock-collapsed");
            resizeGraph();
        });
    }
    if (stripLogs && logStrip) {
        stripLogs.addEventListener("click", () => {
            logStrip.classList.remove("dock-collapsed");
            resizeGraph();
        });
    }
}

/**
 * Initialize scrollable toolbar with mouse wheel, click-and-drag, and edge fades (Phase 17).
 */
function initToolbarScroll() {
    const container = document.getElementById("toolbar-scroll-container");
    const fadeLeft = document.getElementById("toolbar-fade-left");
    const fadeRight = document.getElementById("toolbar-fade-right");

    if (!container) return;

    function updateFades() {
        const maxScroll = container.scrollWidth - container.clientWidth;
        if (fadeLeft) fadeLeft.classList.toggle("visible", container.scrollLeft > 4);
        if (fadeRight) fadeRight.classList.toggle("visible", maxScroll > 4 && container.scrollLeft < maxScroll - 4);
    }

    // Wheel horizontal scrolling
    container.addEventListener("wheel", (e) => {
        if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
            e.preventDefault();
            container.scrollLeft += e.deltaY;
            updateFades();
        }
    }, { passive: false });

    // Drag-to-scroll
    let isDown = false;
    let startX = 0;
    let scrollLeft = 0;

    container.addEventListener("mousedown", (e) => {
        if (e.button !== 0) return;
        isDown = true;
        startX = e.pageX - container.offsetLeft;
        scrollLeft = container.scrollLeft;
        container.classList.add("dragging");
    });

    window.addEventListener("mouseup", () => {
        isDown = false;
        container.classList.remove("dragging");
    });

    window.addEventListener("mouseleave", () => {
        isDown = false;
        container.classList.remove("dragging");
    });

    container.addEventListener("mousemove", (e) => {
        if (!isDown) return;
        e.preventDefault();
        const x = e.pageX - container.offsetLeft;
        const walk = (x - startX) * 1.2;
        container.scrollLeft = scrollLeft - walk;
        updateFades();
    });

    container.addEventListener("scroll", updateFades);
    window.addEventListener("resize", updateFades);
    setTimeout(updateFades, 50);

    // Wire top toolbar tabs to switch center tabs
    const tbMap = [
        { id: "toolbar-tab-graph", name: "graph" },
        { id: "toolbar-tab-table", name: "table" },
        { id: "toolbar-tab-patterns", name: "patterns" },
        { id: "toolbar-tab-code", name: "code" },
        { id: "toolbar-tab-architecture", name: "architecture" }
    ];

    tbMap.forEach(item => {
        const btn = document.getElementById(item.id);
        if (btn) {
            btn.addEventListener("click", () => {
                switchCenterTab(item.name);
                if (item.name === "code" && !window.currentSourceView && window.currentSymbolDetail) {
                    jumpToSource(window.currentSymbolDetail);
                }
            });
        }
    });

    const tbBtnOpenEditor = document.getElementById("toolbar-btn-open-editor");
    if (tbBtnOpenEditor) {
        tbBtnOpenEditor.addEventListener("click", () => {
            const targetPath = (window.currentSourceView && window.currentSourceView.file_path)
                || (window.currentSymbolDetail && window.currentSymbolDetail.file_path);
            if (targetPath) {
                openInEditor(targetPath);
            } else {
                appendLog("[Warn] No source file currently open to open in editor.");
            }
        });
    }
}

/**
 * Apply responsive floor behavior (<1024px vs >=1024px) (Phase 17).
 */
function applyResponsiveFloor() {
    const isSmall = window.innerWidth < 1024;
    document.body.classList.toggle("viewport-compact", isSmall);
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("[CodeStruct] Initializing Phase 11 frontend...");

    const pathInput = document.getElementById("input-project-path");
    const btnAnalyze = document.getElementById("btn-analyze");

    const handleAnalyze = () => {
        const val = pathInput ? pathInput.value.trim() : "";
        runAnalysis(val || "sample_project");
    };

    // Analyze Button (Phase 11: uses entered path or defaults to sample_project)
    if (btnAnalyze) {
        btnAnalyze.addEventListener("click", handleAnalyze);
    }

    // Enter key inside Project Path input
    if (pathInput) {
        pathInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                handleAnalyze();
            }
        });
    }

    // Open Project Button (focuses path input and prompts if desired)
    const btnArchRetry = document.getElementById("btn-architecture-retry");
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

    const btnOpenProject = document.getElementById("btn-open-project");
    if (btnOpenProject) {
        btnOpenProject.addEventListener("click", () => {
            const currentVal = pathInput ? pathInput.value.trim() : (window.currentProjectPath || "sample_project");
            const input = prompt("Enter project directory path:", currentVal);
            if (input !== null && input.trim()) {
                if (pathInput) pathInput.value = input.trim();
                runAnalysis(input.trim());
            } else if (pathInput) {
                pathInput.focus();
                pathInput.select();
            }
        });
    }

    // Check URL search params for initial project (Phase 11)
    const urlParams = new URLSearchParams(window.location.search);
    const initialProjectParam = urlParams.get("project");
    if (initialProjectParam && initialProjectParam.trim()) {
        if (pathInput) pathInput.value = initialProjectParam.trim();
        window.currentProjectPath = initialProjectParam.trim();
    }

    // Explorer Filter Input
    const filterInput = document.getElementById("explorer-filter");
    if (filterInput) {
        filterInput.addEventListener("input", (e) => {
            filterExplorerTree(e.target.value);
        });
    }

    // Center tabs switched via top toolbar (Phase 17 Follow-Up)

    // Open in Editor Buttons (Phase 12)
    const btnOpenEditorInspector = document.getElementById("btn-open-editor-inspector");
    if (btnOpenEditorInspector) {
        btnOpenEditorInspector.addEventListener("click", () => {
            if (window.currentSymbolDetail && window.currentSymbolDetail.file_path) {
                openInEditor(window.currentSymbolDetail.file_path);
            } else {
                appendLog("[Warn] Select a symbol first to open in editor.");
            }
        });
    }

    // Code editor button handled via top toolbar (toolbar-btn-open-editor)

    // Table Header Sorting (Phase 12)
    document.querySelectorAll("#symbols-table th.sortable").forEach(th => {
        th.addEventListener("click", () => {
            const col = th.dataset.col;
            if (!col) return;
            if (window.tableSortColumn === col) {
                window.tableSortAscending = !window.tableSortAscending;
            } else {
                window.tableSortColumn = col;
                window.tableSortAscending = true;
            }
            renderTableView(window.lastGraphData ? window.lastGraphData.nodes : []);
        });
    });

    // Jump to Source Button (Phase 7)
    const btnJump = document.getElementById("btn-jump-source");
    if (btnJump) {
        btnJump.addEventListener("click", () => {
            if (window.currentSymbolDetail) {
                jumpToSource(window.currentSymbolDetail);
            } else {
                appendLog("[Warn] Select a symbol first to jump to source.");
            }
        });
    }

    // Graph Pan / Zoom / Fit Controls
    const btnFit = document.getElementById("btn-fit");
    if (btnFit) {
        btnFit.addEventListener("click", () => {
            if (window.cy) window.cy.fit(null, 30);
        });
    }

    const btnZoomIn = document.getElementById("btn-zoom-in");
    if (btnZoomIn) {
        btnZoomIn.addEventListener("click", () => {
            if (window.cy) {
                const currentZoom = window.cy.zoom();
                window.cy.zoom({
                    level: currentZoom * 1.3,
                    renderedPosition: { x: window.cy.width() / 2, y: window.cy.height() / 2 }
                });
            }
        });
    }

    const btnZoomOut = document.getElementById("btn-zoom-out");
    if (btnZoomOut) {
        btnZoomOut.addEventListener("click", () => {
            if (window.cy) {
                const currentZoom = window.cy.zoom();
                window.cy.zoom({
                    level: currentZoom * 0.77,
                    renderedPosition: { x: window.cy.width() / 2, y: window.cy.height() / 2 }
                });
            }
        });
    }

    const btnResetLayout = document.getElementById("btn-reset-layout");
    if (btnResetLayout) {
        btnResetLayout.addEventListener("click", () => {
            if (window.cy) {
                window.cy.layout({
                    name: "cose",
                    animate: true,
                    animationDuration: 300,
                    fit: true,
                    padding: 30
                }).run();
            }
        });
    }

    // Kind Filter Checkboxes (module, class, function, method)
    ["module", "class", "function", "method"].forEach(kind => {
        const checkbox = document.getElementById(`filter-${kind}`);
        if (checkbox) {
            checkbox.addEventListener("change", () => {
                applyFilters();
            });
        }
    });

    // Window Resize listener
    window.addEventListener("resize", () => {
        if (window.cy) window.cy.resize();
    });

    // Qwen Assistant Chat Wiring (Phase 8)
    const btnSend = document.getElementById("btn-chat-send");
    if (btnSend) {
        btnSend.addEventListener("click", () => {
            sendChatMessage();
        });
    }

    const chatInput = document.getElementById("chat-input");
    if (chatInput) {
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }

    // Check Ollama startup status immediately (Phase 9)
    checkOllamaStartupStatus();

    // Initialize Phase 17 UI/UX Overhaul features
    initDockToggles();
    initToolbarScroll();
    applyResponsiveFloor();
    window.addEventListener("resize", applyResponsiveFloor);

    // Initialize Multi-LLM Model Manager & Settings UI
    initModelManager();

    // Initialize First-Run Setup Wizard
    initSetupWizard();

    console.log("[CodeStruct] Phase 9 frontend initialized.");
});

// ==========================================================================
// First-Run Setup Wizard Controller (Windows Packaging & Onboarding)
// ==========================================================================
let wizardPollTimer = null;

async function initSetupWizard() {
    const btnOpen = document.getElementById("btn-open-wizard");
    const btnClose = document.getElementById("btn-wizard-close");
    const btnRecheck = document.getElementById("btn-wizard-recheck");
    const btnBrowse = document.getElementById("btn-wizard-browse");
    const btnInstallOllama = document.getElementById("btn-wizard-install-ollama");
    const btnPullModel = document.getElementById("btn-wizard-pull-model");
    const btnSkipAi = document.getElementById("btn-wizard-skip-ai");
    const btnFinish = document.getElementById("btn-wizard-finish");
    const inputModelsDir = document.getElementById("wizard-models-dir");

    if (btnOpen) {
        btnOpen.addEventListener("click", () => openSetupWizard());
    }
    if (btnClose) {
        btnClose.addEventListener("click", () => closeSetupWizard());
    }
    if (btnRecheck) {
        btnRecheck.addEventListener("click", () => {
            const customDir = inputModelsDir ? inputModelsDir.value.trim() : "";
            refreshWizardChecks(customDir || null);
        });
    }
    if (btnBrowse) {
        btnBrowse.addEventListener("click", async () => {
            try {
                const res = await fetch("/api/wizard/browse_folder", { method: "POST" });
                const data = await res.json();
                if (data.selected && inputModelsDir) {
                    inputModelsDir.value = data.selected;
                    refreshWizardChecks(data.selected);
                } else if (!data.supported) {
                    appendLog("[Wizard] Native folder dialog not supported in browser mode; type path directly.");
                }
            } catch (e) {
                console.warn("[Wizard] Folder browse error:", e);
            }
        });
    }
    if (inputModelsDir) {
        inputModelsDir.addEventListener("change", () => {
            refreshWizardChecks(inputModelsDir.value.trim() || null);
        });
    }
    if (btnInstallOllama) {
        btnInstallOllama.addEventListener("click", () => triggerInstallOllama());
    }
    if (btnPullModel) {
        btnPullModel.addEventListener("click", () => triggerPullModel());
    }
    // Toggle Ollama vs Cloud panels inside Setup Wizard
    const modeRadios = document.querySelectorAll('input[name="wizard-ai-mode"]');
    const ollamaSubpanel = document.getElementById("wizard-ollama-panel");
    const cloudSubpanel = document.getElementById("wizard-cloud-panel");
    modeRadios.forEach(radio => {
        radio.addEventListener("change", () => {
            const isCloud = radio.value === "cloud" && radio.checked;
            if (ollamaSubpanel) ollamaSubpanel.style.display = isCloud ? "none" : "flex";
            if (cloudSubpanel) cloudSubpanel.style.display = isCloud ? "flex" : "none";
        });
    });

    const wizardCloudProvider = document.getElementById("wizard-cloud-provider");
    const wizardCloudModel = document.getElementById("wizard-cloud-model");
    const wizardCloudUrlRow = document.getElementById("wizard-cloud-url-row");
    if (wizardCloudProvider) {
        wizardCloudProvider.addEventListener("change", () => {
            const pval = wizardCloudProvider.value;
            if (wizardCloudUrlRow) {
                wizardCloudUrlRow.style.display = (pval === "azure" || pval === "custom") ? "flex" : "none";
            }
            if (wizardCloudModel) {
                if (pval === "openai") wizardCloudModel.value = "gpt-4o-mini";
                else if (pval === "anthropic") wizardCloudModel.value = "claude-3-5-sonnet-20241022";
                else if (pval === "gemini") wizardCloudModel.value = "gemini-1.5-flash";
                else if (pval === "azure") wizardCloudModel.value = "gpt-4o";
                else wizardCloudModel.value = "local-model";
            }
        });
    }

    if (btnSkipAi) {
        btnSkipAi.addEventListener("click", () => completeSetupWizard(false));
    }
    if (btnFinish) {
        btnFinish.addEventListener("click", () => completeSetupWizard(true));
    }

    // Auto-open on first run if not yet completed
    try {
        const res = await fetch("/api/wizard/status");
        if (res.ok) {
            const data = await res.json();
            if (data.config && !data.config.first_run_completed) {
                renderWizardStatus(data);
                openSetupWizard(false);
            }
        }
    } catch (e) {
        console.warn("[Wizard] Initial status check failed:", e);
    }
}

function openSetupWizard(shouldRefresh = true) {
    const overlay = document.getElementById("setup-wizard-overlay");
    if (overlay) {
        overlay.style.display = "flex";
    }
    if (shouldRefresh) {
        const inputModelsDir = document.getElementById("wizard-models-dir");
        const customDir = inputModelsDir ? inputModelsDir.value.trim() : "";
        refreshWizardChecks(customDir || null);
    }
}

function closeSetupWizard() {
    const overlay = document.getElementById("setup-wizard-overlay");
    if (overlay) {
        overlay.style.display = "none";
    }
    if (wizardPollTimer) {
        clearInterval(wizardPollTimer);
        wizardPollTimer = null;
    }
}

async function refreshWizardChecks(customModelsDir = null) {
    try {
        const q = customModelsDir ? "?models_dir=" + encodeURIComponent(customModelsDir) : "";
        const res = await fetch("/api/wizard/status" + q);
        if (!res.ok) return;
        const data = await res.json();
        renderWizardStatus(data);
    } catch (e) {
        console.error("[Wizard] Refresh checks failed:", e);
    }
}

function renderWizardStatus(data) {
    if (!data) return;
    const cfg = data.config || {};
    const chk = data.system_checks || {};

    const grid = document.getElementById("wizard-checks-grid");
    const cfgEl = document.getElementById("wizard-path-config");
    const cacheEl = document.getElementById("wizard-path-cache");
    const inputModelsDir = document.getElementById("wizard-models-dir");
    const diskNote = document.getElementById("wizard-models-disk-note");
    const btnInstall = document.getElementById("btn-wizard-install-ollama");

    if (cfgEl) cfgEl.textContent = chk.config_path || "%APPDATA%\CodeStruct\config.json";
    if (cacheEl) cacheEl.textContent = chk.cache_dir || "%LOCALAPPDATA%\CodeStruct\cache";
    if (inputModelsDir && !inputModelsDir.value) {
        inputModelsDir.value = chk.models_dir || cfg.ollama_models_dir || "";
    }

    if (diskNote) {
        const freeGb = chk.disk_models_free_gb || 0;
        diskNote.textContent = chk.disk_ok_ai
            ? "Target drive has " + freeGb + " GB free (>= 2.5 GB required for model)."
            : "Warning: Target drive only has " + freeGb + " GB free (< 2.5 GB recommended for qwen2.5-coder:3b).";
        diskNote.style.color = chk.disk_ok_ai ? "#34d399" : "#fbbf24";
    }

    if (btnInstall) {
        btnInstall.textContent = chk.ollama_installed
            ? "✓ Ollama Installed"
            : "⬇️ Install Ollama Runtime";
    }

    if (!grid) return;
    const items = [
        { label: "OS: " + (chk.os || "Unknown"), badge: "OK", cls: "ok" },
        { label: "WebView2 GUI Runtime", badge: chk.webview2_installed ? (chk.webview2_version || "Ready") : "Missing", cls: chk.webview2_installed ? "ok" : "warn" },
        { label: "Memory: " + (chk.ram_total_gb || "?") + " GB Total (" + (chk.ram_available_gb || "?") + " GB Free)", badge: chk.ram_ok_ai ? "AI Ready" : (chk.ram_ok_static ? "Static Only" : "Low RAM"), cls: chk.ram_ok_ai ? "ok" : "warn" },
        { label: "Disk (%LOCALAPPDATA%): " + (chk.disk_cache_free_gb || "?") + " GB Free", badge: (chk.disk_cache_free_gb || 0) >= 0.5 ? "OK" : "Low Disk", cls: (chk.disk_cache_free_gb || 0) >= 0.5 ? "ok" : "warn" },
        { label: "Ollama CLI / Daemon", badge: chk.ollama_running ? "Running" : (chk.ollama_installed ? "Installed (Stopped)" : "Not Installed"), cls: chk.ollama_running ? "ok" : (chk.ollama_installed ? "info" : "warn") },
        { label: "Model (" + (chk.target_model || "qwen2.5-coder:3b") + ")", badge: chk.model_pulled ? "Pulled & Ready" : "Not Pulled", cls: chk.model_pulled ? "ok" : "warn" },
    ];

    grid.innerHTML = items.map(it =>
        `<div class="wizard-check-item"><span class="wizard-check-label">${escapeHtml(it.label)}</span><span class="wizard-check-badge ${it.cls}">${escapeHtml(it.badge)}</span></div>`
    ).join("");
}

async function triggerInstallOllama() {
    showWizardTaskBox("Starting Ollama installation...");
    try {
        const res = await fetch("/api/wizard/ollama/install", { method: "POST" });
        const data = await res.json();
        if (data.started) {
            startWizardTaskPolling();
        } else {
            showWizardTaskBox(data.message || "Could not start installer.");
        }
    } catch (e) {
        showWizardTaskBox("Error: " + e.message);
    }
}

async function triggerPullModel() {
    const inputModelsDir = document.getElementById("wizard-models-dir");
    const modelsDir = (inputModelsDir ? inputModelsDir.value.trim() : "") || "";
    if (!modelsDir) {
        showWizardTaskBox("Please specify a Custom Model Storage Directory first.");
        return;
    }

    showWizardTaskBox("Starting model download into " + modelsDir + "...");
    try {
        const res = await fetch("/api/wizard/ollama/pull", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ models_dir: modelsDir, model_name: "qwen2.5-coder:3b" }),
        });
        const data = await res.json();
        if (data.started) {
            startWizardTaskPolling();
        } else {
            showWizardTaskBox(data.message || "Could not start model pull.");
        }
    } catch (e) {
        showWizardTaskBox("Error: " + e.message);
    }
}

function showWizardTaskBox(statusText, logs = []) {
    const box = document.getElementById("wizard-task-box");
    const statusEl = document.getElementById("wizard-task-status");
    const logEl = document.getElementById("wizard-task-log");
    if (box) box.style.display = "flex";
    if (statusEl) statusEl.textContent = statusText;
    if (logEl && logs.length > 0) {
        logEl.textContent = logs.join("\n");
        logEl.scrollTop = logEl.scrollHeight;
    }
}

function startWizardTaskPolling() {
    if (wizardPollTimer) clearInterval(wizardPollTimer);
    wizardPollTimer = setInterval(async () => {
        try {
            const res = await fetch("/api/wizard/ollama/task_status");
            if (!res.ok) return;
            const state = await res.json();
            showWizardTaskBox(state.status.toUpperCase() + ": " + state.message, state.logs || []);
            if (state.status === "completed" || state.status === "error") {
                clearInterval(wizardPollTimer);
                wizardPollTimer = null;
                const inputModelsDir = document.getElementById("wizard-models-dir");
                refreshWizardChecks(inputModelsDir ? inputModelsDir.value.trim() : null);
                checkOllamaStartupStatus();
            }
        } catch (e) {
            console.warn("[Wizard] Poll error:", e);
        }
    }, 1000);
}

async function completeSetupWizard(aiEnabled) {
    const inputModelsDir = document.getElementById("wizard-models-dir");
    const modelsDir = inputModelsDir ? inputModelsDir.value.trim() : null;

    if (aiEnabled) {
        const selectedModeEl = document.querySelector('input[name="wizard-ai-mode"]:checked');
        const mode = selectedModeEl ? selectedModeEl.value : "ollama";
        if (mode === "cloud") {
            const cProvider = document.getElementById("wizard-cloud-provider")?.value || "openai";
            const cModel = document.getElementById("wizard-cloud-model")?.value.trim() || "gpt-4o-mini";
            const cKey = document.getElementById("wizard-cloud-key")?.value.trim() || "";
            const cUrl = document.getElementById("wizard-cloud-url")?.value.trim() || null;

            if (cKey || cProvider === "custom") {
                try {
                    await fetch("/api/models", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            provider: cProvider,
                            display_name: `${cProvider.toUpperCase()} (${cModel})`,
                            model_name: cModel,
                            api_key: cKey || null,
                            base_url: cUrl,
                            enabled: true,
                            is_default_chat: true,
                            is_default_architecture: true,
                        }),
                    });
                    const keyInput = document.getElementById("wizard-cloud-key");
                    if (keyInput) keyInput.value = "";
                    appendLog(`[Setup] Saved ${cProvider} cloud model (${cModel}) encrypted to %APPDATA%\\CodeStruct\\models.json.`);
                } catch (err) {
                    appendLog("[Error] Failed to save cloud model: " + err.message);
                }
            }
        }
    }

    try {
        const res = await fetch("/api/wizard/complete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ai_enabled: aiEnabled,
                ollama_models_dir: modelsDir,
                ollama_model: "qwen2.5-coder:3b",
            }),
        });
        if (res.ok) {
            appendLog("[Setup] Configuration saved to %APPDATA%\CodeStruct\config.json (AI Enabled: " + aiEnabled + ").");
            if (window.ModelManager) await window.ModelManager.loadModels();
            checkOllamaStartupStatus();
            closeSetupWizard();
        }
    } catch (e) {
        appendLog("[Error] Failed to save wizard configuration: " + e.message);
    }
}

// ==========================================================================
// Multi-LLM Provider Settings & Model Selectors (ModelManager)
// ==========================================================================
const ModelManager = {
    models: [],

    async loadModels() {
        try {
            const res = await fetch("/api/models");
            if (!res.ok) return [];
            const data = await res.json();
            this.models = data.models || [];
            this.renderModelSelectors();
            this.renderModelsList();
            return this.models;
        } catch (e) {
            console.warn("[ModelManager] Failed to load models:", e);
            return [];
        }
    },

    renderModelSelectors() {
        const enabledModels = this.models.filter(m => m.enabled);
        const chatSel = document.getElementById("chat-model-select");
        const archSel = document.getElementById("architecture-model-select");

        const populate = (selectEl, defaultFlag) => {
            if (!selectEl) return;
            const prevVal = selectEl.value;
            if (enabledModels.length === 0) {
                selectEl.innerHTML = `<option value="">No model configured</option>`;
                return;
            }
            selectEl.innerHTML = enabledModels.map(m =>
                `<option value="${escapeHtml(m.id)}">${escapeHtml(m.display_name)} [${escapeHtml(m.provider)}]</option>`
            ).join("");

            const defaultModel = enabledModels.find(m => m[defaultFlag]);
            if (prevVal && enabledModels.some(m => m.id === prevVal)) {
                selectEl.value = prevVal;
            } else if (defaultModel) {
                selectEl.value = defaultModel.id;
            }
        };

        populate(chatSel, "is_default_chat");
        populate(archSel, "is_default_architecture");
    },

    renderModelsList() {
        const container = document.getElementById("models-list-container");
        if (!container) return;

        if (!this.models || this.models.length === 0) {
            container.innerHTML = `<div class="wizard-field-hint">No models configured. Click "+ Add Model" to configure one.</div>`;
            return;
        }

        container.innerHTML = "";
        this.models.forEach(m => {
            const card = document.createElement("div");
            card.className = "model-card";
            card.dataset.id = m.id;

            const keyDisplay = m.provider === "ollama"
                ? "Local (No API Key)"
                : (m.has_key ? `Key: ${escapeHtml(m.masked_key)}` : "No API Key Set");

            const defaultBadges = [];
            if (m.is_default_chat) defaultBadges.push(`<span class="model-default-pill">Default Chat</span>`);
            if (m.is_default_architecture) defaultBadges.push(`<span class="model-default-pill">Default Architecture</span>`);

            card.innerHTML = `
                <div class="model-card-top">
                    <div class="model-card-title">
                        <span class="provider-badge provider-${escapeHtml(m.provider)}">${escapeHtml(m.provider)}</span>
                        <span class="model-display-name">${escapeHtml(m.display_name)}</span>
                        <span class="model-id-sub">(${escapeHtml(m.model_name)})</span>
                        ${defaultBadges.join("")}
                    </div>
                    <div class="model-card-actions">
                        <button class="wizard-mini-btn btn-validate-model" type="button">Test Connection</button>
                        <button class="wizard-mini-btn btn-default-chat" type="button" title="Set as default for AI Chat">Set Chat</button>
                        <button class="wizard-mini-btn btn-default-arch" type="button" title="Set as default for Architecture">Set Arch</button>
                        <button class="wizard-mini-btn btn-edit-model" type="button">Edit</button>
                        <button class="wizard-mini-btn btn-delete-model" type="button" style="color: #f87171;">Delete</button>
                    </div>
                </div>
                <div class="model-card-meta">
                    <span>${keyDisplay} ${m.base_url ? ` &bull; ${escapeHtml(m.base_url)}` : ""}</span>
                    <span>Status: ${m.enabled ? "Enabled" : "Disabled"}</span>
                </div>
                <div class="model-validation-msg" style="display: none;"></div>
            `;

            const msgEl = card.querySelector(".model-validation-msg");
            card.querySelector(".btn-validate-model").addEventListener("click", async () => {
                if (msgEl) {
                    msgEl.style.display = "block";
                    msgEl.className = "model-validation-msg";
                    msgEl.textContent = "Testing connection...";
                }
                const result = await this.validateModel(m.id);
                if (msgEl) {
                    if (result.valid) {
                        const count = (result.models || []).length;
                        msgEl.className = "model-validation-msg ok";
                        msgEl.textContent = `✓ Connected successfully (${count} model${count === 1 ? "" : "s"} reachable).`;
                    } else {
                        msgEl.className = "model-validation-msg err";
                        msgEl.textContent = `✗ Validation failed: ${result.error || "Connection error"}`;
                    }
                }
            });

            card.querySelector(".btn-default-chat").addEventListener("click", () => this.setDefault(m.id, "chat"));
            card.querySelector(".btn-default-arch").addEventListener("click", () => this.setDefault(m.id, "architecture"));
            card.querySelector(".btn-edit-model").addEventListener("click", () => this.openForm(m));
            card.querySelector(".btn-delete-model").addEventListener("click", () => this.deleteModel(m.id));

            container.appendChild(card);
        });
    },

    openForm(existing = null) {
        const section = document.getElementById("model-form-section");
        const heading = document.getElementById("model-form-heading");
        const idInput = document.getElementById("model-form-id");
        const providerSel = document.getElementById("model-form-provider");
        const displayInput = document.getElementById("model-form-display-name");
        const nameInput = document.getElementById("model-form-name");
        const keyInput = document.getElementById("model-form-api-key");
        const keyHint = document.getElementById("model-form-key-hint");
        const urlInput = document.getElementById("model-form-base-url");
        const depInput = document.getElementById("model-form-deployment");
        const verInput = document.getElementById("model-form-api-version");
        const enCheck = document.getElementById("model-form-enabled");
        const chatCheck = document.getElementById("model-form-default-chat");
        const archCheck = document.getElementById("model-form-default-arch");
        const statusEl = document.getElementById("model-form-status");

        if (statusEl) statusEl.textContent = "";
        if (keyInput) keyInput.value = "";

        if (existing) {
            if (heading) heading.textContent = `Edit Model: ${existing.display_name}`;
            if (idInput) idInput.value = existing.id;
            if (providerSel) providerSel.value = existing.provider;
            if (displayInput) displayInput.value = existing.display_name;
            if (nameInput) nameInput.value = existing.model_name;
            if (keyHint) keyHint.textContent = existing.has_key ? `(Stored: ${existing.masked_key} — leave blank to keep)` : "";
            if (urlInput) urlInput.value = existing.base_url || "";
            if (depInput) depInput.value = existing.deployment_name || "";
            if (verInput) verInput.value = existing.api_version || "";
            if (enCheck) enCheck.checked = existing.enabled;
            if (chatCheck) chatCheck.checked = existing.is_default_chat;
            if (archCheck) archCheck.checked = existing.is_default_architecture;
        } else {
            if (heading) heading.textContent = "Add New Model Provider";
            if (idInput) idInput.value = "";
            if (providerSel) providerSel.value = "openai";
            if (displayInput) displayInput.value = "OpenAI GPT-4o Mini";
            if (nameInput) nameInput.value = "gpt-4o-mini";
            if (keyHint) keyHint.textContent = "";
            if (urlInput) urlInput.value = "";
            if (depInput) depInput.value = "";
            if (verInput) verInput.value = "2024-06-01";
            if (enCheck) enCheck.checked = true;
            if (chatCheck) chatCheck.checked = false;
            if (archCheck) archCheck.checked = false;
        }

        this.updateDynamicFormFields();
        if (section) section.style.display = "flex";
    },

    updateDynamicFormFields() {
        const provider = document.getElementById("model-form-provider")?.value || "openai";
        const keyField = document.getElementById("field-api-key");
        const depField = document.getElementById("field-deployment-name");
        const verField = document.getElementById("field-api-version");
        const urlField = document.getElementById("field-base-url");

        if (keyField) keyField.style.display = provider === "ollama" ? "none" : "flex";
        if (depField) depField.style.display = provider === "azure" ? "flex" : "none";
        if (verField) verField.style.display = provider === "azure" ? "flex" : "none";
        if (urlField) urlField.style.display = provider === "gemini" ? "none" : "flex";
    },

    async saveModel() {
        const idVal = document.getElementById("model-form-id")?.value.trim() || null;
        const provider = document.getElementById("model-form-provider")?.value || "openai";
        const displayName = document.getElementById("model-form-display-name")?.value.trim() || "";
        const modelName = document.getElementById("model-form-name")?.value.trim() || "";
        const apiKey = document.getElementById("model-form-api-key")?.value.trim() || null;
        const baseUrl = document.getElementById("model-form-base-url")?.value.trim() || null;
        const deploymentName = document.getElementById("model-form-deployment")?.value.trim() || null;
        const apiVersion = document.getElementById("model-form-api-version")?.value.trim() || null;
        const enabled = document.getElementById("model-form-enabled")?.checked ?? true;
        const defChat = document.getElementById("model-form-default-chat")?.checked ?? false;
        const defArch = document.getElementById("model-form-default-arch")?.checked ?? false;
        const statusEl = document.getElementById("model-form-status");

        if (!modelName) {
            if (statusEl) statusEl.textContent = "Model Name is required.";
            return;
        }

        try {
            const res = await fetch("/api/models", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id: idVal,
                    provider: provider,
                    display_name: displayName || modelName,
                    model_name: modelName,
                    api_key: apiKey,
                    base_url: baseUrl,
                    deployment_name: deploymentName,
                    api_version: apiVersion,
                    enabled: enabled,
                    is_default_chat: defChat,
                    is_default_architecture: defArch,
                }),
            });
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const saved = await res.json();
            const keyInput = document.getElementById("model-form-api-key");
            if (keyInput) keyInput.value = "";
            document.getElementById("model-form-section").style.display = "none";
            appendLog(`[Models] Saved encrypted config for ${saved.display_name} (${saved.provider}).`);
            await this.loadModels();
            checkOllamaStartupStatus();
        } catch (e) {
            if (statusEl) statusEl.textContent = `Save failed: ${e.message}`;
        }
    },

    async deleteModel(modelId) {
        try {
            const res = await fetch(`/api/models/${encodeURIComponent(modelId)}`, { method: "DELETE" });
            if (res.ok) {
                appendLog(`[Models] Deleted model configuration: ${modelId}`);
                await this.loadModels();
                checkOllamaStartupStatus();
            }
        } catch (e) {
            appendLog(`[Error] Delete model failed: ${e.message}`);
        }
    },

    async validateModel(modelId) {
        try {
            const res = await fetch(`/api/models/${encodeURIComponent(modelId)}/validate`, { method: "POST" });
            if (!res.ok) {
                return { valid: false, models: [], error: `HTTP ${res.status}` };
            }
            return await res.json();
        } catch (e) {
            return { valid: false, models: [], error: e.message };
        }
    },

    async setDefault(modelId, target) {
        try {
            const res = await fetch(`/api/models/${encodeURIComponent(modelId)}/set-default`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ target }),
            });
            if (res.ok) {
                await this.loadModels();
                checkOllamaStartupStatus();
            }
        } catch (e) {
            appendLog(`[Error] Failed to set default model: ${e.message}`);
        }
    }
};

function initModelManager() {
    const overlay = document.getElementById("models-settings-overlay");
    const btnOpen = document.getElementById("btn-open-models");
    const btnClose = document.getElementById("btn-models-close");
    const btnNew = document.getElementById("btn-models-new");
    const btnCancel = document.getElementById("btn-model-form-cancel");
    const btnSave = document.getElementById("btn-model-form-save");
    const providerSel = document.getElementById("model-form-provider");
    const archSelect = document.getElementById("architecture-model-select");

    if (btnOpen && overlay) {
        btnOpen.addEventListener("click", async () => {
            overlay.style.display = "flex";
            await ModelManager.loadModels();
        });
    }
    if (btnClose && overlay) {
        btnClose.addEventListener("click", () => {
            overlay.style.display = "none";
        });
    }
    if (btnNew) {
        btnNew.addEventListener("click", () => ModelManager.openForm(null));
    }
    if (btnCancel) {
        btnCancel.addEventListener("click", () => {
            const sec = document.getElementById("model-form-section");
            if (sec) sec.style.display = "none";
        });
    }
    if (btnSave) {
        btnSave.addEventListener("click", () => ModelManager.saveModel());
    }
    if (providerSel) {
        providerSel.addEventListener("change", () => {
            ModelManager.updateDynamicFormFields();
            const pval = providerSel.value;
            const nameIn = document.getElementById("model-form-name");
            const dispIn = document.getElementById("model-form-display-name");
            const idVal = document.getElementById("model-form-id")?.value;
            if (!idVal && nameIn && dispIn) {
                if (pval === "openai") { nameIn.value = "gpt-4o-mini"; dispIn.value = "OpenAI GPT-4o Mini"; }
                else if (pval === "anthropic") { nameIn.value = "claude-3-5-sonnet-20241022"; dispIn.value = "Claude 3.5 Sonnet"; }
                else if (pval === "gemini") { nameIn.value = "gemini-1.5-flash"; dispIn.value = "Gemini 1.5 Flash"; }
                else if (pval === "azure") { nameIn.value = "gpt-4o"; dispIn.value = "Azure OpenAI GPT-4o"; }
                else if (pval === "custom") { nameIn.value = "local-model"; dispIn.value = "Custom OpenAI-Compat"; }
                else if (pval === "ollama") { nameIn.value = "qwen2.5-coder:3b"; dispIn.value = "Ollama (qwen2.5-coder:3b)"; }
            }
        });
    }
    if (archSelect) {
        archSelect.addEventListener("change", () => {
            if (window.activeCenterTab === "architecture" && window.lastGraphData) {
                window.lastArchitectureData = null;
                loadArchitecture(true);
            }
        });
    }

    // Load models initially to populate Chat & Architecture dropdown selectors
    ModelManager.loadModels();
}

window.ModelManager = ModelManager;

// Export helpers for programmatic access
window.runAnalysis = runAnalysis;
window.applyFilters = applyFilters;
window.selectSymbol = selectSymbol;
window.filterExplorerTree = filterExplorerTree;
window.populateExplorerTree = populateExplorerTree;
window.loadSymbolDetail = loadSymbolDetail;
window.switchCenterTab = switchCenterTab;
window.jumpToSource = jumpToSource;
window.sendChatMessage = sendChatMessage;
window.updateChatConnectionStatus = updateChatConnectionStatus;
window.checkOllamaStartupStatus = checkOllamaStartupStatus;
window.openInEditor = openInEditor;
window.renderTableView = renderTableView;
window.loadPatterns = loadPatterns;
window.renderPatternsView = renderPatternsView;
window.loadSymbolImpact = loadSymbolImpact;
window.initDockToggles = initDockToggles;
window.initToolbarScroll = initToolbarScroll;
window.applyResponsiveFloor = applyResponsiveFloor;
