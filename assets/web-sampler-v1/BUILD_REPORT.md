# Animal Band Web Sampler V1 Build Report

- 构建时间: `2026-09-08T06:31:50.392086Z`
- FluidSynth 路径: `LOCAL_BUILD_TOOL_NOT_DISTRIBUTED`
- SoundFont 名称: `MuseScore_General.sf3`
- SoundFont SHA256: `5b85b6c2c61d10b2b91cddd41efcce7b25cd31c8271d511c73afafbef20b6fa3`
- ffmpeg 版本: `NOT AVAILABLE (LAME fallback used)`
- MP3 编码器: `LAME 64bits version 4.0 (https://lame.sourceforge.io)`
- 总 sample 数: 31
- dog sample 数: 5
- bear sample 数: 9
- cat sample 数: 7
- lion sample 数: 10
- MP3 总文件大小: 1727379 bytes
- ZIP 文件大小: 1740259 bytes

## QA

- 文件完整性: PASS
- sample-library.json: PASS
- MP3 解码: PASS (31/31)
- Duration: PASS
- Clipping: PASS
- Pitch coverage: PASS
- ZIP: PASS

## Warnings

- 未找到可正常运行的 ffmpeg；使用项目内 LAME 4.0 编码 128 kbps CBR MP3，并使用 mpg123 执行解码 QA。
- SoundFont 未附带可定位的许可证文件；公开或商业分发前需要人工许可证审查。

## Result

PASS
