# Product Boundary

本发行版只负责本地备课与静态课堂导出。架构固定为 Skill、Local CLI、专业 Engine、Static Classroom 与 Web Sampler。

不包含 MCP、仓库侧模型 API、API Key、数据库、域名、Electron、Desktop Player、长期 HTTP 产品服务器或 Teacher App 主入口。识谱与 Arrangement AI 推理由 QwenWork/Skill 层完成，本地 CLI 只校验和编译结构化结果。人工校谱可启动一次仅绑定 `127.0.0.1` 的短生命周期 Review Bridge；它只读写当前歌曲校谱数据。课堂运行时不调用 Qwen、Python、CLI 或 Engine。
