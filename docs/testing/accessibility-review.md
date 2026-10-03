# Phase 12 accessibility review

## Scope and method

The review combined a live browser accessibility-tree/keyboard inspection with Phase 11 role-based and axe automation. Automated checks are partial evidence and do not establish WCAG conformance. A real screen reader, browser zoom, light-theme emulation, and reduced-motion emulation were unavailable, so WCAG 2.2 AA remains **not certified**.

## Observed passes

- The page declares `lang="en"`; primary form controls have accessible names; buttons use semantic elements.
- Status/error regions were exposed, and validation failures were discoverable as alerts.
- Keyboard Tab and Enter submitted an analysis; no focus trap was encountered in tested paths.
- Search provides count/status text and Previous/Next controls; filter controls expose labels and reset.
- The accessible table represented every loaded node and edge and provided keyboard-operable inspect actions.
- Relationship meaning uses labels and solid/dashed/dotted patterns in addition to color.
- Source paths and diagnostics are text, not raw HTML; unresolved relationships remain named as unresolved.
- At 390 CSS pixels the document had no horizontal page overflow and controls remained present.
- Dark-theme sampled CSS colors met AA for normal text: body `#9ca3af` on `#16171d` approximately 7.04:1, heading `#f3f4f6` approximately 16.25:1, accent `#c084fc` approximately 6.77:1.

## Findings

| ID | Severity | WCAG | Finding | Evidence / recommendation |
|---|---|---|---|---|
| P12-001 | Medium | 2.4.2 Page Titled | Browser title is `frontend`, not CodeStruct or task-specific. | Set an informative product title and add a component/static assertion. |
| P12-002 | Medium | 4.1.3 Status Messages | During oversized graph retrieval the completed job is temporarily announced/presented as Empty graph. | Expose a distinct graph-retrieval/loading state and announce returned/total progress. |
| P12-005 | Medium | 1.4.10 Reflow / 2.4.11 Focus Not Obscured (risk) | Dense 96-node visual graph is difficult to scan even at wide viewport. | Lower/adapt the canvas threshold and default to aggregation/table when label density exceeds a measured limit. |
| P12-006 | Low | 2.4.6 Headings and Labels | Two sets of graph view controls are visible: product controls and React Flow built-ins. | Clarify labels/grouping or remove duplication after accessibility testing. |

## Keyboard and focus evidence

Initial focus order reached the relative-path input then Analyze Project. Enter activated submission. Native toolbar, search, filter, and table controls are exposed as buttons/inputs. React Flow nodes are not a complete keyboard inspection surface, making the table alternative essential. Full traversal, focus restoration after errors/panel close, selection announcement, and graph pan/zoom from keyboard require a dedicated real-user session.

## Screen-reader protocol (pending)

Run NVDA + Firefox or Chrome on Windows, VoiceOver + Safari on macOS, and a documented Linux combination. Verify page title, landmark navigation, form instructions, progress announcements without repetition, result counts, error recovery, search-result movement, selection/details association, diagnostics, and table relationships. Record speech output summaries, not audio or private paths.

## Visual and motion protocol (pending)

Test light and dark modes, Windows high contrast/forced colors, 125% and 200% browser zoom, text spacing, visible focus, unresolved/warning/error cues, and `prefers-reduced-motion`. Verify contrast for every state with computed foreground/background pairs; the three sampled dark variables above are not a complete contrast audit.

## Conclusion

The accessible table and semantic control structure provide a promising baseline, but open manual evidence and the misleading large-graph status prevent an accessibility release claim.
