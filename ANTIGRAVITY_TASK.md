# Antigravity Task: Integrate the Stitch Workbench as a Thonny Editor Tab

Date: 2026-10-16
Repository: `D:\REP\Codestruct\Codestruct`
Owner: Antigravity implements and verifies; Codex maintains this bounded handoff and reviews the resulting report.

## Authoritative requirement

This task supersedes earlier instructions in this file and older reports that describe a standalone Edge/Chrome application window, an external browser tab, or a separate folder picker. The user has clarified the required workflow:

1. The user opens CodeStruct from Thonny's **Tools** menu.
2. The Stitch workbench opens as a **new editor tab inside Thonny's main window**, like opening a new file in VS Code. It must not open a separate top-level application window or browser.
3. The project root is the folder currently open in Thonny's **File** view when CodeStruct is invoked. Do not substitute the active source file's parent, a folder chooser, a configured demo root, or fixture data.
4. The provided Stitch screen is the visual source of truth. Use the available Stitch MCP connection to inspect and implement the actual design.

The latest Codex review is `docs/verification/STITCH_FRONTEND_INTEGRATION_CODEX_REVIEW_1.md`. The prior report, `docs/verification/STITCH_FRONTEND_INTEGRATION_REVIEW_1.md`, documents a separate Edge standalone window; its UI and quality-gate results do not satisfy the Thonny-host requirement. M7 remains **Changes required** and unaccepted. Do not begin M8 or CS-020–024.

## Read and verify before changing code

- Read `D:\REP\# CodeStruct – Technology Summary.txt` first; it is the primary product and technology source.
- Read `docs/codestruct_audit.md`, `PROCESS_TRACKER.md`, this task, the latest Codex review, and the prior Stitch integration report.
- Inspect the actual Stitch project/screen through MCP. The prior handoff identified Stitch project `projects/3997374805666523009`, screen `94361047d60944b0ab44bfb463329efb` (“Thonny IDE - Docked CodeStruct Architecture Workbench”). Confirm the current screen and record its identity, layout, typography, color, assets, and interactions from MCP rather than relying only on screenshots or the old report.
- Confirm the repository root, branch, HEAD, and `git status --short`. Preserve all existing user/Codex changes. Do not reset, rebase, overwrite unrelated files, or stage unrelated work.
- Inspect the active renderer and launch path from current configuration before deciding which frontend source to use. Reuse the existing live frontend and API wherever possible; do not create a second demo renderer.
- Inspect the installed Thonny version and supported plugin APIs for adding an editor tab and obtaining the folder currently shown by Thonny's File view. Record the API/source evidence and test the host integration in real Thonny.

## Phase 1 — establish the real Thonny host integration

Implement a Thonny **Tools** command for the CodeStruct workbench. Invoking it must open or focus a CodeStruct workbench tab in Thonny's existing editor notebook. The visible workbench must be hosted within the Thonny main window and follow normal editor-tab behavior, including selecting and closing the tab. Use a supported Thonny extension point and a compatible embedded renderer; do not simulate integration with a menu entry that launches Edge, Chrome, `--app`, a separate Tk top-level, or another standalone window.

At command invocation, read the current project directory from Thonny's File view and pass that directory through the existing trusted plugin/host path to the backend. Clearly display the project root in the workbench. If Thonny has no usable folder open, show a clear in-IDE message explaining that the user must open the project folder in Thonny's File view; do not silently fall back to another root or launch a folder chooser. If the user changes the File view folder and invokes CodeStruct again, the displayed/analyzed project must correspond to that current folder, with no stale project state.

Before building out the full screen, prove in the real installed Thonny that the Tools command opens the tab in the same main window and can load the active File view folder. Add plugin tests for command registration, editor-tab lifecycle, root selection, missing-folder behavior, and switching folders. Do not declare success from mocked-only UI tests.

If a supported embedded editor-tab approach requires a dependency or host change, choose the smallest maintainable option compatible with Thonny and document it. Continue investigating and implementing within scope. If the current Thonny host genuinely cannot support the required integrated tab, do not substitute a separate window; document the exact API/host evidence and the remaining blocker for the owner.

## Phase 2 — connect the Stitch workbench to live CodeStruct behavior

Adapt the active frontend to the Stitch design while keeping it inside the Thonny editor tab. Match the target's main layout, typography, spacing, colors, hierarchy, and interactions as closely as the existing stack permits. Reuse existing backend routes and capability boundaries; document and test any necessary contract change.

The workbench must preserve the user's functional requirements:

- Show the current Thonny File view folder as the project root and load that whole project using real backend data.
- Present architecture from folders/files through modules, classes, functions, and methods in clear top-to-bottom hierarchical order. Keep nodes and labels readable; provide useful pan, zoom, fit, and expand/collapse behavior.
- Keep a navigable project/file explorer with Python modules, classes, functions, and methods nested under their files, and an independently closable left drawer.
- Keep an independently closable right inspector showing the selected node's name, source-location pointer, project-relative path, relationships, and evidence-grounded architectural explanation. Related-node navigation must select the corresponding live node.
- Keep **Refresh** for the currently open project. Remove the separate **Analyze** action, theme toggle, project-source selector, demo-root/demo-data controls, and standalone **Open Folder** action.
- Use only real API results. Preserve graph IDs, locations, relationship status/confidence, pagination, diagnostics, cancellation, loading/error/partial states, and existing navigation back to Thonny source files. Never fabricate success or fall back to fixtures after an API failure.
- Keep static analysis non-executing. Opening, refreshing, and navigating a project must never run its source code. Preserve canonical-root containment, traversal/reparse/symlink protections, loopback restrictions, and capability-token secrecy.
- Do not duplicate Thonny's outer application chrome as fake controls. Stitch defines the workbench content; Thonny owns its native menu bar and editor tabs. Every control rendered inside the workbench must have a real behavior or be clearly disabled/labeled.

Keep the existing React Flow decision unless measured evidence shows it cannot meet the design and hierarchy requirements. Do not replace a graph library merely to match a technology-summary name.

## Phase 3 — real workflow, regression gates, and safe cleanup

Use a disposable nested project with distinctive files/symbols and run the actual Thonny application with the installed CodeStruct plugin. Through the visible Thonny UI:

1. Open the fixture folder in Thonny's File view.
2. Select **Tools → CodeStruct** and verify a new editor tab opens in Thonny's existing main window, without an external browser or separate app window.
3. Verify the displayed project root equals the File view folder and that the live explorer, architecture hierarchy, selection, inspector fields, relationship navigation, both drawer controls, Refresh, and editor navigation work.
4. Change Thonny's File view to a second fixture and invoke the Tools command again; prove CodeStruct uses the second folder and cannot display stale data from the first.
5. Verify missing-folder handling, tab close/reopen and process shutdown. Confirm analysis and refresh do not execute fixture code.

Capture screenshots showing the actual Thonny window, editor tab, File view folder, and live workbench. Compare the embedded workbench with the MCP Stitch target at a recorded viewport and report material differences. Verify window ownership/parenting so screenshots cannot be mistaken for a standalone window.

Run all configured frontend lint, typecheck, tests, and production build; the full backend pytest suite and coverage threshold; Ruff, Mypy, Python compilation, and all affected Thonny plugin tests. Run focused tests during development and rerun the complete applicable gates after the last code change. Record exact commands, exit codes, counts, and summaries. If a check fails, diagnose and fix it, then rerun the relevant gates; do not stop at a partial pass.

After the integrated Thonny tab is working, inventory old standalone launchers, host code, and assets. Search code, tests, packaging, shortcuts, scripts, and documentation before deleting anything. Remove only files proven unused by the final Thonny flow; preserve the active frontend, backend, user data, test fixtures, and useful reports. Record every removed path and its reference checks. Commit each completed implementation/cleanup phase separately; do not push and do not include unrelated user changes.

## Report and tracker requirements

Write `docs/verification/THONNY_STITCH_EDITOR_TAB_INTEGRATION.md` with:

- Confirmed Stitch MCP project/screen identity and concise design-to-workbench mapping.
- The Thonny version, plugin/editor-tab integration approach, File view root-discovery method, and evidence that the tab is inside Thonny's existing main window.
- Tested implementation commit(s), report commit(s), changed files, and any safe cleanup inventory.
- Screenshots and the actual user-visible workflow results, including the two-folder switch test and non-execution evidence.
- Exact quality-gate commands/results, failures and fixes, untested cases, remaining limitations, final `git status --short`, and `git diff --check` result.
- Any blocker stated plainly. Do not claim integration based on an Edge/Chrome window, a mock, API-only test, or a report from the earlier standalone implementation.

Update `PROCESS_TRACKER.md` and `docs/codestruct_audit.md` to reflect verified results only. Keep M7 unaccepted until Codex review, and keep M8 not started. Synchronize the designated external audit mirror if the existing workflow permits, and record exact path/hash parity or the blocker. Commit each finished phase with scoped files; never push.

Continue implementation, testing, and safe cleanup until all requirements above pass or a genuine host/API blocker is evidenced and reported. Then share the report and mark the task ready for review. Do not begin M8 or any work outside this scope.

## Launch prompt

> <span style="color:green">Read ANTIGRAVITY_TASK.md and implement the Stitch workbench as a real Thonny editor tab, launched from Tools and rooted in the folder currently open in Thonny's File view. Do not use an Edge/Chrome or standalone window or a separate folder picker. Keep working through implementation, actual Thonny/backend/frontend verification, and safe cleanup until every requirement passes; update PROCESS_TRACKER.md and the audit, commit each completed phase, record full evidence in docs/verification/THONNY_STITCH_EDITOR_TAB_INTEGRATION.md, then send READY FOR REVIEW. Do not begin Milestone 8, do not mark anything Accepted, and do not push.</span>
