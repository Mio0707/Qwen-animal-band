---
name: animal-band-qwenwork
description: Turn a numbered-score image, with optional original song audio, into an interactive Animal Band music classroom through a local deterministic teaching engine. Use when a teacher asks QwenWork to prepare an Animal Band lesson.
---

# Animal Band × QwenWork

Keep curriculum decisions, score state, recipes, readiness, and exports inside the repository runtime. Do not edit workspace JSON directly and do not invent grade suitability in conversation. Prefer repository tools and deterministic code over extra AI reasoning or generated substitutes.

## Start

Run `python3 scripts/doctor.py --json` from this repository. If `ready` is false, run `python3 scripts/setup.py`. The repository runtime must never request, read, or store a model API key; use QwenWork's native reasoning for inference.

The desktop-safe command entry is `python3 scripts/animal_band.py <command> ...`. Use this launcher for all runtime state changes. It automatically resolves Node.js from `ANIMAL_BAND_NODE`, the inherited `PATH`, and common macOS / Windows desktop install locations so QwenWork does not depend on an interactive shell PATH.

When ready, ask the teacher one resource question before requesting files:

“你现在有哪些歌曲资源？
A. 只有简谱图片
B. 简谱图片 + 歌曲音频”

Use the answer only to decide which files to request. The runtime derives the actual capability mode from the files that are present:

- `SCORE_ONLY`: numbered-score image only.
- `SCORE_AUDIO`: numbered-score image + original song audio.

Do not require audio when the teacher only has a score.

## Prepare a lesson

Use only `python3 scripts/animal_band.py <command> ...` for state changes.

1. Require the numbered-score image. Require original song audio only for `SCORE_AUDIO`. Read [references/INFERENCE_CONTRACT.md](references/INFERENCE_CONTRACT.md), inspect the whole score once with QwenWork native multimodal reasoning, save the required score JSON to a temporary untracked file, then run:
   - score only: `recognize-score --score-image <image> --title <title> --inference-input <file>`
   - score + audio: add `--audio <audio>`.
   Do not run model/OCR once per measure or automatically repeat recognition. Never call a model API from the repository.
2. Read the command result's `resourceMode`, `availableActivities`, and `lockedActivities`. Say: “简谱识别完成。我已经把识别结果整理成可校对的简谱。请完成一次人工检查后再生成课堂。”
3. Run `open-score-review --song-id <id>`. Use only the returned `reviewUrl` for “检查乐谱”; never generate or substitute another review page. If the returned page cannot be opened, stop and report the blocker. The teacher checks every measure and selects singing segmentation. The panel also includes “设置小节起点”：如果谱面前面有前奏、弱起、无歌词前导音或教材截取段，教师可以把任意已识别谱面小节设为教学上的“第1小节”；此前的小节保留在 Verified Score 中，但作为 lead-in，不进入课堂教学分段和后续原曲小节对齐。In `SCORE_AUDIO`, the same panel also requires original-audio Measure Alignment, and that alignment must start from the teacher-defined first teaching measure. In `SCORE_ONLY`, audio calibration is skipped automatically. Use the same URL in an embedded web tray when supported; otherwise open it in the local browser.
4. After the teacher returns, run `score-status`.
   - Always require `verificationStatus = verified`.
   - Require `measureAlignmentReady = true` only when `measureAlignmentRequired = true`.
   For `SCORE_ONLY`, say: “✓ 简谱已确认。当前为简谱模式，现在开始分析：这首歌可以学什么。”
   For `SCORE_AUDIO`, say: “✓ 简谱已确认；✓ 原曲小节时间已校准。现在开始分析：这首歌可以学什么。”
5. `update-score`, `verify-score`, and `set-measure-alignment` remain available for small chat corrections and automated-test fallback, but never auto-verify AI output.
6. Run `analyze-song`. Explain what the deterministic Stage 1 curriculum match says the song can teach; do not add unsupported learning targets.
7. Ask the teacher to choose only from `availableActivities` returned by the runtime.
   - `SCORE_ONLY`: `rhythm_learning` 学节奏；`singing` 学演唱（钢琴音高 / 唱名）；`sticker_arrangement` 动物贴纸创作。
   - `SCORE_AUDIO`: all six activities are available: `listen`, `melody_trace`, `rhythm_learning`, `singing`, `ensemble`, `sticker_arrangement`.
   Do not offer locked activities as selectable options.
8. Run `generate-recipe`, summarize the plan, and wait for explicit confirmation before `confirm-recipe --confirmed true`.
9. If `sticker_arrangement` is selected, run `arrangement-context`, use QwenWork's native reasoning to produce the exact shared Arrangement Plan defined in [references/INFERENCE_CONTRACT.md](references/INFERENCE_CONTRACT.md), save it to a temporary untracked file, and run `import-arrangement-plan`.
10. Run `prepare-classroom`, then `check-readiness`. Do not bypass blockers. A score-only preparation can become READY without original audio or Measure Alignment when every selected activity is score-only compatible.
11. When readiness is true, run `export-classroom`. Ask QwenWork to preview or publish the returned export directory with its current Pages capability. Do not fabricate a public URL.

If Pages publishing is unavailable, provide the ZIP and the returned local preview command. The exported classroom is static: it must not call Qwen, Python, the CLI, or a classroom API while teaching.

## Upgrade from score-only to full mode

If a teacher who started in `SCORE_ONLY` later provides the original song audio, run:

`add-audio --song-id <id> --audio <audio>`

Then reopen the score review panel and complete Measure Alignment. Do not repeat score recognition or human score verification unless the score itself changed. After audio is added, `score-status` will report `SCORE_AUDIO` and unlock all six activities.

## Human review gates

- Score: `draft` → explicit teacher review → `verified`.
- Lesson recipe: `NOT_REVIEWED` → explicit teacher review → `REVIEWED`.
- Report failures concisely and preserve all validation checks.

Read [references/USER_FLOW.md](references/USER_FLOW.md) for teacher-facing labels, [references/RESOURCE_MODES.md](references/RESOURCE_MODES.md) for capability rules, and [references/SCORE_CONTRACT.md](references/SCORE_CONTRACT.md) when score-state details are needed.
