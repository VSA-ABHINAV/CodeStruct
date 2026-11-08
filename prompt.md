# Phase 19 + Phase 20 Tooling — Commit to New Branch (Not Main)

## Objective
Commit all Phase 19 (Advanced Architecture) implementation files and Phase 20 (Usability Study tooling) changes currently sitting in the working tree into a **new git branch**. These changes must **not** land on `main`.

## Preconditions
- Working tree at `D:\CodeStruct` contains uncommitted Phase 19 + Phase 20 changes (see `git status`)
- Remote `origin` = `https://github.com/VSA-ABHINAV/CodeStruct.git` (confirmed in Phase 18)
- All Phase 19 tests pass (52/52 regression suite) — verified in report.md
- All Phase 20 unit tests pass — verified in report.md

## Tasks

### 1. Create a new branch
- Create a new branch from the current `master` (e.g., `feature/phase-19-20-tooling` or similar descriptive name).
- **Do NOT commit to `master`/`main`.** The human explicitly requires these changes stay off the main branch.

### 2. Stage the following changes
Stage all files related to Phase 19 and Phase 20 tooling:

**Phase 19 (Advanced Architecture):**
- `codestruct/backend/advanced_architecture.py` (new)
- `codestruct/tests/test_advanced_architecture.py` (new)
- `codestruct/scratch/run_live_advanced_architecture.py` (new)
- `codestruct/scratch/verify_phase19_ui.py` (new)
- `codestruct/docs/screenshots/view_architecture.png` (new)
- `codestruct/docs/screenshots/architecture_cross_navigation.png` (new)
- `docs/screenshots/view_architecture.png` (new)
- `docs/screenshots/architecture_cross_navigation.png` (new)
- `codestruct/backend/api.py` (modified — added `/api/architecture/advanced` endpoint)
- `codestruct/backend/qwen_client.py` (modified — optional `system_prompt` param)
- `codestruct/backend/schemas.py` (modified — added `ComponentCluster`, `AdvancedArchitectureResponse`)
- `codestruct/frontend/index.html` (modified — Architecture tab)
- `codestruct/frontend/static/app.css` (modified — Architecture styles)
- `codestruct/frontend/static/app.js` (modified — Architecture tab controller)
- `codestruct/scratch/update_app_js.py` (modified)

**Phase 20 (Usability Study tooling — Antigravity-buildable tasks only):**
- `docs/usability_study/questionnaire.html` (new)
- `docs/usability_study/score.py` (new)
- `docs/usability_study/test_score.py` (new)
- `docs/usability_study/results.md` (new — structure pending real data)
- `docs/usability_study/raw_data/README.md` (new)
- `docs/usability_study/raw_data/` (empty directory — note: git does not track empty directories; the README suffices)

**Build-record docs:**
- `PROGRESS.md` (modified — added Phase 19 and Phase 20 entries)
- `prompt.md` (modified — Phase 19 then Phase 20 prompts)
- `report.md` (modified — Phase 19 report, then Phase 20 report)

Do **not** stage:
- `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.codestruct_cache/` (gitignored)
- `venv/`, `.venv/` (gitignored)
- `scratch/` debug artifacts unrelated to Phase 19/20 verification (e.g., `cdp_capture.py`, `debug_docks.py`, etc. — leave as-is)

### 3. Commit
- Commit with a clear message, e.g.:
  `feat: Phase 19 Advanced Architecture + Phase 20 usability study tooling`
- Include all the above files in a single commit (or a small logical set of commits on the new branch).

### 4. Push (conditional)
- Per the Phase 18 spec guardrail: "Never push without a human-confirmed remote URL."
- The remote `origin` was confirmed in Phase 18, but **do not push to `master`/`main`**.
- If you push, push only to the new branch, and report the branch name and remote output.
- If you are unsure whether to push, stop and ask the human — do not guess.

## Guardrails
- **Never commit to `main`/`master`.** New branch only.
- **Never force-push.**
- **Never rewrite or squash existing history.**
- **Do not fabricate test results or participant data.** Phase 20 `results.md` correctly shows n=0 pending real study sessions — do not alter it to look complete.
- **Phase 16 (dynamic/runtime execution) remains untouched.** Confirm no Phase 16 code is included.

## What I Need Back in report.md
- The new branch name
- The exact `git` commands run (copy-pasted, not summarized)
- The exact `git status` output after committing (clean working tree on the new branch)
- The exact `git log --oneline` output showing the commit(s) on the new branch
- Whether you pushed and, if so, the `git push` output (branch + remote)
- A confirmation that `master`/`main` was not touched
- Anything you were unsure about or had to make a judgment call on

## Estimated Time
0.5h