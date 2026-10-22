# Antigravity Task — Thonny Workbench Layout Correction

Date: 2026-10-21  
Repository: `D:\REP\Codestruct\Codestruct`  
User evidence: `D:\REP\changes.png`  
Owner: Antigravity implements and verifies; Codex maintains the bounded handoff and reviews the report.

## User's required result

The CodeStruct workbench is already inside Thonny's editor tab. The attached screenshot shows the remaining layout problem: Thonny's native Files pane and CodeStruct's Project Explorer are duplicated; CodeStruct Diagnostics/Shell are separate from the native Thonny Shell; the Inspector occupies only part of the right side and leaves a large blank strip.

The user selected CodeStruct's richer Explorer as the single Explorer. For the bottom surface, use the recommended default of Thonny's native Shell as the single Shell/Diagnostics surface unless the user sends a correction before implementation.

## Required behavior

1. **One unified Explorer on the left.** Keep the CodeStruct Explorer and make it contain the complete current project folder/file tree plus each Python file's module, class, function, and method symbols. It opens by default, has a clear toggle icon to collapse/reopen, and remains usable at practical window sizes. While the CodeStruct editor tab is active, hide Thonny's duplicate native Files pane. When switching to a normal source tab or closing CodeStruct, restore the Files pane to the user's prior visibility/state. Do not permanently change Thonny preferences. Preserve the trusted current File-view project root and project switching behavior even while its native pane is hidden.
2. **One bottom Shell/Diagnostics surface.** Use Thonny's native Shell as the sole bottom Shell/Diagnostics panel. Remove the separate CodeStruct Shell and Diagnostics panes from the editor content. Route useful CodeStruct diagnostic/status/error messages to the native Shell through a supported Thonny API; keep compact connection/progress status in the workbench toolbar if useful. Do not create a second shell window or panel. If installed Thonny APIs constrain structured output, implement the closest supported integrated presentation and document the exact limitation; do not silently retain duplicate panels.
3. **Full-height Inspector on the right.** The Inspector opens by default, fills the complete available right-hand workbench region from the top tool/header area to the bottom of the editor content area, and has a clear toggle icon to close/reopen. Remove the large blank strip visible in the screenshot. Preserve selected-node details, source pointer/path, relationships, explanation, and related-node navigation.
4. **Keep all behavior inside Thonny.** Do not add a standalone window/browser. Retain current File-view-root selection, switching between projects, source navigation, static non-execution guarantees, capability/security boundaries, responsive layout, keyboard operation, and accessible labels/focus.

## Investigation and verification

- Inspect the actual installed Thonny APIs and current plugin lifecycle before changing pane visibility. Implement the hide/restore behavior with a supported extension point where possible. Save and restore the user's prior Files-pane state across tab switch, tab close, plugin shutdown, and application restart; do not strand the user with a hidden Files pane.
- Reproduce the screenshot's layout in the real Windows Thonny main window, then verify: exactly one left Explorer, one native bottom Shell carrying CodeStruct diagnostics, full-height right Inspector; each drawer toggle; switching to source tabs and back; close/reopen; changing to a second project; window resize/narrow view; and clean Thonny shutdown/restart.
- Capture before/after screenshots at recorded viewport sizes. Verify panels in the same Thonny window; mocks/headless checks alone are insufficient.
- Add focused regressions for panel lifecycle and routing. Run the relevant Thonny plugin, frontend, backend, lint, typecheck, build, and packaging gates after the final change. Keep source analysis static and never execute fixture/project code.
- Write `docs/verification/THONNY_WORKBENCH_LAYOUT_CORRECTION_1.md` with the screenshot-based failure, cause, design decisions, real UI steps/screenshots, exact commands/results, failures/fixes, lifecycle and project-switch evidence, cleanup/reference checks, limitations, commits, and final Git status/`git diff --check`.
- Update M7 status to **Changes required** while this user-visible correction is in progress; keep M8's completed evidence intact and do not mark M7/M8 Accepted. Update `PROCESS_TRACKER.md` and `docs/codestruct_audit.md`, and synchronize the external audit mirror/hash if the existing authorized workflow allows it.
- Commit the scoped correction and push it to the already configured `origin/main` without force. This push is authorized by the user's earlier explicit Git-deployment instruction. Do not change the remote URL/visibility, publish packages, create tags/releases, deploy a service, or push unrelated commits. If remote diverged, stop without force and report the blocker.
- After all requirements and gates pass, send `READY FOR REVIEW` with the report, commit/push evidence, and any limitations, then stop. Do not start unrelated work.

## Launch prompt

> <span style="color:green">Read ANTIGRAVITY_THONNY_LAYOUT_TASK.md and reproduce the screenshot problem in the real Windows Thonny window. Implement one toggleable CodeStruct Explorer containing the folder/file tree and nested Python symbols, hide/restore Thonny's native Files pane with the CodeStruct tab lifecycle, route CodeStruct diagnostics into the single native Thonny Shell, and make the toggleable Inspector fill the right workbench height. Verify the actual Thonny workflow, toggles, tab switching, project switching, close/reopen, and resize; capture screenshots and run all affected gates. Update docs/verification/THONNY_WORKBENCH_LAYOUT_CORRECTION_1.md, PROCESS_TRACKER.md, and the audit; commit scoped changes and push only to existing origin/main without force. Do not mark M7/M8 Accepted, publish packages, or start unrelated work. Send READY FOR REVIEW and stop.</span>
