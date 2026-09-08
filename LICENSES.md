# Licenses and Redistribution Status

## Animal Band code

Animal Band 自有代码由仓库权利人保留权利。目标 GitHub 仓库应补充明确的开源或专有许可文本后再对外授权使用。

## Web Sampler V1

31 个 MP3 样本由本地构建流程生成。构建与检测记录见 `assets/web-sampler-v1/BUILD_REPORT.md`。

## MuseScore_General rendering source

Sampler 由 `MuseScore_General.sf3` 0.2.0 渲染。构建记录中的 SHA256
`5b85b6c2c61d10b2b91cddd41efcce7b25cd31c8271d511c73afafbef20b6fa3`
与 MuseScore 官方镜像中的文件完全一致。SoundFont 本体、FluidSynth 和任何
SoundFont 安装文件均未进入本仓库。

MuseScore 官方随附许可将 MuseScore_General 以 MIT License 发布，允许使用、
修改与分发，但要求保留版权声明和许可文本。本仓库在
`assets/web-sampler-v1/LICENSE.md` 中保留完整声明与致谢。

状态：

```text
PASS
```

## User content

用户上传的歌曲、教材图片、备课数据和课堂导出位于被 `.gitignore` 排除的 `workspace/` 子目录，不应提交到仓库。
