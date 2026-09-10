# Score Contract

识谱固定经过 QwenWork 原生图片理解 → 结构化 inference JSON → Local CLI normalization → Draft Score。仓库运行时不调用模型 API、不读取 API Key。AI 输出永远不能直接成为 Verified Score。

正常流程通过 `open-score-review` 打开专业面板，逐小节完成 Draft → Reviewed → Verified。`score-status` 必须同时确认 Verified 与 Measure Alignment Ready。`verify-score` 仍作为聊天式简单修改和测试 fallback，只接受明确的 `confirmed=true`。乐谱被修改或重新确认后，Material Match、Learning Profile、Lesson Recipe 与 Readiness 必须失效并重新生成。

## Lyric Alignment

新的 QwenWork 识谱 inference 不再直接把整首歌词顺序写进 `notes[].lyric`。整张谱仍只做一次多模态识别，但每个小节独立输出 `lyricGroups[]`：

```json
{
  "number": 12,
  "notes": [
    {"degree": 5, "octave": 0, "beat": 0, "duration": 0.5, "rest": false, "confidence": 0.98},
    {"degree": 6, "octave": 0, "beat": 0.5, "duration": 0.5, "rest": false, "confidence": 0.97}
  ],
  "lyricGroups": [
    {"text": "我们", "noteIndex": 0, "spanNotes": 1, "confidence": 0.96},
    {"text": "爱", "noteIndex": 1, "spanNotes": 1, "confidence": 0.95}
  ]
}
```

`noteIndex` 在每个小节内从 `0` 重新开始，因此某个小节漏识或错识歌词不会通过索引机制把后续小节整体顺移。`text` 可以是一个字，也可以是多个字；`spanNotes > 1` 表示同一歌词组延续到多个连续音符。Local CLI normalization 再确定性编译为 Draft Score 现有的 `notes[].lyric`、`lyricSyllableId` 与 `lyricContinuation`。

`lyricsText` 只作为完整歌词参考文本，不能反向用于“第 i 个歌词字 = 第 i 个非休止音符”的顺序分配。视觉位置不明确时允许漏绑并给 warning，交给人工校谱修正。旧的 note-level lyric inference 仍兼容历史 fixture，但新识谱必须使用 measure-local `lyricGroups[]`。

## Measure Origin

如果谱面前面存在前奏、弱起、无歌词前导音，或教材图片并不是从正式第 1 小节开始，教师可以在 Score Review 中设置：

```json
{
  "measureOrigin": {
    "sourceMeasure": 5,
    "logicalMeasure": 1,
    "source": "teacher"
  }
}
```

`sourceMeasure` 是识谱结果中的原始谱面小节编号；`logicalMeasure` 当前固定为 `1`。`sourceMeasure` 之前的小节仍保留在 Verified Score 中，作为 lead-in / 前导段，但 `buildLessonSegments` 从该起点重新按“第 1 小节”组织课堂教学分段。内部 `startMeasure/endMeasure` 继续保存原始谱面编号，显示标签使用逻辑小节编号，避免破坏音符与原谱映射。

Measure Alignment 必须从教师设置的 Measure Origin 开始。教师修改 Measure Origin 后，旧的原曲校准不再视为 Ready，必须重新校准。

Measure Alignment 保存教师确认的真实原曲时间；不能用 BPM 猜测整首 MP3 时间。
