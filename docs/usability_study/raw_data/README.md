# Raw Data Directory — CodeStruct Usability Study

This directory holds raw per-participant responses for the Phase 20 usability evaluation study.

## Format

Each response is a single JSON object on one line (JSON Lines format), as produced by
`docs/usability_study/questionnaire.html` (saved to browser localStorage). The human
researcher exports each participant's per-condition responses into a file here.

Example file (`P01_baseline.jsonl`):
```json
{"participantId":"P01","condition":"baseline","timestamp":"2026-11-08T08:00:00Z","sus":{"item1":4,"item2":2,"item3":5,"item4":1,"item5":4,"item6":3,"item7":5,"item8":2,"item9":4,"item10":1},"rubric":{"contentQuality":4,"presentationQuality":5,"usefulness":4},"comprehension":"The core animal models are Animal, Dog, and Cat; Zoo manages them; build_zoo and main orchestrate creation."}
{"participantId":"P01","condition":"advanced","timestamp":"2026-11-08T08:30:00Z","sus":{"item1":5,"item2":1,"item3":5,"item4":1,"item5":5,"item6":1,"item7":5,"item8":1,"item9":5,"item10":1},"rubric":{"contentQuality":5,"presentationQuality":5,"usefulness":5},"comprehension":"Core Animal Models, Animal Services, and Zoo Management cluster the symbols; the narrative summarizes the architecture."}
```

## How responses get here

1. Participant opens `questionnaire.html`, fills it out once per condition (baseline + advanced).
2. On submit, the response is saved to that browser's `localStorage` (offline-friendly).
3. The researcher copies each response out of localStorage (e.g., via browser DevTools
   Console: `localStorage.getItem('usability_responses')`) and pastes it as a JSON line
   into a file in this directory, named by participant and condition.
4. Once ≥5 participants have completed both conditions, run:
   `python docs/usability_study/score.py`
   to produce `docs/usability_study/results.md`.

## Privacy

Raw data may contain participant identifiers. Do not commit files containing PII to the
repository without consent. This directory is intended to be gitignored or handled per
your institution's data policy.
