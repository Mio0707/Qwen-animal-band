# Score Contract

识谱固定经过 QwenWork 原生图片理解 → 结构化 inference JSON → Local CLI normalization → Draft Score。仓库运行时不调用模型 API、不读取 API Key。AI 输出永远不能直接成为 Verified Score。

正常流程通过 `open-score-review` 打开专业面板，逐小节完成 Draft → Reviewed → Verified。`score-status` 必须同时确认 Verified 与 Measure Alignment Ready。`verify-score` 仍作为聊天式简单修改和测试 fallback，只接受明确的 `confirmed=true`。乐谱被修改或重新确认后，Material Match、Learning Profile、Lesson Recipe 与 Readiness 必须失效并重新生成。

Measure Alignment 保存教师确认的真实原曲时间；不能用 BPM 猜测整首 MP3 时间。
