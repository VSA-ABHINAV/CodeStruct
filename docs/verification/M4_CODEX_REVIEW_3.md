# Codex Review 3 — Milestone 4 Corrections

**Date:** 2026-10-04
**Decision:** Changes required
**Reviewed commit:** `d1f34ee887ec66e33c435ece91184c3e5fac7bd5` (`fix(m4): safe fail-closed smoke harness, real UI actions, dense-graph verification, and cancellation lifecycle`)

## Independent checks

- Review started with a clean `main`; read-only `git ls-remote origin refs/heads/main` confirmed remote `main` matched the reviewed commit.
- `npm.cmd test -- --reporter=dot`: **10 files, 103 tests passed**.
- `npm.cmd run lint`: passed.
- `npm.cmd run build`: passed.
- Ruff check: passed. Ruff format check: 200 files already formatted.
- I did not rerun the M4 workflow harness because it still persists a token-bearing viewer URL to `session_info.json`; the prior review explicitly required keeping the capability only in process memory. The script also tests simulated layout rather than the product layout, so its current output cannot prove CS-007.

## Findings

1. **CS-006 credential must never be written to disk.** The Thonny helper writes `opened_urls[0]`, which contains `session_token`, into `session_info.json` and the parent later unlinks it. The end-of-run scan sees only post-deletion files and cannot prove it was never persisted. Transfer the URL/capability through an in-memory pipe or other non-persistent channel; scan after the run and make no token-bearing file at any point.
2. **CS-007 benchmark is not measuring CodeStruct layout.** The CDP script fetches a dense graph, then times `nodes.map(...)` with a synthetic grid position. It never invokes the app's `layoutGraph`, loads the dense analysis into the explorer, asserts the large-graph overview cap, or compares actual graph/table entity and edge identities. Existing `overviewGraph` filters by node kind and can still return an unbounded number of nodes; `layoutGraph` remains synchronous. Add a deterministic above-threshold end-to-end graph test that drives the real app/components, checks a defined bound and identity parity, and exercises retry in the UI. Benchmark the actual layout function and implement a safe bound or worker if measured runtime warrants it.
3. **CS-021 assertions remain incomplete.** The harness activates a Cancel-like button and waits for the word “cancelled” in a body-text prefix, but does not assert the button changed to disabled “Stopping…”, observe the `cancellation_requested` acknowledgement, assert the backend terminal state is exactly `cancelled`, or prove the frontend poller stopped. Extend the test to assert those specific state transitions and the user-visible live announcement; preserve a deliberately slow fixture so the cancel request cannot race with normal completion.
4. **CS-022 reduced-motion result is only an emulation check.** The harness asserts `matchMedia(...).matches` after emulation, but does not assert computed animation/transition behavior changes. It also does not report an actual screen-reader observation. Verify computed reduced-motion styles/behavior and label manual screen-reader/platform checks as pending if they are not performed.
5. **Smoke evidence must prove it ran against the processes it launched.** The script defines `is_port_in_use` but never uses it, starts services on fixed ports, and `wait_for_url` accepts any existing HTTP 200 response. Vite also lacks `--strictPort`. A preexisting service can therefore satisfy readiness while the newly launched process failed. Select free isolated ports, use strict binding, verify child processes remain alive, and confirm the unique test project/database nonce is served by the launched backend.
6. **Failure-safe cleanup and scope status.** The harness is now scoped to a unique temp directory and assertions generally fail closed. Keep it that way. The dense graph section and cancellation checks still overstate evidence in `M4.md`, the tracker, and audit; correct those claims and keep M4 **Changes required** until the specific gates above pass. No later milestone is authorized.

## Decision

The frontend suite, lint, build, and Ruff checks pass, but M4 is not accepted. The end-to-end harness was not run because it still writes the capability to a temporary file, and source inspection shows material evidence gaps for CS-007, CS-021, and CS-022. Correct these issues in a bounded M4 pass, rerun required tests and the safe real workflow, commit/push only M4 corrections, and stop for Codex review.
