# Recognition Pipeline v3

This subsystem converts a numbered-score image into a Draft Score without changing the teaching engine.

```text
score image
→ deterministic recognition plan
→ one bounded visual-recognition round
→ per-region compact JSON
→ deterministic assembly + source coverage
→ score normalization
→ Draft Score
→ human review
→ Verified Score
```

Preferred CLI flow:

```bash
python3 scripts/animal_band.py prepare-score-recognition --score-image /path/to/score.png

# QwenWork writes one JSON file per returned region into /tmp/inference/
# e.g. header.json, system-01.json, system-02.json ...

python3 scripts/animal_band.py check-score-inference \
  --score-image /path/to/score.png \
  --recognition-plan /path/to/recognition-plan.json \
  --inference-dir /tmp/inference

python3 scripts/animal_band.py recognize-score \
  --score-image /path/to/score.png \
  --title "Song title" \
  --recognition-plan /path/to/recognition-plan.json \
  --inference-dir /tmp/inference
```

The planner may choose `whole_page`, `system_parallel`, or `system_highres_parallel`. The model cannot create its own crops or retry loop. Only source regions explicitly reported by the preflight gate may be read one additional time. Numeric recognition confidence is not used.

Legacy aggregate `--inference-input` remains readable for existing fixtures and migrations.
