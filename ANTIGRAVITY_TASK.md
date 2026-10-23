# Antigravity Task: Integrate the Stitch Workbench as a Thonny Editor Tab

> **Current follow-up (2026-10-23):** In addition to the Correction 2 requirements and report, `D:\REP\changes\3.png` shows a real Thonny failure: “Could not register project folder with CodeStruct backend: timed out.” The active scope is Correction 3 in `ANTIGRAVITY_THONNY_LAYOUT_TASK.md`. Diagnose and fix the registration timeout, recheck the Correction 2 user-visible requirements, update the new verification report/tracker/audit, then stop for Codex review. M7 remains Changes required; do not mark M7 or M8 Accepted.

> <span style="color:green">Read `ANTIGRAVITY_THONNY_LAYOUT_TASK.md`, `docs/verification/THONNY_WORKBENCH_LAYOUT_CORRECTION_2.md`, and inspect `D:\REP\changes\3.png`. Complete only Current correction follow-up 3: diagnose and fix the real Thonny error “Could not register project folder with CodeStruct backend: timed out,” then regression-check the persistent single Explorer, clean Inspector, interactive graph, clear relationship arrows, native Thonny Shell, project switching, and static-only/security requirements from Correction 2. Verify in real Thonny using the affected Python 3.14.6 workflow; do not merely increase a timeout without establishing the cause. Write `docs/verification/THONNY_WORKBENCH_LAYOUT_CORRECTION_3.md` with root cause, fix, real workflow/screenshots, regression and quality-gate evidence, limitations, and commit/push details; update `PROCESS_TRACKER.md` and `docs/codestruct_audit.md`; safely clean only proven-unused files; commit scoped changes and push only to existing `origin/main` without force. Continue correcting and testing until all requirements pass or a genuine blocker is documented. Then stop all implementation, make no further changes or begin other work, send `READY FOR REVIEW`, and wait for Codex review. Do not mark M7/M8 Accepted or publish packages/releases.</span>

> **Current handoff (2026-10-21):** M7 has been accepted on the report-based review recorded in `docs/verification/M7_CODEX_REVIEW_2_ACCEPTED_REPORT_BASED.md`. The next authorized task is M8 (CS-020–024), specified in `ANTIGRAVITY_M8_TASK.md`. That file supersedes the historical M7 instructions below. M8 is not started until Antigravity begins.

> **Latest user instruction (2026-10-21):** Complete M8 owner-default finalization and push the scoped changes to the existing Git remote under `ANTIGRAVITY_M8_FINALIZATION_TASK.md`. This supersedes the earlier no-push restriction for this specific authorized Git sync only. Do not publish packages or change repository visibility.

> <span style="color:green">Read ANTIGRAVITY_M8_FINALIZATION_TASK.md and complete the authorized M8 closeout. Apply the approved MIT/license, maintainer-handle, and Git-only distribution defaults; keep human Narrator observation explicitly pending and provide the owner checklist. Reconcile the M8 report/tracker/audit, rerun the applicable full gates and clean-package lifecycle, commit scoped changes, then push only to the existing remote/current branch without force or visibility changes. Do not publish packages, create tags/releases, mark M8 Accepted, or begin work beyond M8. Record commits and push evidence, send READY FOR REVIEW, and stop.</span>

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

## Current correction follow-up — user reports unresolved workspace behavior (2026-10-20)

Antigravity's 2026-10-19 report says the Stitch workbench opens as a Thonny editor tab and analyzes the File view folder. The user has now reported that the result still does not meet the requirement. Treat that report and its green checks as prior claims, not acceptance. Reproduce and correct the actual user-visible workflow; do not stop at the earlier automated runner passing.

The required behavior is:

1. Starting from a normal Thonny editing session with one or more source files open, **Tools → CodeStruct** switches the same Thonny main window to a new, visible CodeStruct editor tab. The tab behaves like another document in Thonny's editor notebook: the user can switch back to the already-open source tabs and back to CodeStruct. No separate window, browser, or hidden/detached workbench is acceptable.
2. The CodeStruct tab analyzes and displays the **whole project folder currently open in Thonny's File view**, recursively, subject only to documented safe exclusions. It must not use the active editor file or a selected file as the analysis scope. It must show multiple nested files and each Python file's module/classes/functions/methods in the project tree and architecture view, with clear exclusion diagnostics where applicable.
3. Open a realistic multi-file fixture in Thonny's File view, invoke CodeStruct from Tools, and prove that files in separate nested directories appear in the live explorer and graph. Then open a different project folder in the File view and invoke CodeStruct again; prove the new project replaces the prior project without stale single-file or prior-root data. If the File view is pointed at a file, determine the containing folder view/root from Thonny's actual API; never analyze only that file.
4. If the current implementation reads `current_focus` or another File view field that can resolve to a single file or selection instead of the directory being browsed, fix root discovery using the correct supported Thonny API. If Thonny's current state has no open project directory, show a clear in-IDE explanation and do not fall back to the active file, demo root, fixture, or a separate folder picker.

Use real Thonny UI interaction to reproduce the user's workflow. An API smoke, mocked plugin test, standalone renderer, or automated script alone cannot prove the editor-tab and whole-folder experience. Inspect why the previous evidence diverged from the user's result, fix the cause, and rerun the complete applicable gates after the final code change. Preserve the Stitch design and all prior security/non-execution requirements while correcting behavior.

Write the corrective evidence to `docs/verification/THONNY_STITCH_EDITOR_TAB_CORRECTION_1.md`, preserving the prior report. Include a concrete before/failure reproduction, the cause, the corrected real Thonny workflow, screenshots of the same Thonny window with source and CodeStruct tabs, evidence from a nested multi-file project, project-switch evidence, exact commands/results, failures/fixes, untested cases, and final Git/whitespace status. Update `PROCESS_TRACKER.md` and the audit to **Changes required** while work remains, then to Ready for Codex review only when every behavior above is demonstrated. Keep M8 unstarted. Continue until the requirements pass or a genuine blocker is evidenced and reported; do not commit/push unrelated user changes.

## Current launch prompt

> <span style="color:green">Read ANTIGRAVITY_TASK.md and complete the Current correction follow-up. The user reports that the prior result still does not behave as required: CodeStruct must open as a switchable editor tab in Thonny's existing main window, and it must analyze/display the whole folder currently open in Thonny's File view, not a single active/selected file. Reproduce the real Thonny workflow with a nested multi-file project, find and fix the mismatch, verify switching to a second project, and keep running the real UI and applicable quality gates until all requirements pass. Preserve the Stitch design and security/non-execution rules, update PROCESS_TRACKER.md and the audit, record evidence in docs/verification/THONNY_STITCH_EDITOR_TAB_CORRECTION_1.md, then send READY FOR REVIEW. Do not begin Milestone 8, do not mark anything Accepted, and do not push.</span>

## Current follow-up — remove the duplicate standalone window (2026-10-20)

The user confirms that the Thonny-hosted CodeStruct editor tab works, but starting the prototype still opens a second, standalone CodeStruct window. Read-only launch-path tracing identifies the cause in `prototype-launcher/Start-CodeStruct-Prototype.ps1`: section 8 ("Standalone Windows Desktop Application Window") starts `msedge.exe` with `--app=$frontendUrl` (around lines 473–497), then section 9 separately launches Thonny. The separate Edge window is obsolete and must be removed from the prototype startup flow.

### Required correction

- Remove the Edge `--app` UI launch from `Start-CodeStruct-Prototype.ps1`, including obsolete PID/start-time state, runtime app profile, status output, and rollback handling that exists only for that window.
- Update `Stop-CodeStruct-Prototype.ps1` so it safely stops only launcher-owned backend/frontend services and does not expect or terminate a standalone CodeStruct app window. Leave Thonny open and preserve its embedded WebView2 children as part of the IDE.
- Keep the loopback backend and frontend/Vite service if the embedded Thonny tab needs them. Do not remove the renderer or server just because the standalone Edge host is removed.
- Search and update launcher tests, prototype config, README, reports, and shortcut/startup guidance so they no longer promise or trigger a separate browser/application window or browser-based analysis flow. Remove `appWindow`/`app_profile` state only after reference checks prove it is no longer needed.
- The prototype start shortcut must result in the Thonny IDE as the only user-facing application window. The user then opens **Tools → CodeStruct** and sees the architecture tab inside Thonny. Do not auto-open another window, browser tab, or duplicate CodeStruct UI on startup.
- Verify on Windows by starting through the actual prototype `.cmd`/shortcut, recording visible top-level windows and process command lines, and confirming there is no Edge `--app` CodeStruct window. Do not reject legitimate WebView2 renderer/helper processes that are children of Thonny; the acceptance condition is no separate visible CodeStruct window. Then exercise the embedded workbench in Thonny and confirm backend/frontend connectivity remains healthy.
- Exercise stop and restart: stopping services must not close Thonny; restarting must still produce no second window. Run the launcher test suite, plugin tests, and all other affected quality gates, fixing regressions and rerunning applicable full gates until clean.
- Write `docs/verification/THONNY_SINGLE_WINDOW_LAUNCH_CORRECTION_1.md` with the root cause, changed files, actual shortcut/startup workflow, window/process evidence, embedded tab smoke, stop/restart results, exact gates and outcomes, cleanup/reference inventory, failed attempts, limitations, and final `git status --short` / `git diff --check`.
- Keep M7 **Changes required** until the duplicate-window workflow is fixed and evidenced. Update `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and the designated external audit mirror/hash record. Commit scoped fixes; do not push or begin M8.

Continue implementation and verification until the actual prototype startup opens only Thonny and the embedded CodeStruct tab remains usable, or a genuine blocker is documented. Preserve unrelated working-tree changes, including any in-progress frontend work.

## Current launch prompt

> <span style="color:green">Read ANTIGRAVITY_TASK.md and complete the Current follow-up to remove the duplicate standalone window. The cause is the legacy Edge `--app` launch in `prototype-launcher/Start-CodeStruct-Prototype.ps1` before Thonny starts. Remove that user-facing window launch and its obsolete state/stop/test/docs wiring while keeping backend and frontend services needed by the embedded Thonny tab. Verify the real prototype shortcut opens only Thonny, Tools → CodeStruct still works inside Thonny, and stop/restart leaves Thonny safe. Keep running the actual Windows workflow and affected quality gates until the requirements pass; write docs/verification/THONNY_SINGLE_WINDOW_LAUNCH_CORRECTION_1.md, update PROCESS_TRACKER.md and the audit, commit scoped changes, then send READY FOR REVIEW. Do not begin Milestone 8, do not mark anything Accepted, and do not push.</span>
