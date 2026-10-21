# CodeStruct user guide

## Select and analyze a project

An administrator configures authorized aliases. Wait for **Configured project**,
choose an available display name, and press **Analyze project**. The browser never
needs or displays the server root path. If no project appears, see
[configuration](configuration.md).

CodeStruct announces validation, queueing, scanning, parsing, resolution, graph
construction, and bounded graph retrieval. **Cancel** requests cancellation; wait
for Cancelled because completion can win a race. **Refresh analysis** bypasses a
compatible cached result; an ordinary repeat may show Cached result.

## Explore and interpret results

- Pan, zoom, fit, or reset; search names, qualified names, relative paths, or kinds.
- Filters narrow entity kind, relationship kind, resolution, classification, and diagnostics.
- **Entity Details Panel:** Redesigned responsive panel providing an independently scrollable visual hierarchy:
  - **Overview:** Entity name, kind badge with non-color symbols, qualified name with one-click copy, project path with copy, and parent link with jump and graph-center actions.
  - **Relationships:** Segmented into Incoming and Outgoing dependencies with direction indicators, kind badges, resolution status (`[✓ Resolved]`, `[? Unresolved]`, `[~ Ambiguous]`, `[○ Syntactic only]`), loaded endpoint links with centering, and clear `[Unloaded/External]` tags for entities outside the current loaded slice.
  - **Evidence & Resolution:** When inspecting relationships, displays a Source → Target hero, static confidence level, static reason, evidence origin, and source code span with one-click copy.
  - **Diagnostics:** Inline list of diagnostics associated with the selected element with severity badges, codes, messages, and source locations.
  - **Keyboard & Accessibility:** Full `Escape` key panel dismissal, focus management, and screen-reader announcements via polite `aria-live` regions.
- **Table** is the keyboard/screen-reader-oriented text alternative.
- A partial-load message gives returned/total counts. **Load more graph data** gets the next deterministic page; search, filters, and Table cover loaded data only.

**Resolved/exact** means supported static evidence identified one target.
**Ambiguous** means multiple targets remain. **Unresolved** means no exact target
was found, not that runtime execution fails. **External** is outside this graph.
**Partially completed** source analysis differs from a **partially loaded** graph.
**Cached** means a validated compatible stored result was reused.

## Analyze projects and files from Thonny IDE

CodeStruct integrates natively into the Thonny Python IDE:

1. Launch CodeStruct through the Windows prototype script (`Start-CodeStruct-Prototype.cmd` or `prototype-launcher/Start-CodeStruct-Prototype.ps1`). This launches Thonny as the single application window with local backend and frontend services running on loopback.
2. In Thonny's **File view**, navigate to and open your Python project folder.
3. Select **Tools → CodeStruct** (or press the configured shortcut).
4. CodeStruct registers the active folder with the backend, performs whole-folder static analysis across all Python source files recursively, and opens the architecture workbench directly inside Thonny as an embedded editor tab (`CodeStructEditorTab`).
5. When switching folders in Thonny's File view, selecting **Tools → CodeStruct** reuses and updates the existing tab without tab duplication.
6. Selecting any architectural node and clicking **Open in editor** navigates back to Thonny, opening the source file at the exact line of code.

### Configured project roots vs. temporary editor capabilities

- **Configured Project Roots (`CODESTRUCT_AUTHORIZED_ROOTS`):** Persistent directory trees authorized globally in backend configuration. When analyzing a configured project, CodeStruct scans and analyzes all matching files throughout that directory tree.
- **Temporary Host Capabilities (`cap_*`):** Short-lived tokens generated through `POST /api/v1/host/register-folder` or `POST /api/v1/editor/selection`.
  - **Folder Scope:** A valid host registration capability authorizes the directory currently active in Thonny's File view.
  - **Access Outside Configured Roots:** Safely analyzes projects located on the local filesystem without requiring manual edits to global server configuration.
  - **Per-Job Policy Isolation:** Sibling folders outside the target directory are never scanned, parsed, or included.
  - **No Global Leakage:** Target directories are bound to the session lifecycle and never pollute global persistent configuration.


## Open an existing analysis by URL

You can open a previously created analysis directly in the browser by appending the `analysis_id` query parameter:

```text
http://localhost:5173/?analysis_id=<analysis-id>
```

- **Ongoing Analyses:** If the analysis is currently in progress (`queued`, `scanning`, `parsing`, `resolving`, etc.), the viewer automatically polls until terminal completion and then renders the architecture graph and diagnostics.
- **Partial Analyses:** If the analysis finished with partial results (`partially_completed`), the viewer displays the retained graph elements alongside all reported diagnostics.
- **Terminal Failures:** If the analysis failed (`failed`) or was cancelled (`cancelled`), the viewer presents the terminal status message without requesting nonexistent graph assets.
- **Provenance & Refresh Limitations:** When an analysis is loaded via URL, its local project provenance (`root_id` and `relative_path`) is not known to the browser session. Consequently, the **Refresh analysis** button is disabled with the notice: *"Select a project and choose Analyze project to run a new analysis."* To trigger a new analysis or forced cache refresh, select an authorized project from the dropdown and click **Analyze project**.
- **Service Assumptions:** Both the CodeStruct backend API (e.g. `http://localhost:8000`) and the web frontend (e.g. `http://localhost:5173`) must be running.

Unknown/unauthorized selection requires a configuration correction; a missing
project must be restored or reconfigured. Backend unavailable means start or
reconnect the API. Expired results must be analyzed again. For dense graphs use
filters, overview, or Table. Operators should use
[troubleshooting](development/troubleshooting.md).

