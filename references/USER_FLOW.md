# User Flow

1. Skill 先询问资源情况：A 只有简谱；B 简谱 + 原曲音频。
2. `SCORE_ONLY` 只上传简谱图片；`SCORE_AUDIO` 上传简谱图片和原曲音频。
3. QwenWork 在 Skill 会话中读取简谱图片并生成结构化 inference JSON；Local CLI 将其规范化为 Draft Score，再打开专业“简谱检查”面板。
4. 教师逐小节校谱并选择演唱分段。仅在 `SCORE_AUDIO` 中校准原曲；`SCORE_ONLY` 自动跳过 Measure Alignment。
5. 教师在面板完成 Reviewed → Verified，返回千问；`score-status` 确认当前资源模式、乐谱状态和可用活动。
6. Engine 按第一学段课程库分析歌曲。
7. 教师只从当前 `availableActivities` 中选择；Engine 决定底层教学材料。
8. Engine 生成课堂方案；教师明确确认。
9. 如选择动物贴纸创作，QwenWork 在 Skill 会话中生成共享 Arrangement Plan，Local CLI 校验后编译四轨 Event JSON。
10. Readiness 按所选活动实际依赖检查。简谱模式只要所选活动均支持 `SCORE_ONLY`，无需原曲即可 READY。
11. Readiness 通过后导出 Static Classroom。
12. 使用 QwenWork Pages 预览或发布；不可用时交付 ZIP 和本地预览命令。

## 活动可用性

`SCORE_ONLY`：

- `rhythm_learning` 学节奏
- `singing` 学演唱（钢琴音高 / 唱名）
- `sticker_arrangement` 动物贴纸创作

`SCORE_AUDIO`：

- `listen` 听一听，动一动
- `melody_trace` 画旋律
- `rhythm_learning` 学节奏
- `singing` 学演唱
- `ensemble` 一起合奏
- `sticker_arrangement` 动物贴纸创作

## 模式升级

教师如果先以 `SCORE_ONLY` 开始，之后补充原曲音频，运行 `add-audio` 即升级为 `SCORE_AUDIO`。之后重新打开简谱检查面板完成 Measure Alignment，即可解锁完整活动；不需要重新识谱。
