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

### Recognition Pipeline v3

Recognition is a bounded transcription pipeline, not an open-ended agent task. **One recognition round means every planned visual region is read once; it does not mean the whole page must be one model call.** The model must never decide its own crop/retry strategy.

1. Require the numbered-score image. Require original song audio only for `SCORE_AUDIO`. Read [references/INFERENCE_CONTRACT.md](references/INFERENCE_CONTRACT.md).
   1. Run `prepare-score-recognition --score-image <image>`. The deterministic planner returns `recognitionPlan`, `strategy`, `profile`, and ordered `recognitionInputs`.
   2. Follow the plan exactly:
      - `whole_page`: read the returned `whole-page` image once and save `whole-page.json`.
      - `music_systems`: read the optional `header` plus **all required system regions once in one parallel round**. Save one independent JSON file per region: `header.json`, `system-01.json`, `system-02.json`, etc. Do not ask the model to merge systems.
   3. For every system result use the compact local schema from the inference contract. **Measure boundaries are structure, not a duration calculation:** first follow the barlines visibly printed in the source from left to right, then transcribe notes/durations/lyrics inside each resulting measure. Never split or merge measures merely because recognized durations do or do not add up to the meter. `barlineCandidates*` from the deterministic planner are advisory visual anchors only; confirm them against the image. Do not emit numeric recognition confidence. If a symbol or boundary is unclear, use `u` / warnings and continue to human review.
   4. Run `check-score-inference --score-image <image> --recognition-plan <plan> --inference-dir <dir>`. This is the source-coverage gate.
      - If it passes, continue immediately.
      - If it returns `SCORE_SOURCE_COVERAGE_INCOMPLETE`, re-read **only** `repairRegionIds`, at most once per region, replace those JSON files, and run the check once more.
      - Do not repair merely because a note/lyric is ambiguous, a duration advisory appears, or the model wants extra reassurance. Those cases go to human review. A duration mismatch must never trigger automatic measure repartitioning.
      - Never rerun already accepted regions, never split by measure, never create ad-hoc crops, never perform cross-check loops.
   5. Run `recognize-score --score-image <image> --title <title> --recognition-plan <plan> --inference-dir <dir>`; add `--audio <audio>` for `SCORE_AUDIO`. The repository deterministically assembles regions, globally numbers measures, expands compact notes, and writes the Draft Score.

The only supported compatibility path is legacy `--inference-input <aggregate-json>`; new recognition must use the per-region directory workflow above. Source coverage means every planned source region was transcribed. A measure-duration check can detect an internal anomaly but **never proves the page is complete**.

2. Read the command result's `resourceMode`, `availableActivities`, and `lockedActivities`. Say: “简谱识别完成。我已经把识别结果整理成可校对的简谱。请完成一次人工检查后再生成课堂。”
3. Run `open-score-review --song-id <id> --port 3000` in QwenWork Web / DingTalk. **Do not preview any file from `review/score/` directly, do not invent a replacement page, do not create a reverse proxy, and do not replace the visual review with command-line/manual text review.** The bridge itself binds the preview port.
   - The command returns `previewUrl`. In QwenWork Web / DingTalk, immediately call the webpage-app / server-port preview tool with **that exact URL**: `http://localhost:3000/`. Do not use `127.0.0.1`, do not append a path/query, and do not open a repository HTML/TMPL file. The bridge root `/` directly serves the real review UI and injects a short-lived session token into page memory; protected API/media requests carry that token explicitly. **The QwenWork preview does not depend on redirects or cookies.**
   - Do not send the teacher a review-complete message until the webpage-app preview has actually opened successfully.
   - In a desktop/local environment, run `open-score-review --song-id <id> --port 0` and open the returned `reviewUrl` directly.
   - If the exact `previewUrl` cannot be opened or the root preview fails, stop and report `REVIEW_UI_UNAVAILABLE`. Do not fall back to a static file preview, a tokenized URL, a proxy, or chat/CLI score correction.
   The teacher checks every measure and selects singing segmentation. The panel supports **measure-structure repair**: if recognition misses or invents a barline, the teacher can split a measure between notes, merge with the previous/next measure, insert an empty measure, or delete a measure. Structural edits deterministically renumber following measures, clear per-measure confirmation, invalidate stale original-audio Measure Alignment, and require review again. The panel also includes “设置小节起点”：如果谱面前面有前奏、弱起、无歌词前导音或教材截取段，教师可以把任意已识别谱面小节设为教学上的“第1小节”；此前的小节保留在 Verified Score 中，但作为 lead-in，不进入课堂教学分段和后续原曲小节对齐。In `SCORE_AUDIO`, the same panel also requires original-audio Measure Alignment, and that alignment must start from the teacher-defined first teaching measure. In `SCORE_ONLY`, audio calibration is skipped automatically.
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
