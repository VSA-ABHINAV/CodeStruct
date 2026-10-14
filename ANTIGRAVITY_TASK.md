# Antigravity Task: M7 Corrections and Standalone Windows Project Explorer

Date: 2026-10-13
Repository: `D:\REP\Codestruct\Codestruct`
Task owner: Antigravity. Codex authored the review and task brief; do not treat this task as permission for Codex to implement the application changes.

## Goal

Resolve the findings in `docs/verification/M7_CODEX_REVIEW_1.md`, then deliver the user-requested Windows-only standalone CodeStruct workbench that opens a whole project folder. Use `docs/LOVABLE_STANDALONE_PANEL_BRIEF.md` for the visual requirements. Work through the phases below, commit each completed phase separately, keep running tests and fixing regressions until the requirements are met, then create the reports and stop for Codex review. Do not begin M8.

This scope is the M7 correction pass plus the standalone project-explorer/frontend-integration work requested by the user. It does **not** include CS-020–024 evaluation/release work or deferred CS-025 features.

## Read first and verify the checkout

Read these current sources before changing code:

- `docs/verification/M7_CODEX_REVIEW_1.md` — current Codex findings and required regressions.
- `docs/codestruct_audit.md` and `PROCESS_TRACKER.md` — stable issue IDs and current statuses.
- `D:\REP\# CodeStruct – Technology Summary.txt` — primary product and technology direction.
- `frontend.lovable/INTEGRATION_HANDOFF.md` and `prototype-launcher/prototype-config.json` — active frontend and launcher wiring.
- The relevant source, tests, and launcher files for each finding.

Verify the actual Git root, branch, HEAD, remotes, and working tree before editing. The expected checkout is the existing repository on `main`; the review was performed at `590a208`, with tested M7 code at `921f930`. Do not reset, rebase, discard, or overwrite user files. The current working tree is expected to contain Codex-authored changes to `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, `docs/verification/M7_CODEX_REVIEW_1.md`, this task file, and `docs/LOVABLE_STANDALONE_PANEL_BRIEF.md`. Preserve them and inspect every other modification before staging.

## Phase 1 — Correct M7 findings R1 and R2

### R1: enforce Graphviz output bounds while output is produced

In `backend/src/codestruct/graph/export_dot.py`, replace the post-`communicate()` output-size check with enforcement that bounds stdout and stderr as they are consumed. Terminate the renderer and descendants promptly when a stream exceeds its cap. Bound or safely discard diagnostics on stderr. Enforce an output bound on DOT serialization as well; node/edge counts alone do not bound label sizes. Preserve timeout behavior, format validation, safe errors, API status mapping, and Windows process-tree cleanup.

Add regressions for a renderer that emits well beyond the configured stdout cap, a renderer that floods stderr, and an oversized DOT label/serialization. Tests must prove the limit is enforced, the child is terminated, and callers receive the documented output-limit failure without buffering the full output. Cover the relevant API error response too.

### R2: enforce the persistent cache byte limit

In `backend/src/codestruct/storage/file_cache.py`, make eviction continue until the cache fits both the entry-count and byte budgets after the incoming entry, or skip caching an entry that cannot fit by itself. Preserve LRU behavior, transactions, and concurrency safety.

Add tests for byte-only pressure, simultaneous count and byte pressure, and one entry larger than the configured byte budget. Assert both `entries <= max_entries` and `total_bytes <= max_bytes` after insertion. The review's direct failing example is ten existing 10-byte entries under a 100-byte budget followed by an 80-byte entry; the resulting stored total must not exceed 100 bytes.

Do not weaken existing analysis or cache-key invariants. Keep the complete-result cache and per-file cache behavior intact.

## Phase 2 — Windows standalone window and whole-folder workflow

Create a top-level Windows desktop application window for the visualization. It must open as an application window and must not send the user to a Chrome/Edge browser tab. Inspect the existing Python/FastAPI/Vite stack and choose the smallest reliable Windows host that fits it; document the choice and any required runtime. Do not add a large framework or package installer without evidence it is necessary. Keep backend and window process startup/shutdown under the existing launcher lifecycle, with no orphan processes.

The user selected these product decisions:

- **Windows-only standalone app window.**
- **Open a whole folder/project**, not an individual Python file.
- Use only the new standalone panel in the application.
- Visual frontend creation belongs to Lovable; Antigravity owns the native shell, backend/API, and integration work. Use the provided Lovable brief. Do not author a substitute visual design, contact external services, or access a Lovable account. The user will provide the Lovable-generated UI in the active frontend source for integration. Do not invent or substitute demo UI/data.

Provide a native **Open Folder** action that opens a Windows folder chooser. The selected directory becomes the current project root and starts the initial analysis automatically. Do not use a browser file input. Add or adapt a host-to-renderer bridge and backend flow safely: a browser-originated unauthenticated request must not be able to register arbitrary filesystem paths. Preserve canonical-root containment, traversal and reparse/symlink protections, local capability boundaries, and static-analysis non-execution. Do not make source code run as part of opening or refreshing a project.

The project explorer must represent the complete selected folder tree. Add a safe backend/API contract for directory and symbol data if the existing graph API does not provide it. Every in-root entry must remain navigable, using lazy expansion or pagination for large projects. Under Python files, show the module, classes, functions, and methods in source order; nest methods under their classes. Keep ignored/generated directories safe and explain exclusions rather than silently claiming a complete tree when an entry was skipped.

## Phase 3 — Integrate the Lovable workbench requirements

Use `docs/LOVABLE_STANDALONE_PANEL_BRIEF.md` as the UI acceptance source. The user will create the visual screen in Lovable; do not author a replacement visual design in React/CSS or access Lovable externally. Complete the shell, APIs, security, and test work that does not depend on the new export. When the Lovable-generated files are available in the active frontend, wire the host bridge and real data into them and verify the full workbench. Until then, preserve the current frontend and report the exact external handoff needed rather than claiming the visual phase passed. Preserve the existing React Flow decision unless a measured requirement proves it cannot support the top-down hierarchy; the audit explicitly says not to rewrite a graph library solely to match a technology-summary name.

The workbench must:

- Present a readable, IDE-like single-theme interface. Remove the theme toggle; do not add dark/light mode switching.
- Open a whole folder through the native host. Remove the project-source selector and demo-root/demo-data options.
- Remove the separate Analyze action. Opening a folder starts analysis; a visible **Refresh** action reanalyzes the currently open project.
- Show the architecture in a clear top-to-bottom hierarchy from folder/file to module, class, function, and final method. Keep object dimensions and labels readable; use expand/collapse, pan/zoom, and fit-to-view instead of shrinking the graph until labels are unreadable. Show real relationships without obscuring the parent-child hierarchy.
- Provide an independently collapsible left drawer with the full folder/file tree and nested Python symbols. Selecting an item synchronizes the tree and graph.
- Provide an independently collapsible right inspector with the selected node's name, source-location pointer, project-relative path, relationships, and architectural explanation. Related nodes should be navigable. Explanations must use the existing evidence-backed service and distinguish evidence from interpretation.
- Preserve real graph IDs, location data, relationship status/confidence, pagination, cancellation, diagnostics, error states, and existing Thonny/editor navigation where available. Never substitute fixtures after a live API failure.
- Make DOT export labels explicit about loaded-slice versus complete-graph behavior; satisfy R3 from the review in the active standalone UI.

Do not redesign unrelated product areas or change API contracts without documenting and testing the compatibility impact.

## Frontend folder cleanup

The user explicitly requested removal of frontend files that will not be used by the standalone panel. Perform cleanup only after the replacement is integrated and verified:

1. Inventory frontend directories, entrypoints, build outputs, tests, package manifests/lockfiles, launcher paths, backend bundling, CI, scripts, and documentation references with `rg` and direct inspection.
2. Identify the actual source needed to build and launch the standalone renderer. Keep `frontend.lovable/` if it remains the active Lovable source. Do not infer that `frontend/` or any subfolder is safe to delete merely because the prototype launcher does not point to it; migrate or remove its tests/build references deliberately.
3. Delete only exact, proven-unused frontend source folders/files after the new app builds and launches from its retained source. Do not remove historical verification reports, user data, databases, logs, screenshots, lockfiles with live dependency provenance, backend assets, or Thonny files.
4. Record each removed path and the reference/build/package checks that justified its removal. Verify the final working tree and repository tree; leave no task-created temporary databases or build artifacts unless they are required outputs.

Codex's review attempt created `D:\REP\_codestruct_m7_review.sqlite3` and `D:\REP\_codex_m7_review_tmp_20261013`. Verify these exact paths and that no process is using them; remove them as task-created review artifacts if accessible. Do not broaden cleanup to other files in `D:\REP`.

## Required verification

Keep fixing and rerunning until the applicable gates pass. Record exact commands, exit codes, counts, and evidence; distinguish automated tests from real desktop and visual checks.

- M7: focused cache/export regressions; full backend pytest and configured coverage threshold; Ruff check/format; Mypy; Python compilation; M7 verification runner updated for the corrected behavior.
- Frontend: active renderer typecheck, unit tests, lint, and production build. Ensure tests exercise tree hierarchy, selected node details, refresh, and partial/complete export labels.
- Thonny: existing plugin suite and any affected real editor-navigation workflow. Do not claim Thonny integration if not exercised.
- Real Windows workflow: start the project through its supported shortcut/launcher; observe a separate CodeStruct app window with no browser tab; choose a whole fixture/project folder with the native dialog; inspect a nested Python file, class, function, and method; refresh; select a node and verify its source pointer, relationships, and explanation; verify the left and right drawers open/close; stop the app and confirm task-owned processes/ports are gone.
- Security: verify invalid roots, traversal, symlink/reparse escape, and unauthenticated root registration are rejected; confirm analysis remains static and does not execute source files.
- Run `git diff --check` on the complete phase diffs and the final tree. Remove the known trailing whitespace in `docs/verification/M6_REPORT_ACCEPTED.md:3` only if that exact line remains and include the cleanup in a scoped documentation commit.
- Use isolated test databases and temporary directories under a writable, task-owned location. Never point tests at the prototype user's persistent database.

If a test or runtime flow fails, diagnose and fix it; do not stop after the first test run. If an external dependency blocks the Lovable export or the actual Windows runtime, complete all independent work, preserve the current usable app, record the exact blocker and evidence, and do not claim the standalone visual workflow is complete.

## Phase commits, tracker, audit, and reports

- Commit each completed implementation phase separately, with scoped files and clear messages. The repository already exists: do not create a nested repository, reset history, or push to a remote.
- Do not stage unrelated user files. Keep the Codex-authored review and brief changes intact.
- Update `PROCESS_TRACKER.md` and `docs/codestruct_audit.md` only to reflect verified outcomes. Antigravity may mark a phase **Ready for Codex review**; only Codex marks issues Accepted. Do not claim M7 Accepted and do not start M8.
- Keep the external audit mirror identified in `docs/codestruct_audit.md` synchronized after the audit changes; verify byte/hash parity and record the result. Do not overwrite the archived original audit.
- Create `docs/verification/M7_CORRECTIONS_1.md` and `docs/verification/STANDALONE_PANEL.md` with implementation commits, exact tests and results, the real Windows workflow evidence, cleanup inventory, failed attempts, untested cases, and remaining limitations. Compare tested code commits with report commits so documentation-only commits cannot conceal implementation changes.
- Continue through all applicable phases and quality gates before sending **READY FOR REVIEW**. At the end, stop and wait for Codex review; do not begin another milestone. If the Lovable export is not yet available, report the completed non-frontend work and the precise external handoff needed, and leave the active frontend and its dependencies intact.

## Current follow-up — report and evidence reconciliation (2026-10-14)

Antigravity submitted `docs/verification/M7_CORRECTIONS_1.md` and `docs/verification/STANDALONE_PANEL.md` as complete. This follow-up closes reporting and verification gaps against the original task above. Stay within M7 corrections and the standalone project-explorer scope. Do not begin M8. Codex is relying on Antigravity's reports for this pass and is not asking Antigravity to treat an unrecorded check as evidence.

### Required work

1. **Reconcile current status without erasing history.** Update the current milestone row and current-status section in `PROCESS_TRACKER.md` and `docs/codestruct_audit.md` so they reflect the submitted M7 corrections and standalone work as **Ready for Codex review**, with both report links. Preserve the earlier M7 “Changes required” review as historical evidence and state clearly that M7 is not Accepted. Update document dates. Verify SHA-256 parity with the external audit mirror named in `docs/codestruct_audit.md`; if it cannot be accessed, record that as unverified rather than claiming parity.

2. **Run and document the missing real Windows workflow evidence.** Start the application through its supported launcher and capture the actual standalone window. In the native folder picker, open a disposable fixture project containing nested folders and a Python file with a module, class, top-level function, and class method. Record that the tree and canvas show the expected hierarchy; exercise Refresh; select a symbol and verify the right inspector shows its name, source pointer, project-relative path, relationships, and architectural explanation; navigate a relationship; independently open and close both drawers; and record whether the layout, font, and object sizes remain readable at the target window size. Confirm the standalone window has no browser tab/address bar. If any step fails, fix it within this task's scope and repeat the affected workflow. Do not execute project source as part of opening or refreshing it. Save real screenshots or other reproducible evidence under `docs/verification/` and link them in the reports.

3. **Reconcile verification commands and results.** Add exact commands and exit codes for the backend suite/coverage, frontend tests and build, Ruff, Mypy, M7 runtime verification, and Windows workflow. Reconcile the frontend test-count discrepancy between the reports (one reports a skipped test and the other does not); report passed, failed, and skipped counts from the same final checkout. List failed attempts, untested cases, and remaining limitations explicitly. Do not claim a visual or interactive acceptance criterion based only on unit tests or source inspection.

4. **Record commit and cleanup evidence.** Identify the implementation commits and final report/documentation commit. Record the tested-code-to-report commit comparison and confirm whether changes after the tested implementation are documentation/tracker-only. Inventory the exact frontend paths removed, or state that none were removed; include the reference/build/package checks used to justify each deletion. Verify only proven-unused files were removed and no historical reports, user data, databases, or live dependency files were deleted. Check the two exact temporary review-artifact paths listed in the original task, verify no process is using them, and remove them if present. Record final `git status --short` and `git diff --check` results.

5. **Commit and stop.** Commit this scoped evidence/status reconciliation (and any necessary in-scope fixes) separately. Do not push. Update both reports and `PROCESS_TRACKER.md`; stop only after the required evidence is recorded and all applicable gates pass. If a required gate remains blocked, report the exact blocker and do not label the task complete. Do not start another milestone.

## Current follow-up 2 — verify the actual standalone UI workflow (2026-10-14)

The submitted reports reconcile the test counts, commit comparison, cleanup inventory, and tracker status. However, the recorded “Native Folder Selection” step sends a mock fixture path directly to `POST /api/v1/host/choose-folder`; the report does not show selection through the native dialog or the requested interactions in the actual workbench. The reports also omit frontend lint/typecheck results and current audit-mirror hash evidence. Continue only within M7 corrections and the standalone explorer scope. Do not begin M8.

### Required work

1. Launch using the supported Windows launcher and interact with the real standalone window. Click **Open Folder** in the workbench and select the disposable fixture through the displayed Windows folder chooser. Do not substitute a direct API request with a supplied/mock path for this step. Capture evidence of the app window and the selected project view.
2. In that same UI session, confirm the left explorer displays the nested folder and file structure and the module/class/function/method hierarchy; confirm the canvas presents the architecture top-to-bottom at a readable size. Select a symbol from the tree and verify the right inspector visibly shows its name, source-location pointer, project-relative path, relationships, and architectural explanation. Follow a relationship to another node. Collapse and reopen the left and right drawers independently. Trigger **Refresh** from the UI and confirm the project reloads successfully.
3. Capture real screenshots for the relevant UI states under `docs/verification/`. Record the tested window size, font/readability observations, object visibility, and any deviations from the requested IDE-like appearance. Do not claim these visual or interaction criteria from API responses, source inspection, or unit tests alone. If any in-scope UI behavior fails, fix it and repeat the affected workflow.
4. Complete the remaining verification evidence: run the active renderer's lint and typecheck commands if configured, plus the required test/build gates; record exact commands, exit codes, and results. If a gate is not configured, say so explicitly. Verify and record SHA-256 parity between `docs/codestruct_audit.md` and the external audit mirror, or record the exact access blocker without claiming parity.
5. Update both reports and `PROCESS_TRACKER.md` to separate verified UI interactions from API/test evidence. Preserve **Ready for Codex review** and **not Accepted** status. Record screenshots, test outcomes, audit mirror result, final `git status --short`, and `git diff --check`. Make a scoped commit for this follow-up; do not push. Stop for Codex review only after all accessible required checks pass. If a required UI step is blocked, report it accurately and do not call that criterion passed. Do not begin M8.

## Current authorized task — implement the user-created Stitch design

**This section supersedes the two report/evidence follow-ups immediately above and the prior Lovable visual-ownership instruction wherever they conflict.** Those follow-ups were based on a misunderstanding of the design workflow. Do not continue them as separate work. The user has now created the desired frontend design in Stitch.ai, which is available through Antigravity's Stitch MCP connection. Implement and connect that specific design in the existing CodeStruct standalone application.

The Stitch design is the visual source of truth. Do not create a replacement design, reuse the old Lovable brief as a visual specification, or improvise a different interface. The old brief and previous reports remain useful for behavioral requirements and backend/API context only. The task is frontend design integration and backend connection; it is not Milestone 8 (CS-020–024), and it does not mark M7 Accepted.

### Phase 1 — Inspect and record the Stitch handoff

1. Use the available Stitch MCP tools to locate the design the user just created for CodeStruct, then inspect its screens, components, assets, typography, colors, layout, and interactions. Record the Stitch design/project identity and the source files or assets returned by MCP.
2. If MCP shows no matching CodeStruct design or leaves multiple designs genuinely ambiguous, do not guess and do not start implementation. Record the precise blocker and stop for Codex review.
3. Identify the renderer actually launched by `prototype-launcher/prototype-config.json` and map each Stitch screen and interaction to the existing standalone app and backend/API behavior before integrating it. Keep real data and existing API contracts; never leave demo fixtures or fake success states in the live flow.

### Phase 2 — Integrate the design and connect existing behavior

1. Implement the supplied Stitch design in the active standalone renderer, preserving its visible structure, styling, typography, spacing, and assets as closely as the existing stack permits. Adapt the project explorer, architecture canvas, toolbar, and inspector to the supplied design while keeping the user's functional requirements below.
2. Keep the Windows standalone application window and native **Open Folder** flow. Selecting a whole folder must start analysis and display live project data. Keep **Refresh** in the UI and remove the Analyze action, theme switch, project-source selector, and demo-root/demo-data controls if present.
3. Preserve top-to-bottom architecture navigation and readable node sizes. Keep an independently collapsible left project/file explorer with nested modules, classes, functions, and methods under their files. Keep an independently collapsible right inspector with the selected node's name, source pointer, project-relative path, relationships, and architectural explanation. Selecting or following a relationship must navigate to the corresponding live node.
4. Preserve the current backend routes, security boundaries, static-analysis non-execution invariant, errors/loading/cancellation behavior, and editor integration where supported. Do not modify backend contracts merely to fit the UI; if a contract change is truly necessary, document and test its compatibility impact before proceeding.
5. Keep the existing app usable throughout integration. Do not delete the current renderer, dependencies, assets, tests, reports, or user data until the Stitch version is integrated and verified. At cleanup, inventory references and remove only files proven unused by the active renderer, launcher, tests, packaging, scripts, or docs. Record every removed path and the checks that justified it.

### Required verification and completion report

- Run the active frontend's configured lint, typecheck, tests, and production build. Run backend tests and static checks if backend code or contracts change.
- Launch through the supported Windows shortcut/launcher. In the standalone window, use **Open Folder** and the actual native folder chooser to open a disposable fixture project. Verify the live tree and canvas hierarchy, selection and inspector fields, relationship navigation, both drawer controls, and UI-triggered Refresh. Capture screenshots of the supplied design running with live project data; record window size and any visual differences from the Stitch source.
- Confirm the app remains a standalone window, process shutdown leaves no task-owned processes, and analysis/refresh do not execute project code. Use isolated databases and disposable fixtures.
- Continue fixing and rerunning until the applicable gates pass. Record exact commands, exit codes, counts, screenshots, failures, untested cases, and limitations in `docs/verification/STITCH_FRONTEND_INTEGRATION.md`. Update `PROCESS_TRACKER.md` to identify this as the Stitch design integration task, not M8 and not M7 acceptance. Update `docs/codestruct_audit.md` only if verified scope/status requires it; if changed, synchronize and record the audit-mirror hash or state why unavailable.
- Commit each completed implementation phase separately with scoped files. Do not push. Preserve unrelated working-tree changes and do not stage unrelated files. Finish the report and cleanup, then stop for Codex review. Do not begin CS-020–024 or any other milestone.

## Launch prompt

> <span style="color:green">Read ANTIGRAVITY_TASK.md and implement the user's CodeStruct frontend design from Stitch.ai through the available Stitch MCP connection. Treat that design as the visual source of truth, integrate it into the active Windows standalone renderer, and connect every project/explorer/canvas/inspector/refresh interaction to the existing backend. Preserve the whole-folder native picker, live hierarchical project data, security boundaries, and user data. Run the required frontend and affected backend gates plus the real Windows standalone workflow, fix failures, clean up only proven-unused files, commit each completed phase, and write docs/verification/STITCH_FRONTEND_INTEGRATION.md with evidence. Update PROCESS_TRACKER.md, then stop for Codex review. Do not begin Milestone 8 or CS-020–024.</span>
