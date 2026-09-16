# QwenWork Inference Contract

QwenWork performs AI inference in the active Skill conversation. Repository scripts only plan visual regions, validate, merge, normalize, persist and compile results. They must not call a model endpoint or request an API key.

## Score inference — Recognition Pipeline v3

This step is **visual transcription, not teaching analysis**. The repository chooses the visual plan before recognition. The model must not invent crops, retries, or cross-check loops.

Run:

```text
prepare-score-recognition --score-image <image>
```

Read `recognitionPlan`, `strategy`, `profile`, `recognitionInputs`, and `policy`.

### Core rules

**One recognition round = each planned region is read once.** A score with seven planned systems may use seven parallel visual reads; that is still one recognition round. Do not turn “one round” into one overloaded whole-page call.

**Measure boundaries are visual structure.** Read the printed barlines first, from left to right, and create measures from those visible boundaries. Only after the measure structure is fixed should notes, durations and lyrics be transcribed inside each measure. **Never derive, split, merge or move a measure boundary from duration sums or meter arithmetic.** Duration is a validation signal after transcription, not a segmentation signal. If a barline is visually ambiguous, preserve the best visible structure and add a warning for human review.

### A. `whole_page`

Read only the returned `whole-page` image once. Save exactly `whole-page.json`:

```json
{
  "schema": "animal-band-score-compact-v1",
  "title": "歌曲名",
  "tonic": "C",
  "mode": "major",
  "meter": "2/4",
  "bpm": null,
  "measures": [
    {"p": false, "x": [[5,0,0.5],[6,0,0.5],[0,0,1]], "l": [["祖",0,1],["国",1,1]], "u": [], "w": []}
  ],
  "warnings": []
}
```

Do not create extra crops. If a symbol is unclear, use `u` or `w` and leave final correction to human review.

### B. `music_systems`

The planner has already created complete horizontal music-system crops with safe padding. Read all required `system-*` regions once in one parallel round. The optional header can be read in the same round.

Do **not** ask the model to merge systems. Save independent files in one temporary inference directory.

Optional `header.json`:

```json
{
  "schema": "animal-band-score-header-v3",
  "regionId": "header",
  "title": "歌曲名",
  "tonic": "C",
  "mode": "major",
  "meter": "2/4",
  "bpm": null,
  "warnings": []
}
```

Each required system must be saved as `system-XX.json`:

```json
{
  "schema": "animal-band-score-region-v3",
  "regionId": "system-01",
  "systemIndex": 1,
  "measures": [
    {"p": false, "x": [[5,0,0.5],[6,0,0.5]], "l": [["祖",0,1],["国",1,1]], "u": [], "w": []}
  ],
  "warnings": []
}
```

Rules:

1. Produce one file for every required `system-*` region returned by the plan.
2. Keep the full music system intact. Never crop by measure. Within that full-system image, **identify visible barlines before reading durations** and preserve their left-to-right boundaries exactly.
3. Planner fields `barlineCandidatesSourceX` / `barlineCandidatesNormalized` are advisory anchors, not commands. Use them to look at likely barlines, but the source image is authoritative.
4. Do not create a new measure boundary because accumulated durations reach the meter. Do not merge adjacent visible measures because durations appear short/long. A wrong duration must remain a duration problem, not become a measure-structure problem.
5. Do not globally number measures. Local files preserve source order; deterministic code assigns global measure numbers.
6. If a symbol, lyric, or barline is unclear, use `u` / `w`; ambiguity does not justify another visual pass.
7. Do not emit numeric recognition confidence at note, lyric, measure, region, or score level.
8. Do not compare one crop against another to “prove” correctness. Coverage is checked by code and correctness is finalized by human review.

After the first round run:

```text
check-score-inference \
  --score-image <image> \
  --recognition-plan <recognition-plan.json> \
  --inference-dir <dir>
```

If the command passes, recognition is complete. If it returns `SCORE_SOURCE_COVERAGE_INCOMPLETE`, read only `repairRegionIds` once more, replace those files, and run the check once more. Never rerun accepted regions. A duration mismatch or visual ambiguity is advisory and does not trigger repair.

Then run:

```text
recognize-score \
  --score-image <image> \
  --title <title> \
  --recognition-plan <recognition-plan.json> \
  --inference-dir <dir>
```

Add `--audio <audio>` when original audio exists.

### Compact note fields

- `p`: pickup flag; omit or `false` normally.
- `x`: notes. Default tuple is `[degree, octave, duration]`.
  - `degree`: `1–7`; rest is `0`.
  - `octave`: middle `0`, upper `1`, lower `-1`.
  - `duration`: quarter-note units (`1` = quarter, `0.5` = eighth, `2` = half).
  - Notes are sequential by default. Add a fourth value `[degree, octave, duration, beat]` only when a non-sequential onset is visibly required.
- `l`: measure-local lyric groups `[text, noteIndex, spanNotes]`; `noteIndex` starts from `0` inside that measure.
- `u`: optional zero-based note indexes that are visually uncertain.
- `w`: optional short warnings.

General transcription rules:

1. Bind lyrics by visual position. Never distribute a full lyric string sequentially across the whole song.
2. Multiple characters on one note are valid: `["我们",0,1]`.
3. One lyric group over several notes is valid: `["啊",2,3]`.
4. If lyric alignment is unclear, omit that group and add a warning; do not shift later lyrics.
5. Preserve what is visibly notated. Do not invent notes/rests merely to make the meter add up.
6. Preserve visible barlines even when the recognized duration total is inconsistent with the meter. Mark the measure with `w`, e.g. `"时值合计与拍号不一致，请人工核对"`; never repartition it automatically.
7. Do not output prose around the JSON.
8. Do not perform teaching analysis during recognition.
9. Measure-duration consistency validates note transcription only; it never defines measure boundaries and never proves the whole page was covered.

The local assembler verifies planned source coverage, merges region files, assigns global source order, and the normalizer calculates beat positions, pitch names, MIDI numbers and frequencies. Human score review is mandatory before any course analysis.

## Arrangement inference

After the score and lesson recipe are human verified, run `arrangement-context --song-id <id>`. Follow its prompt and return exactly:

```json
{
  "harmony": [{"measure": 1, "degree": 1, "quality": "major"}],
  "measurePlans": [{"measure": 1, "drums": "light", "keys": "hold", "bass": "root", "sax": "melody"}],
  "notes": []
}
```

Both arrays must cover every measure exactly once. Degrees are limited to 1/4/5/6; quality to major/minor; role values to those stated in the generated context. Save the JSON in a temporary untracked file and pass it to:

```text
import-arrangement-plan --song-id <id> --plan-json <temporary-json>
```

The local compiler preserves the verified melody, BPM, meter and measure boundaries while producing four Event JSON tracks.
