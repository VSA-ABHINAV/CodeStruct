# Antigravity task: create and publish the accepted CodeStruct baseline repository

Date: 2026-10-03. Local repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M1_CODEX_REVIEW_8_ACCEPTED.md`, `docs/verification/M2_CODEX_REVIEW_4_ACCEPTED.md`, `PROCESS_TRACKER.md`, the current audit, `.gitignore`, release/security documentation, and the current Git state. M1 and M2 are Accepted. This task is repository bootstrap and baseline publication only. Do not begin M3, M4, frontend redesign, runtime work, RAG, caching/export milestones, release publication, package publication, or deployment.

The user explicitly authorizes creating a remote repository, committing the accepted local baseline, and pushing it. Create the remote as **private** by default under the currently authenticated GitHub account. Preferred repository name: `CodeStruct`. If that name already exists, do not overwrite, delete, force-push, or reuse an unrelated repository; stop and report the exact conflict.

## Repository safety and baseline preparation

1. Confirm `D:\REP\Codestruct\Codestruct` is the Git top level, branch `main`, with no existing commits and no remote. Preserve every project/user file.
2. Audit all staged, modified and untracked paths before committing. Ensure `.gitignore` excludes secrets and generated/runtime data, including `.env` (while keeping `.env.example`), virtual environments, `node_modules`, Python/pytest/coverage caches, build/dist output, local `.codestruct` databases/WAL/SHM files, temporary smoke projects, session/capability artifacts, logs, IDE metadata, and dependency caches. Do not delete local files merely to exclude them.
3. Perform a filename and content secret scan without printing secret values. Reject real credentials, tokens, private keys, capability/session tokens, machine-specific database files, or personal absolute paths that do not belong in portable documentation. Keep intentional documented repository paths only where needed for historical verification; redact live credentials.
4. Inspect the final staged inventory and `git diff --cached --check`. Do not include `.venv`, `node_modules`, runtime databases, coverage HTML, temporary files, generated caches, or task-created credentials. Do include source, tests, lockfiles, accepted audit/tracker/task history, Lovable contract/fixtures, Thonny plugin, CI, and verification evidence.

## Verification before the baseline commit

Run the accepted baseline gates from a clean staged tree:

- exhaustive M2 parity probe and both Codex M2 probes;
- full backend pytest with coverage;
- Thonny plugin pytest;
- Ruff check and format check;
- mypy using the authoritative configuration;
- frontend tests, lint, and production build;
- real M2 backend smoke;
- internal/external audit hash comparison.

If a command requires Windows temporary-directory access, rerun it outside the managed sandbox and record the distinction. Do not weaken checks to obtain a pass.

## Commit and private remote creation

1. Add a short version-control policy to `CONTRIBUTING.md` or `docs/development/` stating:
   - each milestone stays within its declared scope;
   - Antigravity commits and pushes a milestone only after its required gates pass and it is ready for Codex review;
   - review corrections receive bounded follow-up commits after their gates pass;
   - Codex acceptance is recorded in a small acceptance/tracker commit when applicable;
   - never combine the next milestone with the current commit;
   - never rewrite published history, force-push, commit secrets/generated runtime data, or tag/release/deploy unless the user explicitly requests it.
2. Stage the complete safe accepted M1–M2 baseline and create the initial commit with message: `chore: establish accepted M1-M2 baseline`.
3. Using the authenticated GitHub CLI/account, create private repository `CodeStruct`, set it as `origin`, and push `main` with upstream tracking. Do not make it public. Do not create a release or tag.
4. Verify the remote URL, repository visibility, pushed commit SHA, upstream relationship, and clean working tree. Confirm the remote commit matches local `HEAD`.
5. Record sanitized evidence in `docs/verification/REPOSITORY_BOOTSTRAP.md` and update `PROCESS_TRACKER.md`. Because these records are created after the initial commit, create and push a second small documentation commit: `docs: record repository bootstrap evidence`. The final working tree must be clean and local/remote `main` must match.

If GitHub CLI authentication, repository creation, or push fails, preserve the local commit, record the exact sanitized blocker, and stop. Never expose credentials or change account authentication silently.

## Standing commit rule for later milestones

Carry this rule into every later `ANTIGRAVITY_TASK.md`: after the milestone implementation and required gates pass, commit and push only that milestone's bounded changes before stopping for Codex review. If Codex requests corrections, commit and push each verified correction separately. After acceptance, commit and push acceptance/tracker documentation. Never begin or include the next milestone in those commits.

## Stop condition

Stop after the private repository exists, both bootstrap commits are pushed, local and remote `main` match, the working tree is clean, and evidence is recorded. Return the repository URL, visibility, both commit SHAs/messages, verification results, and any limitations. Do not begin M3 or M4.

## Launch prompt

Read ANTIGRAVITY_TASK.md and create the private CodeStruct GitHub repository from the accepted M1–M2 local baseline. Audit exclusions and secrets, run every required gate, create and push the baseline and repository-evidence commits, establish the standing per-milestone commit policy, update PROCESS_TRACKER.md, verify local/remote main and a clean tree, then stop for Codex review. Do not begin Milestone 3 or 4.
