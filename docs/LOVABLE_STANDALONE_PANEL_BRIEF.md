# Lovable Brief: CodeStruct Standalone Project Explorer

Create the visual workbench for CodeStruct's Windows-only standalone desktop window. The user opens a **whole project folder** with a native folder picker. The application should feel like a focused IDE tool window, not a website in a browser tab. Use the existing Lovable frontend as the visual starting point and keep real backend data and API contracts.

## Visual direction

- Match the typography, spacing, controls, and restrained colors of a modern IDE such as the user's Antigravity/VS Code setup. Use one consistent IDE-aligned theme; there is no theme toggle.
- Keep a compact title/toolbar, a left project explorer drawer, a central architecture canvas, and a right inspector drawer. Both drawers have visible open/close controls and collapse cleanly without covering the canvas.
- Make the hierarchy and labels readable at normal Windows display scaling. Do not shrink nodes to fit a dense graph. Prefer collapse/expand, pan/zoom, and a fit-to-view action. Design for 1366x768 and larger desktop windows.
- Use React Flow, the current renderer in the active frontend, unless measured requirements show it cannot support the requested hierarchy. Do not rewrite the graph renderer just to match a technology-summary recommendation.

## Project opening and toolbar

- Provide **Open Folder**. The desktop host will implement the native Windows folder dialog through a bridge such as `window.codeStructHost.chooseProjectFolder()`. Do not use a browser file input or ask the user to select one Python file.
- Selecting a folder opens that complete root in the workbench and begins its initial analysis automatically. Show progress, errors, and partial results honestly.
- Provide **Refresh** to reanalyze the currently open folder and refresh its tree. Keep the selected root visible in the window title or breadcrumb.
- Do not show an Analyze action, project-source selector/dropdown, demo-root option, demo data, or dark/light theme control.
- Never substitute fabricated graph data when a live API call fails.

## Left project explorer drawer

- Show the complete folder structure of the currently opened root, with folders and files nested like an IDE file explorer. Support expansion/collapse, scrolling, and symbol search.
- Under every Python file, nest its module, classes, functions, and methods. Place methods under their owning class. Keep non-Python files visible in the filesystem tree without inventing Python symbols for them.
- Selecting a folder, file, module, class, function, or method should synchronize the selection with the central architecture view where a graph node exists.
- The tree is backed by the selected real project and parser results. Do not hard-code a sample project.

## Central architecture canvas

- Default to a clear top-to-bottom hierarchy: project/folder, file, module, class, then function/method. Keep parent-child order stable and easy to follow.
- Show architectural relationships as clear, secondary connections that do not destroy the hierarchy. Use existing relationship kinds and evidence; do not fabricate edges.
- Support pan, zoom, fit-to-view, selection, and expand/collapse for large projects. Avoid overlapping objects and preserve readable node dimensions and text.
- The visible canvas selection and left tree selection stay synchronized. The loaded/total state must be clear for paginated graphs.
- If DOT export is exposed, state clearly whether it exports the loaded slice or the complete graph.

## Right inspector drawer

For a selected graph node, show:

- Name and kind.
- Source pointer in `relative/path.py:line:column` form, plus the full project-relative path.
- Relationships, with clickable related nodes that focus the graph and tree.
- Architectural explanation from the existing backend explanation service, clearly separating observed evidence from interpretation. Show a useful empty state when no explanation is available.
- Preserve the existing Thonny/editor navigation action when a valid source location and editor session are available.

The inspector can open and close independently of the project explorer. With no selection, show a useful prompt rather than fabricated details.

## Data and integration rules

- Use the existing CodeStruct API and canonical graph/node/edge fields. Preserve IDs, source locations, relationship status/confidence, pagination, cancellation, and diagnostic states.
- The desktop host owns folder selection. The renderer must call the host bridge, then use the authorized project/root returned by the backend. Do not send arbitrary filesystem paths to an unauthenticated endpoint.
- The backend is responsible for safe root containment and a complete, navigable folder/symbol tree. Tree navigation may load children lazily for large folders, but every entry inside the selected root must remain reachable; visibly explain any policy exclusions.
- Keep keyboard navigation and meaningful accessible labels for both drawers, the tree, graph controls, and inspector.

## Acceptance checks

- A user can open a whole folder, see its directory tree, and expand a Python file into its module/class/function/method hierarchy.
- Refresh updates the same project without requiring a separate Analyze action.
- The graph reads top to bottom and remains legible at normal window sizes; selection opens correct source, relationships, and explanation in the inspector.
- No demo root, demo data, source selector, Analyze button, or theme toggle appears.
- The UI works inside the standalone Windows window through the host bridge and real API; it does not depend on a browser tab or a hard-coded path.
