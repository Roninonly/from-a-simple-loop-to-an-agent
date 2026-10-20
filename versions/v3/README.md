# Agent V3：Memory Agent

这个版本在 V2 的 LangGraph Agent 基础上，加入按会话保存和恢复的 SQLite 记忆。

## 已完成的能力

- 使用 Checkpointer 保存和恢复完整图状态。
- 使用 thread_id 区分会话，默认会话为 default-session。
- 输入 /session 会话名 切换会话，切换命令不会提交给模型。
- 每轮只向图提交新消息，历史由 Checkpointer 恢复。
- 没有历史的会话自动加入系统提示词，已有会话不会重复加入。
- SQLite 数据库保存用户消息、模型消息、工具请求和工具结果。
- 程序退出后，重启并使用相同会话名可以恢复历史。
- 保留 V2 的计算器和时间工具、模型与工具节点循环及循环上限。

## 目录与存储位置

```text
自学agent/
├── main.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── data/
│   └── memory.db
└── versions/
    ├── v0/
    ├── v1/
    ├── v2/
    ├── v3-memory/
    └── v3/
        ├── main.py
        ├── requirements.txt
        └── README.md
```

数据库在对应 main.py 同级的 data 文件夹里自动创建。
根目录程序使用 data/memory.db。
运行此历史快照时，使用 versions/v3/data/memory.db，便于独立复现，
不会自动读取根目录程序的聊天记录。两者都有 SQLite 持久化能力。

快照保存代码和依赖清单，没有复制 .env 或聊天数据库。
v3-memory 保留切换到 SQLite 前的内存版代码，关闭后仍会丢失记忆。

## 安装与启动

在项目根目录的 PowerShell 中，如果需要重新安装快照依赖：

```powershell
uv pip install --python .\.venv\Scripts\python.exe -r .\versions\v3\requirements.txt
```

运行当前版本：

```powershell
.\.venv\Scripts\python.exe main.py
```

运行这个历史快照：

```powershell
.\.venv\Scripts\python.exe .\versions\v3\main.py
```

依赖与前一步一致，SQLite 适配器为 langgraph-checkpoint-sqlite。
不需要单独安装 SQLite 服务。

## 模型配置

在根目录 .env 中沿用这三个配置，不需要新增密钥：

```dotenv
MODEL_NAME=你的模型名称
API_KEY=你的API密钥
BASE_URL=你的兼容接口地址
```

正常启动时会显示 Agent V3、SQLite Checkpointer、实际数据库路径、
默认会话名和 /session 命令提示。

## 最小重启测试

第一次运行时，依次输入并等待回答：

```text
/session 记忆测试
请记住本次测试口令：青竹417。
exit
```

重新运行同一个 main.py，依次输入：

```text
/session 记忆测试
我让你记住的测试口令是什么？
```

预期模型根据历史回答青竹417。
重启时仍默认进入 default-session，需要手动切回原会话名。

## 常见问题

- 导入失败：确认用的是项目 .venv 的解释器，依赖安装在该环境内。
- 重启后没有恢复：核对 thread_id 和启动时打印的数据库路径是否相同；
  根目录程序与历史快照的数据库不同，内存版也不会恢复 SQLite 记录。
- 数据库无法写入或被锁：检查文件夹权限，避免多个程序同时写入同一数据库。
- 连接或模型接口报错：检查网络和 .env，错误来源是模型请求。
- 模型说明自己不能记忆：模型的口头描述不是持久化证据；
  用退出再启动的测试判断保存器是否生效。
- 某轮报错后：Checkpointer 可能已经保存输入或中间节点状态；
  不要认为异常会自动撤销这一轮。当前没有实现清理或恢复失败轮次的命令。

## 阶段边界

这是 thread 级对话历史的持久化，仍属于会话记忆。
它没有实现跨会话共享的用户画像、自动提取长期事实、历史摘要或消息裁剪。
很长的对话仍会占用模型上下文窗口。
RAG、MCP、FastAPI、Evaluation 和 Docker 留给后续阶段。
