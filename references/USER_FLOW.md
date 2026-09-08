# User Flow

1. 上传简谱图片和原曲音频。
2. QwenWork 在 Skill 会话中读取图片并生成结构化 inference JSON；Local CLI 将其规范化为 Draft Score，再打开专业“简谱检查”面板。
3. 教师逐小节校谱、选择演唱分段、校准原曲，并在面板完成 Reviewed → Verified。
4. 返回千问；`score-status` 确认乐谱和校准已完成。
5. Engine 按第一学段课程库分析歌曲。
6. 教师从六项活动中选择；Engine 决定底层教学材料。
7. Engine 生成课堂方案；教师明确确认。
8. 如选择动物贴纸创作，QwenWork 在 Skill 会话中生成共享 Arrangement Plan，Local CLI 校验后编译四轨 Event JSON。
9. Readiness 通过后导出 Static Classroom。
10. 使用 QwenWork Pages 预览或发布；不可用时交付 ZIP 和本地预览命令。

活动标签：`listen` 听一听，动一动；`melody_trace` 画旋律；`rhythm_learning` 学节奏；`singing` 学演唱；`ensemble` 一起合奏；`sticker_arrangement` 动物贴纸创作。
