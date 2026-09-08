# Score Contract

识谱固定经过 QwenWork 原生图片理解 → 结构化 inference JSON → Local CLI normalization → Draft Score。仓库运行时不调用模型 API、不读取 API Key。AI 输出永远不能直接成为 Verified Score。

正常流程通过 `open-score-review` 打开专业面板，逐小节完成 Draft → Reviewed → Verified。`score-status` 必须同时确认 Verified 与 Measure Alignment Ready。`verify-score` 仍作为聊天式简单修改和测试 fallback，只接受明确的 `confirmed=true`。乐谱被修改或重新确认后，Material Match、Learning Profile、Lesson Recipe 与 Readiness 必须失效并重新生成。

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
