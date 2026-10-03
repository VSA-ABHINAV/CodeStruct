# Known issues after Phase 12

Severity follows the project scale: Critical blocks safe use; High blocks a primary workflow or major scale/reliability objective; Medium materially harms usability/correct feedback; Low is localized polish. Status is Open unless noted.

| ID | Severity | Area | Reproduction and evidence | Impact | Recommended next owner |
|---|---|---|---|---|---|
| P12-007 | High · Fixed Phase 13 | Project selection | Reproduced from the hard-coded `sample` request. `GET /api/v1/projects`, alias validation, and the labeled selector now expose only safe capability metadata. | Fixed; tests cover discovery, no path leakage, duplicate aliases/locations, selector loading/empty/failure, and selected-ID submission. | Retain security review on configuration changes. |
| P12-003 | High · Fixed Phase 13 | Large-graph scalability | Reproduced: the client called unbounded graph then exhausted every cursor. It now requests `limit=1000` first and advances only through keyboard-accessible Load more. | Fixed for eager transfer; client virtualization and richer server slices remain future work. | Regression tests cover first bounded request, deterministic merge/dedup, cross-result rejection, and loaded totals. |
| P12-002 | Medium · Fixed Phase 13 | State truthfulness | Reproduced Empty graph during page fetch. A distinct Retrieving graph state is announced before the first bounded page. | Fixed for initial retrieval; page failures preserve loaded data. | Poller/component state regression coverage. |
| P12-004 | Medium · Fixed Phase 13 | Error recovery | Reproduced non-JSON Vite 5xx as malformed response. | Fixed: transport/non-JSON 5xx reports backend unavailable. | API-client regression and browser validation. |
| P12-001 | Medium · Fixed Phase 13 | Accessibility | Reproduced title `frontend`. | Fixed as `CodeStruct Architecture Explorer`. | Static regression plus real-browser title check. |
| P12-005 | Medium · Mitigated Phase 13 | Graph usability | Reproduced dense 96-node rendering. Warning/overview threshold lowered from 350/800 to 80/240 nodes/edges. | Safer default, but layout/aggregation research remains open. | Revalidate with users and representative graphs. |
| P12-008 | Medium | Cancellation evidence | Attempt to cancel local fixtures; they finish before a running Cancel action can be exercised in the UI. | Manual acceptance for perceived acknowledgement and terminal cancellation is incomplete. | Testability: provide a safe controlled-delay fixture/test mode, never production delay logic. |
| P12-006 | Low | Controls | Open a graph: custom Zoom/Fit/Reset controls and React Flow built-in controls are both visible. | Duplication adds keyboard stops and uncertainty. | UX/accessibility review after user testing. |

## Pending evidence, not confirmed defects

- Real screen-reader operation, complete keyboard traversal/focus restoration, 125%/200% zoom, light theme, forced colors, and reduced motion.
- Firefox, Safari, installed Chrome/Edge, macOS, and Linux workflows.
- Manual worker crash, timeout, queue saturation, expiry-during-retrieval, corrupt-cache, and read-only/disk-full recovery.
- Moderated usability sessions using [usability-study-protocol.md](usability-study-protocol.md).

No Critical defect was observed. No production change was made in Phase 12; these issues remain reproducible release inputs rather than silently fixed behavior.
