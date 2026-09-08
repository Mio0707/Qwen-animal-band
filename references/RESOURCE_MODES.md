# Resource Modes

Animal Band QwenWork Release supports two capability modes. The mode is derived from the resources that actually exist for a Song; it is not a free-form model decision.

## SCORE_ONLY

Required resource:

- numbered-score image

Available classroom activities:

- `rhythm_learning`
- `singing`
- `sticker_arrangement`

Rules:

- Score recognition still produces Draft only.
- Human score review is still mandatory.
- Measure Alignment is not required.
- Rhythm learning uses Verified Score, curriculum match and learning profile; its first three steps work without original audio.
- Singing uses piano pitch and solfege playback. Original-song playback is unavailable.
- Sticker arrangement uses Verified Score + QwenWork Arrangement Plan + deterministic four-track compiler + Web Sampler.
- `listen`, `melody_trace` and `ensemble` are locked until original audio is added.

## SCORE_AUDIO

Required resources:

- numbered-score image
- original song audio

Available classroom activities:

- `listen`
- `melody_trace`
- `rhythm_learning`
- `singing`
- `ensemble`
- `sticker_arrangement`

Rules:

- The Score Review panel also requires Measure Alignment before the normal full-mode flow continues.
- Original-song playback can be used by singing and rhythm extension experiences after alignment.
- Melody trace and ensemble require aligned original audio.

## Upgrade

A Song may upgrade from `SCORE_ONLY` to `SCORE_AUDIO` by adding original audio with:

```bash
python3 runtime/animal_band_cli.py add-audio --song-id <songId> --audio <path>
```

Adding/replacing audio invalidates old Measure Alignment and readiness, but does not invalidate the Verified Score itself. Reopen Score Review, complete alignment, then regenerate or update the lesson activity selection as needed.

## Capability principle

Product copy may describe two modes, but Readiness remains dependency-based. A preparation is READY when every selected activity has all of its required capabilities and every human review gate is satisfied. Original audio is never a global requirement for a score-only lesson.
