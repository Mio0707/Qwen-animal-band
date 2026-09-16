# Animal Band × QwenWork

把教材中的一首歌变成一堂可以直接上课的互动音乐课。

## 安装

把这个 GitHub 仓库地址交给千问办公，让它安装 Animal Band Skill：

```text
https://github.com/Mio0707/Qwen-animal-band.git
```

首次运行会自动检查并初始化本地环境。之后先选择资源模式：只有简谱，或简谱 + 歌曲音频。若安装目录只读，运行时会自动把状态写入用户可写 workspace，不再要求临时 sudo/chown。

## 两种资源模式

### 简谱模式 `SCORE_ONLY`

只需要简谱图片，也可以完成：

- QwenWork 识谱 + 人工校谱
- 课程知识点分析
- 学节奏
- 学演唱基础版（钢琴音高 / 唱名）
- 动物贴纸创作

不要求歌曲原音频，也不要求 Measure Alignment。

### 完整模式 `SCORE_AUDIO`

提供简谱图片 + 原曲音频，在简谱模式能力之外解锁：

- 听一听，动一动
- 跟原曲画旋律
- 原曲跟唱
- 一起合奏
- 原曲小节时间校准
- 核谱页支持拆分/合并/插入/删除小节；结构修改后自动重编号并使旧的原曲小节校准失效
- 核谱页左侧原始简谱保持固定阅读宽度；右侧当前小节音符卡保持单行顺序，并在音符区域内独立横向滚动，不挤压原谱。

简谱模式后续可直接补充音频升级为完整模式，不需要重新识谱。

## Recognition Pipeline v3

识谱子系统与课程 Engine 解耦，目标是支持 1–6 年级不同复杂度的简谱输入。核心原则：

- “一轮识谱”指所有计划区域各读取一次，不等于必须整页只调用一次视觉模型。
- 检测到两个及以上可靠 music system 时按完整 system 并行读取；密集谱面自动提高 crop 分辨率；单 system 或布局不稳定时保守退回 whole-page。
- 每个 system 单独输出 JSON，本地代码负责合并与全局小节编号，避免模型跨区域对账。
- **小节线优先**：先按原谱中可见小节线确定小节结构，再识别每小节内的音高、时值与歌词；时值合计只做异常提示，绝不反向拆分/合并小节。
- Source Coverage 先确认没有漏 system，再做音乐结构检查。拍数自洽不能证明整页完整。
- 只允许缺失/结构损坏的区域做一次 targeted repair；视觉模糊直接进入人工核谱。
- 识谱阶段不使用数值 confidence。

## 用户流程

```text
安装 Skill
→ 选择资源：只有简谱 / 简谱 + 音频
→ Recognition Plan（整页 / music system 自适应）
→ QwenWork 单轮并行视觉识谱（每个区域只读一次）
→ 本地确定性合并 + Source Coverage + 结构校验
→ CLI 生成 Draft Score
→ 打开“简谱检查”专业面板
→ 人工校谱
→ 有音频时完成原曲时间校准
→ 返回千问
→ 课程分析
→ 从当前可用活动中选择
→ 教师确认课堂方案
→ 如选择动物贴纸创作，QwenWork 生成 Arrangement Plan
→ 静态课堂
```

六项课堂活动：听一听，动一动；画旋律；学节奏；学演唱；一起合奏；动物贴纸创作。系统会根据当前资源自动决定哪些活动可用。

只有简谱校对与有音频时的原曲时间校准需要专业操作面板，其余备课都在千问对话中完成。面板由一次性 Review Bridge 提供，空闲后自动退出；QwenWork Web 固定用网页应用/端口预览打开 `http://localhost:3000/`。Bridge 在根路径直接返回真实核谱 UI，并把短期 session token 注入页面内存，后续 API 与媒体请求显式携带 token；因此不依赖 302 跳转、跨站 iframe Cookie、带 token 的预览入口或仓库里的可预览 HTML。不能直接预览 `review/score/` 下的文件，不能额外建立反向代理，也不能退回命令行校谱。桌面环境可用临时端口直接打开返回的本地 URL。它不是长期产品 HTTP Server。

## 本地初始化

需要 Python 3.9+ 与 Node.js。识谱与 Arrangement AI 推理由 QwenWork 当前会话直接完成；本地运行时不调用模型 API，也不需要任何模型 API Key。

```bash
python3 scripts/setup.py
python3 scripts/doctor.py --json
```

QwenWork / Desktop 可能不会继承终端的 `PATH`。发行版会自动从 `ANIMAL_BAND_NODE`、当前 `PATH`、Homebrew、Volta、NVM、fnm、asdf 及常见 Windows Node.js 安装位置查找 Node，普通用户不需要手动配置环境变量。

## 技术边界

发行架构是 `Skill/QwenWork Inference + Recognition Pipeline v3 + Local CLI + Animal Band Engine + Static Classroom + Web Sampler`。QwenWork 只负责计划区域内的视觉转写；本地代码负责区域规划、合并、Source Coverage 与结构检查。多 system 页面采用 per-region JSON，模型不负责整首合并，也不能自行裁图/复核。专业 Engine 是课程判断与备课生成的唯一事实来源。课堂导出后不依赖服务器、Qwen、CLI、FluidSynth 或 MCP。

面向 QwenWork / 普通用户的本地命令入口：

```bash
python3 scripts/animal_band.py --help
```

`runtime/animal_band_cli.py` 是内部 canonical JSON CLI；桌面宿主应通过 `scripts/animal_band.py` 调用，以获得 Node 自动发现能力。

静态课堂位于当前可写 workspace 的 `exports/<preparationId>/`，也会生成对应 ZIP；`doctor --json` 会返回实际 workspace 路径。若客户端不能直接发布，可进入导出目录运行 `python3 -m http.server 4176` 预览。

## 许可提醒

公开或商业分发前请阅读 [LICENSES.md](LICENSES.md)。Web Sampler 的来源、MIT 许可与署名已经核验并随包保留。
