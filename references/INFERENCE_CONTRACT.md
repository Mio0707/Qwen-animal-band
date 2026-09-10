# QwenWork Inference Contract

QwenWork performs AI inference in the active Skill conversation. Repository scripts only validate, normalize, persist and compile JSON. They must not call a model endpoint or request an API key.

## Score inference

Inspect the whole numbered-score image once and output one JSON object:

- `title`, `tonic`, `mode`, `meter: {beats, unit}`, optional `bpm`
- `lyricsText`, `confidence`, `warnings`
- `measures[]`, each with `number`, `notes[]`, `lyricGroups[]`
- each note: `degree`, `octave`, `beat`, `duration`, `rest`, `confidence`
- each lyric group: `text`, `noteIndex`, `spanNotes`, `confidence`

Rules:

1. `noteIndex` is zero-based inside the current measure and resets for every measure.
2. Bind lyrics by visual position in the score. Never distribute `lyricsText` sequentially across notes.
3. Multiple lyric characters on one note are valid: `text: "我们", spanNotes: 1`.
4. One lyric group across several notes is valid: `spanNotes > 1`.
5. If alignment is unclear, omit that group and add a warning; do not shift later lyrics.

Use degrees 1–7; rest is degree 0 with `rest=true`; middle octave is 0. Beats use quarter-note units and begin at 0 within each measure. Preserve the score as visibly notated; do not invent notes or rests just to fill the meter. Every measure must include `lyricGroups`, using `[]` when none is visible.

Example:

```json
{
  "number": 5,
  "notes": [
    {"degree": 5, "octave": 0, "beat": 0, "duration": 0.5, "rest": false, "confidence": 0.98},
    {"degree": 6, "octave": 0, "beat": 0.5, "duration": 0.5, "rest": false, "confidence": 0.97}
  ],
  "lyricGroups": [
    {"text": "我们", "noteIndex": 0, "spanNotes": 1, "confidence": 0.96},
    {"text": "爱", "noteIndex": 1, "spanNotes": 1, "confidence": 0.93}
  ]
}
```

The local normalizer deterministically compiles `lyricGroups` into the Draft Score's `notes[].lyric`, `lyricSyllableId`, and `lyricContinuation`. Legacy note-level lyric input remains supported only for old fixtures. This inference always becomes a draft.

Pass it to:

```text
recognize-score --inference-input <temporary-json>
```

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
