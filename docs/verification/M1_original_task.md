# Antigravity task — Milestone 1

Status: Ready to start. Implement only M1, then stop for Codex review.
Workspace root: `D:\REP\Codestruct\Codestruct`.
Product source: `D:\REP\# CodeStruct – Technology Summary.txt`.
Audit: `docs/codestruct_audit.md`. Tracker: `PROCESS_TRACKER.md`.

## Objective

Make the local editor/navigation boundary safe and correctly scoped, establish reproducible quality checks, and produce the backend contract needed for the user to build a new frontend in Lovable. Issue IDs: CS-001, CS-002, CS-003, CS-004, CS-023 and only the contract/requirements portion of CS-026.

User workflow: Lovable creates frontend visuals. Antigravity does backend, IDE, tests, documentation and later integration of Lovable export. Do not redesign or replace the frontend in M1. Minimal compatibility edits to its API/session handling are allowed only when needed for the secured editor bridge; explain them in evidence. Do not implement M2 metrics/RAG fixes, runtime execution, incremental caching or Graphviz rendering yet.

## Read first and preserve state

Read the technology summary, audit, tracker, applicable AGENTS.md files if present, API/security/graph contracts, `navigate.py`, `editor.py`, `jobs/service.py`, plugin navigation/selection code, existing navigation/editor/plugin tests, `App.jsx`, `useAnalysisJob.js` and the shared API client. Inspect `git status` and preserve all staged/modified/untracked files. Do not reset, clean, checkout over user changes, reformat the entire repository, commit, publish or deploy.

Keep static analysis non-executing. Do not expose credentials, private roots, database contents or source in logs/artifacts. Use temporary fixtures and task-owned databases. Never edit the sibling Thonny checkout unless the defect cannot be addressed in the plugin and the evidence justifies the scope.

## Required implementation

### 1. CS-001 — Navigation session and API trust boundary

- Replace acceptance of arbitrary nonempty session tokens with service-owned active editor-session/capability validation. Separate public root IDs from credentials. Use a single consistent session lifecycle with expiry/revocation and bounded outstanding commands.
- Authorize POST, pending and acknowledgement for the same valid session and permitted source scope. Revalidate path/file scope before delivery; ensure expired, unknown, revoked or wrong-session commands cannot operate.
- Define local origin/proxy policy explicitly. A browser cannot authenticate navigation just by supplying a configured project alias. Preserve legitimate same-origin/local frontend operation; do not solve the problem with wildcard CORS, arbitrary filesystem access or unrestricted remote exposure.
- Validate relative paths across Windows and POSIX forms; reject absolute/drive/UNC paths, traversal, NUL, symlink/junction escapes and disallowed files. Keep private absolute paths server-side.
- Keep queue bounds, TTL and acknowledgement/replacement behavior deterministic; eliminate cross-test/cross-service leakage from global state as appropriate. Match acknowledgement to the command ID, and retain meaningful delivered/failed outcome semantics.

### 2. CS-002 — Correct Thonny destination and acknowledgement

- Bind each pending command to the root/file registered by that IDE session. Do not search all roots and choose the first file with a matching name.
- Validate canonical containment and symlink/reparse behavior in the plugin as defense in depth. Handle session expiry, missing files and source changes safely.
- Verify Thonny's actual line/column convention against installed/source API. Open exact file and cursor on Tk main thread; no repeated/overlapping pollers or leaked threads on shutdown.
- Failure must not be reported as successful navigation. Return/record a safe reason and do not retry indefinitely. If a minimal current UI adapter needs updating to use a revised session contract, do so without visual redesign and surface truthful status.
- Support the currently authorized selected-file scope. Document project-wide IDE selection as a later contract need rather than broadening authorization silently.

### 3. CS-003 — Reproducible checks

- Reconcile root `mypy.ini` with `[tool.mypy]` in `pyproject.toml` so the documented check runs the intended targets and settings.
- Ensure plugin tests and relevant plugin lint are part of a documented repeatable quality workflow/CI. Preserve coverage gates; do not lower thresholds, exclude failing code or delete tests to make checks green.
- Run baseline first; separate environmental failures from application defects. Fix newly introduced regressions and M1-related failures. Log unrelated discovered issues with proposed CS ID/milestone instead of expanding scope.

### 4. CS-004 / CS-023 / CS-026 — Lovable handoff and truthful docs

Create `LOVABLE_FRONTEND_BRIEF.md` at repository root with a copy-pastable Lovable brief plus actual backend contract. It must include:

- Product purpose and evidence principle; target user workflow; high-priority replacement of the unsatisfactory current frontend; accessible responsive visual hierarchy, graph/table parity, clear controls and detail/evidence panels.
- Required screens/states: project selection, submission/progress/cancel, graph retrieval, complete/partial/cache results, empty/error/expired states, bounded Load more, search/filter/views, details/evidence/diagnostics, metrics, DOT export, optional explanation, available/unavailable editor navigation. Mark later backend capabilities as unavailable until implemented.
- Actual endpoint/method/request/response/error/pagination schemas, versioning and source coordinates. Give examples produced from real canonical serialization or contract tests, not invented field names. Include capability/session handoff and navigation outcome schema after the M1 change.
- API base and same-origin proxy configuration, local exported-frontend deployment, precise CORS/loopback boundaries and packaged assets. Hosted Lovable preview must use clearly labeled fixtures unless there is an approved secure reachable backend; no promise that hosted HTTPS can directly use a user's local HTTP service.
- No new backend/database/auth service in Lovable, no secrets in frontend, no fabricated live analyses, no remote project-source upload. Reuse this backend and its contract.
- Renderer choice requirements: current React Flow versus summary-proposed Cytoscape.js; document rationale/options and performance/accessibility needs, without deciding by library name alone. Do not migrate a renderer in M1.
- Frontend integration checklist and user design acceptance criteria; Antigravity will connect the exported source in M4. Include a fixture/contract package under `docs/frontend-contract/` if useful, generated and validated against current backend.

Update touched API/security/testing docs to reflect what actually works. Do not mark unverified source navigation or the future new frontend complete. Keep the audit issue meanings stable; record new findings separately rather than renumbering existing IDs.

## Required regression coverage

Use tests that exercise real service/session validation and canonical API shapes, not merely mocks that accept any string:

- Unknown/expired/revoked session, wrong IDE session, public alias used as credential, TTL, queue bound, last-command replacement and acknowledgement of the wrong command.
- Traversal using both separators, absolute/drive/UNC paths, unsupported/missing file, link escape where platform allows, and same relative filename in two distinct roots.
- Selected-file capability remains confined to its selected source scope; valid navigation reaches only its owning IDE session.
- Plugin exact path/line/column, UI-thread scheduling, failure outcome, poll shutdown and no duplicate pollers.
- Minimal frontend compatibility/session contract changes, if any, have API-level/component regression coverage; contract fixtures match canonical serialization.

## Checks and real application verification

Run from the repository root using the existing environment. If dependencies/tool permissions are blocked, record exact error and recover within authorized capabilities; do not claim success.

```powershell
.\.venv\Scripts\python.exe -m pytest --no-cov -p no:cacheprovider -q
.\.venv\Scripts\python.exe -m pytest thonny-plugin/tests --no-cov -p no:cacheprovider -q
.\.venv\Scripts\python.exe -m pytest -m "not performance and not slow"
.\.venv\Scripts\python.exe -m ruff check backend tests sample_project thonny-plugin
.\.venv\Scripts\python.exe -m ruff format --check backend tests sample_project
.\.venv\Scripts\python.exe -m mypy
npm.cmd --prefix frontend test -- --reporter=dot
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Run frontend coverage when changing frontend logic and keep configured thresholds. Verify the post-change mypy command uses the authoritative configuration. Log pass/fail/skip counts, exit status and limitations. Do not treat jsdom canvas warnings as proof of real graph rendering.

This is a Python/web/Thonny application, not a game: the equivalent of the real main scene is the actual local backend + browser + Thonny workflow. Use the prototype launcher only after reading its instructions/scripts and verifying its configured paths. Do not terminate unrelated user processes.

Perform short bounded real smoke sessions:
1. Start local backend and current frontend against temporary safe roots, and open Thonny with plugin.
2. Analyze a selected fixture Python file from Thonny and verify real result retrieval.
3. Invoke Open in editor; record exact target path relative to fixture root, expected line/column and observed editor selection.
4. With two roots containing the same filename, prove only the session-owned file opens.
5. Exercise invalid/expired session and failed navigation; verify safe feedback/outcome and continued operation.
6. Shut down only processes started for this task; record cleanup/listener status.

If direct GUI control is unavailable, complete automated/process/API checks and report the exact missing manual verification. Mark that acceptance gate pending; do not invent screenshots, cursor observations or full completion. Limit each browser/IDE smoke to one focused action/30–60 seconds and preserve partial evidence if interrupted.

## Deliverables and stop gate

- M1 implementation and meaningful regression tests only.
- `LOVABLE_FRONTEND_BRIEF.md` and any validated contract fixtures.
- `docs/verification/M1.md`: initial/final changed-file list, issue-by-issue changes, exact test commands/results, real application reproduction/evidence, safe screenshots/logs if available, limitations, new findings and cleanup.
- Update `PROCESS_TRACKER.md` with M1 and issue statuses plus evidence links; update audit status only to Ready for Codex review or Verification gap. Preserve historical baseline.
- Final response: concise changed behavior, test results, remaining limitations, and `Ready for Codex review`.

Do not mark M1 Accepted. Do not begin M2, redesign the frontend, add optional features, publish or deploy. Stop and wait for Codex review.

## Launch line

Read ANTIGRAVITY_TASK.md and implement Milestone 1 within its scope. Update PROCESS_TRACKER.md, run the required tests and real backend/browser/Thonny workflow, record verification evidence, then stop for Codex review. Do not begin Milestone 2.
