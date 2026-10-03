# Phase 12 cross-platform matrix

## Support evidence

| Platform / browser | Startup | Spawned worker | SQLite/restart | Path security | UI workflow | Accessibility | Result |
|---|---|---|---|---|---|---|---|
| Windows + Codex in-app Chromium | Observed | Observed through v1 analysis | Cache hit observed; destructive recovery not repeated manually | Traversal/missing path observed | Core, partial, cache, large, responsive observed | Partial keyboard/tree/dark review | Partial pass |
| Windows + Chrome | Not run | Not run | Not run | Automated Windows coverage only | Not run | Not run | Pending |
| Windows + Edge | Not run | Not run | Not run | Automated Windows coverage only | Not run | Not run | Pending |
| Windows + Firefox | Not run | Not run | Not run | Automated Windows coverage only | Not run | Not run | Pending |
| macOS + Safari/Chrome | CI/configuration evidence only | Not observed | Not observed | Symlink/case semantics not observed | Not observed | VoiceOver pending | Pending |
| Linux + Firefox/Chrome | CI/configuration evidence only | Not observed | Not observed | Symlink/permission semantics not observed | Not observed | Screen reader pending | Pending |

## Required platform smoke

Each supported release platform must run: documented install/start from repository root and another working directory; v1 sample analysis; real spawned-process completion/cancellation/shutdown; SQLite cache/restart; invalid, traversal, symlink/junction, case, alternate-separator and permission paths; partial parse; frontend search/filter/details/table; and cleanup verification.

## Platform risks

- Windows junction creation and denial behavior depends on privileges and filesystem configuration.
- macOS default case-insensitive filesystems and Linux case-sensitive filesystems may expose different identity/collision behavior.
- Spawn initialization and shutdown differ across platforms; passing unit tests does not replace an actual process smoke.
- Safari/VoiceOver and Firefox accessibility trees can differ from Chromium.
- The current frontend hard-codes authorized-root ID `sample`; deployments whose configured capability ID differs cannot use the primary UI (`P12-007`).

## Release gate

`NFR-PLAT-001` remains open until the agreed smoke/security suite produces real results on Windows, macOS, and Linux. Phase 12 observed only one Windows Chromium-derived browser surface.
