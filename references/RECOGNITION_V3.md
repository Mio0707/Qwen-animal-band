# Recognition Pipeline v3

## Goal

Provide one stable score-transcription subsystem for numbered-score songs across grades 1–6 without coupling recognition behavior to the teaching engine.

## Boundaries

```text
Score image
→ Recognition Plan
→ Visual transcription
→ Deterministic assembly
→ Source Coverage
→ Structural advisories
→ Draft Score
→ Human Review
→ Verified Score
```

Only the segment from image to Draft Score is changed by Recognition v3. `runtime/engine/`, curriculum matching, lesson recipes, classroom runtime and export are outside this subsystem.

## Structure-first invariant

Measure segmentation follows **visible barlines in the source image**, never recognized duration sums. The order is fixed:

```text
Music system image
→ visible barlines / measure boundaries
→ notes + octave marks + durations + lyrics inside each measure
→ duration validation advisory
→ human review
```

A duration error may create `MEASURE_DURATION_MISMATCH`, but it must not cause an automatic split/merge. Weak pickups, incomplete measures, long/short editorial measures and recognition mistakes therefore stay local instead of shifting every following measure. Planner barline candidates are advisory visual anchors only; the image remains authoritative.

## Why per-region JSON

A model reading several cropped systems must not also be responsible for merging, global measure numbering, or deciding which conflicting pass is correct. Each source region therefore produces one local JSON file. The repository merges those files in source order.

This gives three independent checks:

1. **Source coverage** — every required planned region exists and contains measures.
2. **Structural advisories** — barline-vs-measure count, meter/duration and malformed data can be flagged without letting duration redefine measure boundaries or pretending they prove page completeness.
3. **Human review** — the teacher remains the final authority for note, octave, duration and lyric correctness.

## Routing

- `whole_page_fast`: a single system, irregular page, or segmentation confidence too low.
- `system_parallel`: two or more reliably segmented textbook music systems.
- `system_highres_parallel`: dense multi-system score; same semantic contract, larger crop width.

No route crops by measure. Full systems retain slurs, octave dots, underlines and lyric context.

## Retry policy

Normal case: one recognition round.

A round may contain multiple parallel visual calls. If Source Coverage fails, only `repairRegionIds` may be read once more. The preflight command freezes hashes of already accepted region JSON files; changing them during targeted repair is a policy violation. If the second coverage check still fails, automatic recognition stops.

## Non-goals

- No numeric recognition confidence.
- No autonomous model crop loop.
- No model-side global merge.
- No inference API or API key inside the repository.
- No automatic verification; Draft Score always requires human review.
