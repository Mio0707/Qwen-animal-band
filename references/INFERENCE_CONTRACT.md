# QwenWork Inference Contract

QwenWork performs both AI inference tasks in the active Skill conversation.
Repository scripts only validate, normalize, persist and compile JSON. They
must not call a model endpoint or request an API key.

## Score inference

Inspect the uploaded numbered-score image **once for the whole score** and output
one JSON object. Do not make one model/OCR call per measure. The inference should
be fast enough for interactive lesson preparation; uncertain local regions are
left for human review instead of automatically triggering repeated recognition.

Output:

- `title`, `tonic`, `mode`, `meter: {beats, unit}`, optional `bpm`
- `lyricsText`, `confidence`, `warnings`
- `measures[]`, each with `number`, `notes[]`, and `lyricGroups[]`
- each note: `degree`, `octave`, `beat`, `duration`, `rest`, `confidence`
- each lyric group: `text`, `noteIndex`, `spanNotes`, `confidence`

### Music rules

Use degrees 1–7; rest is degree 0 with `rest=true`; middle octave is 0. Beats use
quarter-note units and begin at 0 within each measure. A measure may contain fewer
or more beats than the meter suggests (for example pickup, lead-in, incomplete or
source-specific measures); preserve what is visibly notated and do not invent
notes or rests merely to fill the meter.

### Measure-local lyric alignment

`lyricGroups` is the source of truth for inferred lyric-to-note alignment. Treat
every measure as an independent coordinate frame:

- `noteIndex` is **zero-based inside the current measure** and resets to `0` for
  every new measure.
- Determine `noteIndex` from the lyric's visual horizontal position under the
  numbered score. Never distribute `lyricsText` sequentially across all notes.
- `spanNotes` is the number of consecutive pitched note entries in this measure
  that belong to the same lyric group. It must be at least `1`.
- One lyric on one note: `{ "text": "我", "noteIndex": 0, "spanNotes": 1 }`.
- One note carrying multiple lyric characters is valid: `{ "text": "我们", "noteIndex": 0, "spanNotes": 1 }`.
- One lyric character/group stretched across several notes: `{ "text": "我", "noteIndex": 0, "spanNotes": 3 }`.
- Do not create overlapping lyric groups.
- Do not bind a lyric group to a rest.
- If the visual lyric-to-note position is unclear, omit that group and add a
  warning. Prefer one missing lyric over shifting later lyrics.
- A wrong or missing lyric in one measure must not cause any index shift in later
  measures. At every barline and every new score line, re-anchor visually.
- `lyricsText` is only the recognized full lyric text for reference. It must
  never be used as `lyric i -> non-rest note i` assignment input.
- Every measure must include `lyricGroups`, using `[]` when no lyric is visibly
  attached to that measure.

Example:

```json
{
  "number": 5,
  "notes": [
    {"degree": 5, "octave": 0, "beat": 0, "duration": 0.5, "rest": false, "confidence": 0.98},
    {"degree": 6, "octave": 0, "beat": 0.5, "duration": 0.5, "rest": false, "confidence": 0.97},
    {"degree": 5, "octave": 0, "beat": 1, "duration": 1, "rest": false, "confidence": 0.96}
  ],
  "lyricGroups": [
    {"text": "我们", "noteIndex": 0, "spanNotes": 1, "confidence": 0.96},
    {"text": "爱", "noteIndex": 1, "spanNotes": 2, "confidence": 0.93}
  ]
}
```

The local normalizer deterministically compiles `lyricGroups` into the Draft
Score's existing `notes[].lyric`, `lyricSyllableId`, and
`lyricContinuation` fields. Legacy inference JSON that has note-level `lyric`
fields and no `lyricGroups` remains supported for old fixtures, but new QwenWork
inference must use `lyricGroups`.

This JSON is untrusted inference and always becomes a draft.

Pass it to:

```text
recognize-score --inference-input <temporary-json>
```

## Arrangement inference

After the score and lesson recipe are human verified, run
`arrangement-context --song-id <id>`. Follow its prompt and return exactly:

```json
{
  "harmony": [{"measure": 1, "degree": 1, "quality": "major"}],
  "measurePlans": [{"measure": 1, "drums": "light", "keys": "hold", "bass": "root", "sax": "melody"}],
  "notes": []
}
```

Both arrays must cover every measure exactly once. Degrees are limited to
1/4/5/6; quality to major/minor; role values to those stated in the generated
context. Save the JSON in a temporary untracked file and pass it to:

```text
import-arrangement-plan --song-id <id> --plan-json <temporary-json>
```

The local compiler preserves the verified melody, BPM, meter and measure
boundaries while producing four Event JSON tracks.
