# Animal Band × QwenWork

把教材中的一首歌变成一堂可以直接上课的互动音乐课。

## 安装

把这个 GitHub 仓库地址交给千问办公，让它安装 Animal Band Skill：

```text
https://github.com/Mio0707/Qwen-animal-band.git
```

首次运行会自动检查并初始化本地环境。随后上传简谱图片和歌曲音频，打开“简谱检查”专业面板完成人工校谱与原曲时间校准，再按对话提示生成课堂。

## 用户流程

```text
安装 Skill → 上传简谱与原曲 → QwenWork 原生推理 → CLI 生成识谱草稿 → 打开“简谱检查”
→ 人工校谱与原曲时间校准 → 返回千问 → 课程分析
→ 选择活动 → 教师确认课堂方案 → QwenWork Arrangement 推理 → 静态课堂
```

六项课堂活动：听一听，动一动；画旋律；学节奏；学演唱；一起合奏；动物贴纸创作。

只有简谱校对与原曲时间校准需要专业操作面板，其余备课都在千问对话中完成。面板由一次性本地 Review Bridge 提供，只监听 `127.0.0.1`，空闲后自动退出；它不是产品 HTTP Server。

## 本地初始化

需要 Python 3.9+ 与 Node.js。识谱与 Arrangement AI 推理由 QwenWork 当前会话直接完成；本地运行时不调用模型 API，也不需要任何模型 API Key。

```bash
python3 scripts/setup.py
python3 scripts/doctor.py --json
```

如 Node.js 不在 `PATH`，可设置 `ANIMAL_BAND_NODE` 指向 Node 可执行文件。

## 技术边界

发行架构是 `Skill/QwenWork Inference + Local CLI + Animal Band Engine + Static Classroom + Web Sampler`。QwenWork 只产出待校验的结构化推理；专业 Engine 是课程判断与备课生成的唯一事实来源。课堂导出后不依赖服务器、Qwen、CLI、FluidSynth 或 MCP。

本地命令入口：

```bash
python3 runtime/animal_band_cli.py --help
```

静态课堂位于 `workspace/exports/<preparationId>/`，也会生成对应 ZIP。若客户端不能直接发布，可进入导出目录运行 `python3 -m http.server 4176` 预览。

## 许可提醒

公开或商业分发前请阅读 [LICENSES.md](LICENSES.md)。Web Sampler 的来源、MIT 许可与署名已经核验并随包保留。
