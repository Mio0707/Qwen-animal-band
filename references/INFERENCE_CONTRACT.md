# QwenWork Inference Contract

QwenWork performs both AI inference tasks in the active Skill conversation.
Repository scripts only validate, normalize, persist and compile JSON. They
must not call a model endpoint or request an API key.

## Score inference

Inspect the uploaded numbered-score image and output one JSON object with:

- `title`, `tonic`, `mode`, `meter: {beats, unit}`, optional `bpm`
- `lyricsText`, `confidence`, `warnings`
- `measures[]`, each with `number` and `notes[]`
- each note: `degree`, `octave`, `beat`, `duration`, `rest`, `lyric`,
  `lyricContinuation`, `confidence`

Rules: use degrees 1–7; rest is degree 0 with `rest=true`; middle octave is 0;
beats use quarter-note units and begin at 0 within each measure. For one lyric
syllable over several pitches, put the character on the first note and set
`lyricContinuation=true` with a null lyric on following notes. Never guess an
unclear lyric. This JSON is untrusted inference and always becomes a draft.

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
