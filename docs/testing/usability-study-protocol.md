# CodeStruct usability-study protocol

## Study goal

Evaluate whether representative users can select a safe project, understand analysis progress, find an architectural entity, interpret a relationship and its evidence, recover from partial/failing analysis, and choose a safe large-graph view without coaching.

## Participants

Recruit 5–8 participants across three profiles: Python developer new to the repository, maintainer familiar with architecture tools, and learner who understands modules/classes but not static-analysis terminology. Record experience bands, not names or employer data. Obtain consent before recording; do not collect analyzed proprietary source.

## Setup

Use an isolated local build and synthetic/sample projects. Provide keyboard/mouse and, for accessibility sessions, the participant's preferred assistive technology. Reset app, cache, viewport, and task fixture between sessions. The facilitator must not reveal target controls unless the participant is irrecoverably blocked.

## Tasks

1. Analyze the sample project and explain when the analysis is complete.
2. Find `get_user`, identify its containing entity, and explain why one call remains unresolved.
3. Filter to classes and inheritance, then restore the full graph.
4. Use the table alternative to find the same relationship and evidence.
5. Analyze a partial project, identify which failure occurred, and state whether other results are trustworthy.
6. Re-run unchanged input, explain the cache state, and deliberately refresh it.
7. Attempt an unsafe path and describe the recovery action.
8. Open a large result and choose a representation that remains usable.
9. Keyboard-only participants repeat search, result navigation, details, filters, view switching, and reset.

## Measures

- Task completion without help, with one hint, or failed.
- Time on task and first meaningful feedback latency.
- Wrong turns, repeated actions, and recovery success.
- Correct interpretation of resolved, unresolved, ambiguous, external, partial, and cached states.
- Confidence rating (1–5) and Single Ease Question (1–7) per task.
- Verbatim observations and accessibility barriers, with no source content in notes.

## Interview prompts

Ask what the user believes was analyzed, whether results are current, which facts are certain, what a diagnostic means, what they expect selection/refresh/cancel to do, and what would make the graph easier to navigate. Avoid leading questions such as “Was the filter easy?”

## Success criteria

At least 80% of participants should complete Tasks 1–7 without facilitator intervention; all participants must distinguish unresolved from resolved evidence; no critical safety misunderstanding is acceptable. Keyboard participants must complete the primary workflow without pointer input. These are proposed study criteria and were not measured in Phase 12 because no participants were recruited.

## Analysis and issue handling

Aggregate behavior by task and participant profile. Convert repeated or safety-relevant failures into reproducible issues using [known-issues.md](known-issues.md), but keep design suggestions separate from observations. A future session report must disclose participant count, configuration, exclusions, and deviations from this protocol.
