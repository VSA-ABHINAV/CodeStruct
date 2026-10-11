# Antigravity task: Milestone 5 corrections — Codex Review 1

Date: 2026-10-09. Repository: `D:\REP\Codestruct\Codestruct`.

Read `docs/verification/M5_CODEX_REVIEW_1.md`, `docs/verification/M5.md`, `PROCESS_TRACKER.md`, `docs/codestruct_audit.md`, and the technology summary at `D:\REP\# CodeStruct – Technology Summary.txt`. M5 remains **Changes required** at `1325bb3453214ae2f1472e676ebc1c461da5a962`. Work only on the three findings in Review 1 and their necessary tests/evidence. Preserve M1–M4 and do not begin M6.

## Required corrections

1. **CS-012: enforce runtime bounds and cancellation.** Replace same-process daemon-thread execution with a killable isolated process. Enforce the timeout and event/output limits; ensure timeout/cancellation leaves no target code running and cannot race process-global `sys.argv`/`sys.path`. Define terminal session status and diagnostic behavior. Add a deterministic regression proving a timed-out/cancelled target cannot perform a later side effect.
2. **CS-013/CS-014: do not attach ambiguous observations to the first candidate.** Preserve multiple candidate identities without assigning runtime counts or a canonical graph target to an arbitrary symbol. Add assertions for edge target/resolution and node stats when attribution remains ambiguous.
3. **CS-013: provide truthful timing evidence.** Measure per-event duration and instrumentation overhead with a documented method, or remove/rename unsupported metrics and amend API/report claims. Never report a hard-coded zero as measured overhead. Test positive measurement and unavailable/zero-call cases honestly.

## Required verification and stop condition

Run focused timeout/cancellation, tracer, merger, API, and persistence tests; full backend coverage; Thonny plugin tests; frontend tests/lint/build if affected; Ruff check/format; mypy; compilation; and `git diff --check`. Rerun `scripts/verify_m5_runtime.py` against an isolated database and record actual timing values, session persistence, merged graph provenance, and bounds/cancellation evidence in `docs/verification/M5.md`. Update this task, tracker, and audit to the current evidence. Commit the correction pass, verify repository state, then stop for Codex review. Do not begin M6.

## Launch prompt

<span style="color:green">&gt; 🟢 Read ANTIGRAVITY_TASK.md and docs/verification/M5_CODEX_REVIEW_1.md. Correct only these M5 findings: run opted-in target code in a killable isolated process with enforced timeout/event/output bounds and terminal cancellation, prove no target side effect occurs after timeout/cancellation, preserve ambiguous symbol candidates without assigning observations to the first candidate, and report measured per-event duration/overhead truthfully (or remove unsupported metrics and amend claims). Add focused deterministic regressions, run the required gates and the isolated real backend/API M5 workflow, record evidence in docs/verification/M5.md and PROCESS_TRACKER.md, update the audit, commit the correction pass, and stop for Codex review. Preserve M1–M4; do not begin M6.</span>
