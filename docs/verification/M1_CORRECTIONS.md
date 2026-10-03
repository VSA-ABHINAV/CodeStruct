# Milestone 1 — Codex Review Correction Pass

Date: 2026-09-26. Addresses findings R1–R6 in `docs/verification/M1_CODEX_REVIEW.md`.  
Prior baseline evidence preserved in `docs/verification/M1.md`. No code changes by Codex.

---

## R1 — Path identity hardening (CS-001/002)

**Finding:** Service resolved the registered path before checking reparse points, without comparing resolved identity with registration.

**Corrections in `backend/src/codestruct/jobs/service.py`:**

- `register_editor_file`: calls `_has_link_component(file_path)` **before** resolution to catch ancestor junction/symlink/reparse swaps. Stores `cap.file_identity = os.path.normcase(str(file_path.resolve(strict=True)))` at registration time.
- `queue_editor_navigation` and `get_pending_navigation`: re-run `_has_link_component(cap.file_path)` on each call, then re-resolve and compare `os.path.normcase(str(curr)) != cap.file_identity` — rejecting retargeted junction ancestor swaps with `PROJECT_UNAUTHORIZED`.
- `resolve_project`: same pattern — `_has_link_component` → resolve → identity compare.

**Probe result (all pass):**
```json
{
  "retargeted_junction_post_status": 403,
  "retargeted_junction_pending": false
}
```

---

## R2 — Session uniqueness & storage bounds (CS-001/002)

**Finding:** `register_editor_file` reused capability by path digest; independent registrations returned the same token.

**Corrections in `backend/src/codestruct/jobs/service.py`:**

- Removed credential-reuse loop. Every registration now gets a unique token: `"cap_" + secrets.token_urlsafe(24)`.
- Added bounded capability storage (`max_capabilities = 100`) with oldest-entry eviction and expired-entry pruning on each registration.

**Corrections in `thonny-plugin/thonnycontrib/codestruct/__init__.py`:**

- Added `_nav_registered_file_resolved: Optional[Path] = None` and `_nav_poll_generation: int = 0` module globals.
- `_drain_queue` now resolves and stores `_nav_registered_file_resolved` from the registered file path.

**Probe result:**
```json
{
  "two_registrations_share_session_token": false
}
```

---

## R3 — Canonical contract fixtures (CS-004/026)

**Finding:** `graph_slice.json` nested coordinates under `location.span`, used `metadata` not `attributes`, invented evidence/page shapes.

**Corrections — `docs/frontend-contract/graph_slice.json` regenerated using actual `graph_to_dict` schema:**

- `location` is flat: `{ source_unit_id, path, start_line, start_column, end_line, end_column }` (no `span` nesting)
- nodes use `attributes` dict (not `metadata`), with `modifiers`, `parent_id`, `module_id`, `file_id`
- edges include `resolution_status`, `confidence`, `confidence_reason`, `candidate_ids`, `occurrence_count`, `diagnostic_ids`
- evidence uses `origin` enum value (`"source_ast"`), `observation_kind`, flat `location`, `explanation`
- Validated to round-trip through `graph_from_dict / graph_to_dict` without error:

```
Round-trip OK: graph_canonical_01 3 nodes, 2 edges, 2 evidence
Node location keys: ['end_column', 'end_line', 'path', 'source_unit_id', 'start_column', 'start_line']
Sample attributes: {'docstring': 'Service module implementation.'}
Evidence origin: source_ast
```

---

## R5 — Browser origin enforcement & delivery accuracy (CS-001/002)

**Finding:** Untrusted Origin returned 200. Expired command ack returned `[true, "delivered"]`.

**Corrections in `navigate.py`:**

- `_validate_trusted_origin(request)`: checks `Origin` and `Referer` headers; returns 403 `UNTRUSTED_ORIGIN` for non-loopback.
- `acknowledge_navigate_command`: propagates service `outcome` string as `status` (e.g. `"unknown_command"`, `"command_expired"`) — not hard-coded `"failed"`.
- `AcknowledgeResponse` schema extended with `reason: str | None = None`.

**Corrections in `editor.py`:** `_validate_trusted_origin` applied to registration endpoint.

**Corrections in `service.py`:** `acknowledge_navigation` checks `expires_at <= now`; returns `(False, "command_expired")` when expired.

**Probe results:**
```json
{
  "untrusted_origin_post_status": 403,
  "expired_command_ack": [false, "command_expired"]
}
```

---

## R6 — Quality gates & evidence (CS-003/CS-023)

### Test results — all gates green

| Suite | Result |
|---|---|
| Backend tests (no perf/slow) | **149 passed, 1 skipped; coverage 84.60%** ✅ |
| Thonny plugin tests | **44 passed** ✅ |
| mypy | **50 source files, no issues** ✅ |
| ruff lint | **All checks passed** ✅ |
| ruff format --check | **59 files already formatted** ✅ |
| Frontend tests (vitest) | **73 passed (7 files)** ✅ |
| Frontend ESLint | **Clean** ✅ |
| Frontend build (vite) | **Success — 465 kB bundle** ✅ |

### Formatter-only fixes applied

- 3 import-block `I001` errors in `service.py` (auto-fixed by `ruff check --fix`)
- 16 files reformatted by `ruff format` (plugin + backend sources)
- `# noqa: S310` repositioned to opening line of `urllib.request.Request(...)` in `llm_summary.py`

### Codex probe validation (runnable: `docs/verification/M1_review_probes.py`)

```json
{
  "two_registrations_share_session_token": false,
  "untrusted_origin_post_status": 403,
  "expired_command_ack": [false, "command_expired"],
  "junction_created": true,
  "retargeted_junction_post_status": 403,
  "retargeted_junction_pending": false
}
```

### Live smoke test output

```
Backend/Frontend health checks PASSED (HTTP 200)
Unique session token per registration: cap_Qv2isvKe_...
Navigate queued -> Thonny poll has_command=True (app.py line=4)
Execute: opened smoke_root2/app.py at line 4, col_offset 4
Two-root disambiguation: PASSED
Pending after ACK: has_command=False ✅
Traversal rejection: HTTP 403 ✅
Invalid session: HTTP 403 ✅
Scope mismatch: HTTP 403 ✅
```

> [!IMPORTANT]
> Physical GUI cursor observation remains headless (no live OS window). This gate is marked pending for real Thonny UI validation.

---

## Files changed in this correction pass

| File | Change | Finding |
|---|---|---|
| `backend/src/codestruct/jobs/service.py` | Path identity, unique tokens, bounded storage, expiry on ack | R1, R2, R5 |
| `backend/src/codestruct/api/routes/navigate.py` | Origin validation + ack status propagation fix | R5 |
| `backend/src/codestruct/api/routes/editor.py` | Origin validation | R5 |
| `thonny-plugin/thonnycontrib/codestruct/__init__.py` | Generation globals + resolved file store; ruff format | R2, R6 |
| `docs/frontend-contract/graph_slice.json` | Regenerated with canonical serializer schema | R3 |
| `backend/src/codestruct/analysis/llm_summary.py` | Repositioned `# noqa: S310` (formatter-only) | R6 |

*Ready for Codex review. Milestone 2 not started.*
