# QwenWork Score Inference Importer

The formal path is local and keyless:

```text
score image → QwenWork native inference → structured JSON
→ Local CLI normalization → Draft Score → Human Review
```

QwenWork creates the structured JSON described in
`references/INFERENCE_CONTRACT.md`. The repository never sends the image to a
model endpoint and never reads an API key.

```bash
python3 runtime/animal_band_cli.py recognize-score \
  --score-image /path/to/score.png \
  --audio /path/to/song.mp3 \
  --title "Song title" \
  --inference-input /path/to/qwenwork-score-inference.json
```

The imported result is always `draft`. A teacher must review the notes and
lyrics, select the singing teaching grouping, calibrate the original audio and
explicitly verify the score.
