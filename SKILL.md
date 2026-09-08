---
name: animal-band-qwenwork
description: Turn a numbered-score image and song audio into an interactive Animal Band music classroom through a local deterministic teaching engine. Use when a teacher asks QwenWork to prepare an Animal Band lesson.
---

# Animal Band × QwenWork

Keep curriculum decisions, score state, recipes, readiness, and exports inside the repository runtime. Do not edit workspace JSON directly and do not invent grade suitability in conversation.

## Start

Run `python3 scripts/doctor.py --json` from this repository. If `ready` is false, run `python3 scripts/setup.py`. The repository runtime must never request, read, or store a model API key; use QwenWork's native reasoning for inference.

When ready, say: “Animal Band 已准备完成。请上传简谱图片和歌曲音频。”

## Prepare a lesson

Use only `python3 runtime/animal_band_cli.py <command> ...` for state changes.

1. Require both the numbered-score image and original song audio. Read [references/INFERENCE_CONTRACT.md](references/INFERENCE_CONTRACT.md), inspect the uploaded score image with QwenWork's native multimodal reasoning, save only the required score JSON to a temporary untracked file, then run `recognize-score --inference-input <file>`. Never call a model API from the repository. Say: “简谱识别完成。我已经把识别结果整理成可校对的简谱。请完成一次人工检查后再生成课堂。”
2. Run `open-score-review --song-id <id>` and provide or open the returned “检查乐谱” URL. The teacher uses this one professional panel to check every measure, select singing segmentation, calibrate the real original-audio interval, mark Reviewed, and finally verify the score. Use the same URL in an embedded web tray when supported; otherwise open it in the local browser.
3. After the teacher returns, run `score-status`. Continue only when `verificationStatus` is `verified` and `measureAlignmentReady` is true. Then say: “✓ 简谱已确认；✓ 原曲小节时间已校准。现在开始分析：这首歌可以学什么。”
4. `update-score`, `verify-score`, and `set-measure-alignment` remain available for small chat corrections and automated-test fallback, but never auto-verify AI output.
5. Run `analyze-song`. Explain what the deterministic Stage 1 curriculum match says the song can teach; do not add unsupported learning targets.
6. Ask the teacher to choose one or more activities: `listen`, `melody_trace`, `rhythm_learning`, `singing`, `ensemble`, `sticker_arrangement`.
7. Run `generate-recipe`, summarize the plan, and wait for explicit confirmation before `confirm-recipe --confirmed true`.
8. If `sticker_arrangement` is selected, run `arrangement-context`, use QwenWork's native reasoning to produce the exact shared Arrangement Plan defined in [references/INFERENCE_CONTRACT.md](references/INFERENCE_CONTRACT.md), save it to a temporary untracked file, and run `import-arrangement-plan`. Then run `prepare-classroom` and `check-readiness`. Do not bypass blockers.
9. When readiness is true, run `export-classroom`. Ask QwenWork to preview or publish the returned export directory with its current Pages capability. Do not fabricate a public URL.

If Pages publishing is unavailable, provide the ZIP and the returned local preview command. The exported classroom is static: it must not call Qwen, Python, the CLI, or a classroom API while teaching.

## Human review gates

- Score: `draft` → explicit teacher review → `verified`.
- Lesson recipe: `NOT_REVIEWED` → explicit teacher review → `REVIEWED`.
- Report failures concisely and preserve all validation checks.

Read [references/USER_FLOW.md](references/USER_FLOW.md) for teacher-facing labels and [references/SCORE_CONTRACT.md](references/SCORE_CONTRACT.md) when score-state details are needed.
