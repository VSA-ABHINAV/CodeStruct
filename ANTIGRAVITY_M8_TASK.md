# Antigravity Task — Milestone 8 (CS-020–024)

Date: 2026-10-21
Repository: `D:\REP\Codestruct\Codestruct`
Owner: Antigravity implements and verifies; Codex prepares this bounded handoff and reviews the final report.
Prerequisites: M1–M7 recorded accepted in `PROCESS_TRACKER.md`; M7's report-based decision is documented in `docs/verification/M7_CODEX_REVIEW_2_ACCEPTED_REPORT_BASED.md`.

## Goal

Complete the remaining in-scope quality, evaluation, accessibility, documentation, and packaging work in M8. Use `D:\REP\# CodeStruct – Technology Summary.txt` as the primary product and technology source, together with `docs/codestruct_audit.md`, `PROCESS_TRACKER.md`, and the current implementation. Keep findings evidence-based and distinguish implemented behavior, automated evidence, real application evidence, owner decisions, and unverified limitations.

M8 covers CS-020–024 only. Do not add deferred CS-025 features, redesign the approved frontend, or expand product scope.

## Required work

### CS-020 — Accuracy and performance evaluation

- Create reproducible ground-truth fixtures representing small, nested, typed, and larger Python projects, with documented expected entities and relationships for modules/files, imports, calls, inheritance, and dependencies.
- Measure precision, recall, and F1 separately for each supported entity and relationship category. Define normalization, matching, exclusions, and treatment of uncertain/inferred edges before reporting scores.
- Measure analysis time, peak or representative memory, graph layout time, and runtime instrumentation overhead where applicable. Include multiple project sizes and repeat methodology sufficient to report variability.
- Set explicit regression budgets based on measured behavior and product requirements. Avoid inventing accuracy claims or budgets unsupported by data; document unsupported language constructs and known limitations.
- Record commands, environment, fixture revision/hash, raw or machine-readable results, summary tables, and reproducibility instructions.

### CS-021 — Storage and failure behavior

- Preserve the already accepted M4 cancellation lifecycle. Investigate the deferred M8 storage-fault cases: unavailable/unwritable database, transaction/commit failure, interrupted writes, corrupt or incompatible persisted state, and recovery/restart behavior as applicable to the actual storage design.
- Define expected API/UI outcomes for each applicable fault, prevent partial/corrupt state from being presented as successful, and add meaningful regression tests.
- Exercise real local service restart/recovery when a test can safely and deterministically cover it. Do not claim unsupported hardware or power-loss guarantees.

### CS-022 — Accessibility observation

- Retain existing automated keyboard, focus, ARIA, responsive, and reduced-motion checks.
- Perform a manual screen-reader observation using an already available screen reader if possible. Record screen reader/browser versions, steps, observed announcements and issues, and any fixes/retests.
- If no usable screen reader is installed or a human observation is required, report this as pending evidence and identify the exact owner action. Do not claim manual accessibility acceptance from automated checks.

### CS-023 — Documentation and audit consistency

- Reconcile current README, architecture/API documentation, technology summary references, process tracker, audit rows, and verification claims against the actual code and executed checks.
- Preserve historical reports, but label superseded or report-only claims clearly. Remove stale instructions that still describe the standalone Edge app or an obsolete workflow, while retaining useful history and user files.
- Update CS-023 evidence incrementally and ensure every current completion claim points to reproducible evidence.

### CS-024 — Packaging and release readiness

- Verify the frontend production build is included in the Python wheel/package and served by the installed application, with consistent version metadata and declared runtime/development dependencies.
- Build the package, install it into a clean isolated environment, run the packaged backend and Thonny plugin workflow, and verify startup, restart, shutdown, upgrade, and rollback behavior as supported by the project.
- Audit supported OS/Python versions, dependency licenses, and third-party notices. Identify owner decisions such as project license, maintainer/contact, and any distribution policy; do not choose these on the user's behalf.
- Do not publish, deploy, upload artifacts, create public releases, expose services to the internet, or make irreversible release/ownership decisions. Prepare evidence and flag approvals needed.

## Workflow and safety boundaries

- Confirm repository root, branch, HEAD, and working tree before editing. Preserve unrelated changes and user data. Never reset/rebase or stage unrelated files.
- Work in bounded subphases with scoped commits; do not push. Keep local services bound to loopback. Use disposable test data and isolated environments for destructive package/database tests.
- Before deleting any file, search references across source, tests, packaging, scripts, shortcuts, and docs; remove only proven-unused artifacts and list the inventory in the report.
- If an owner decision is needed, continue independent technical work and list the decision precisely. Stop only the dependent action; do not guess.
- Keep `PROCESS_TRACKER.md` and `docs/codestruct_audit.md` current. Synchronize the designated external audit mirror only if the existing workflow allows it; otherwise record the exact blocker and local hash.

## Verification and completion

- Run focused tests while developing and the complete applicable backend, plugin, frontend, lint, type, build, packaging, and runtime gates after the final code change. Record exact commands, exit codes, counts, and important output.
- Run the real Windows Thonny prototype using the packaged install where supported. Verify that only the Thonny window opens, Tools → CodeStruct opens the embedded editor tab, the File view project is analyzed, source navigation works, and service stop/restart does not open a standalone window or close Thonny.
- Write `docs/verification/M8.md` with scope, changed files, commits, evaluation method/results, fault matrix, accessibility observation or exact blocker, package clean-install and lifecycle evidence, commands/results, cleanup inventory, limitations, owner decisions, and final Git/whitespace status.
- Update the M8 and CS-020–024 rows in `PROCESS_TRACKER.md` and `docs/codestruct_audit.md`; do not mark the milestone Accepted. Keep owner decisions and pending manual evidence explicit.
- Continue implementation and testing until all technically actionable M8 requirements pass or a genuine external/owner blocker is documented with independent work completed. Then send `READY FOR REVIEW` with the report path and concise evidence summary. Stop there; do not start work beyond M8.

## Launch prompt

> <span style="color:green">Read ANTIGRAVITY_M8_TASK.md and implement Milestone 8 (CS-020–024) within its scope. Run the reproducible accuracy/performance evaluation, storage-fault checks, available manual accessibility observation, documentation reconciliation, and clean-package install/lifecycle workflow; keep fixing and rerunning applicable gates until requirements pass or a genuine owner/environment blocker is evidenced. Update PROCESS_TRACKER.md and docs/codestruct_audit.md, write docs/verification/M8.md, commit scoped phases, then send READY FOR REVIEW and stop. Do not mark M8 Accepted, do not implement CS-025, and do not push, publish, deploy, or expose services publicly.</span>
