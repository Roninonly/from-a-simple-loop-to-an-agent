# Agent V3 中间版本：内存会话记忆

这个快照保留加入 SQLite 前的版本，方便对比两种 Checkpointer。

- 使用 InMemorySaver 保存图状态。
- 使用 thread_id 区分会话。
- 输入 `/session 会话名` 切换会话。
- 默认会话为 `default-session`。
- 关闭程序后，所有会话记忆消失。
- 完整 V3 的持久化版本完成后另存为 `versions/v3/`。

在项目根目录，使用已安装快照依赖的环境运行：

```powershell
python .\versions\v3-memory\main.py
```

测试：在一个会话告诉模型名字，切换到另一个会话，最后切回来询问名字。

快照共用项目根目录的 `.env`，没有复制密钥或运行中的会话数据。
