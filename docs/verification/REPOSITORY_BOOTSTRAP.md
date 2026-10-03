# CodeStruct Repository Bootstrap and Baseline Publication

**Date:** 2026-10-03  
**Status:** Complete  
**Scope:** Repository Bootstrap and Accepted M1–M2 Baseline Publication.

---

## 1. Remote Repository Summary

- **Repository Name:** `CodeStruct`
- **Owner Account:** `VSA-ABHINAV`
- **Full Name:** `VSA-ABHINAV/CodeStruct`
- **Remote URL:** `https://github.com/VSA-ABHINAV/CodeStruct`
- **Clone URL:** `https://github.com/VSA-ABHINAV/CodeStruct.git`
- **Visibility:** `private` (Private repository)
- **Default Branch:** `main` (tracked upstream `origin/main`)
- **Initial Baseline Commit SHA:** `ff8a774c85fe13f7afd62a81bafc0cc7d7e9a1ee` (`chore: establish accepted M1-M2 baseline`)

---

## 2. Exclusion and Secret Audit Summary

1. **Ignored Runtime & Cache Artifacts:**
   - `.gitignore` explicitly excludes `.env` (preserving `.env.example`), Python virtual environments (`.venv/`, `venv/`), `node_modules/` (including `frontend/` and `frontend.lovable/`), Python/pytest/coverage/ruff/mypy caches, build/dist outputs (`frontend/dist/`, `frontend.lovable/dist/`, `release-output/`), local `.codestruct/` databases, temporary test outputs, launcher runtime files (`prototype-launcher/runtime/`, `prototype-launcher/logs/`), and SQLite journal/WAL/SHM files (`*.sqlite`, `*.sqlite3`, `*.sqlite-wal`, `*.sqlite3-wal`, `*.sqlite-shm`, `*.sqlite3-shm`, `*.db-wal`, `*.db-shm`).
2. **Secret Scan:**
   - Automated regex scan for GitHub tokens (`ghp_`, `gho_`, `github_pat_`), private keys, and authorization bearer tokens across the entire tree returned **0 potential secret matches**.
   - No live credentials, passwords, private keys, or machine-specific tokens are tracked in git.

---

## 3. Version-Control and Milestone Policy

The version-control policy has been documented in `CONTRIBUTING.md`:
1. **Declared Scope Isolation:** Each milestone stays strictly within its declared scope.
2. **Pre-Review Commit & Push Gate:** Antigravity commits and pushes a milestone only after all its required gates pass and it is ready for Codex review.
3. **Bounded Correction Commits:** Review corrections receive bounded follow-up commits after their specific gates pass.
4. **Acceptance Documentation Commits:** Codex acceptance is recorded in a small acceptance/tracker commit when applicable.
5. **No Milestone Mixing:** Never combine the next milestone with the current commit.
6. **Immutable Published History & Safety:** Never rewrite published history, force-push, commit secrets/generated runtime data, or tag/release/deploy unless the user explicitly requests it.

---

## 4. Verification Gates Pre-Commit Baseline

All required quality gates executed cleanly prior to the baseline commit:

| Gate | Command | Result |
|---|---|---|
| **Exhaustive Parity Probe** | `.venv\Scripts\python docs/verification/M2_review2_parity_probe.py` | **Exit 0** (64 4-node + 1024 5-node graphs pass) |
| **Codex Review Probe** | `.venv\Scripts\python docs/verification/M2_codex_review_probe.py` | **Exit 0** (canonical location `app.py:1-2`, unresolved fan-in/out 0/0) |
| **Ruff Check** | `.venv\Scripts\ruff check .` | **All checks passed!** |
| **Ruff Format Check** | `.venv\Scripts\ruff format --check .` | **195 files already formatted** |
| **Mypy Type Check** | `.venv\Scripts\mypy --config-file pyproject.toml` | **0 issues across 50 source files** |
| **Backend Pytest** | `.venv\Scripts\python -m pytest` | **189 passed, 1 skipped, 1 warning** (85.49% coverage, exceeds 84% gate) |
| **Plugin Pytest** | `.venv\Scripts\python -m pytest thonny-plugin/tests --no-cov` | **53 passed, 1 skipped** |
| **Frontend Vitest** | `npm --prefix frontend test -- --run` | **94 passed across 10 test files** |
| **Frontend Lint** | `npm --prefix frontend run lint` | **Exit 0** |
| **Frontend Build** | `npm --prefix frontend run build` | **Exit 0** (production bundle built in 576ms) |
| **Real Backend Smoke** | `.venv\Scripts\python docs/verification/M2_real_smoke.py` | **Exit 0** (metadata, module metrics, location range, evidence observations) |
| **Audit Mirror Hash** | `Get-FileHash docs\codestruct_audit.md, <mirror_path>` | **Identical SHA-256** (`7DDFD63AAD...`) |

---

## 5. Branch and Push State

- Local branch `main` tracks `origin/main`.
- Remote repository URL: `https://github.com/VSA-ABHINAV/CodeStruct.git`.
- Visibility: Private.
