# 阶段 5 报告：Agent V5 — MCP 工具接入

本快照在用户于 2026-10-10 成功验证连续两次实时查询后保存。

## 相比 V4 的完整改动

- 新增 mcp_server.py：使用官方 MCP SDK 的 MCPServer，注册当前时间工具，以 stdio 方式提供服务。
- 新增 mcp_client.py：配置本地 Server 子进程、连接、发现工具、调用时间工具并提取返回文本。
- main.py 删除直接读取时间的本地函数和 datetime 导入，改为导入客户端的同名包装函数。
- main.py 保留同一份三工具列表：计算器、MCP 时间工具、知识库检索工具。
- main.py 更新 V5 标识及系统提示，要求时间问题实时调用工具，不使用历史时间推断。
- requirements.txt 新增 mcp==2.3.0；没有新增专门的 LangChain MCP 适配包。
- LangGraph 循环、SQLite 会话隔离及恢复、RAG 文档读取和检索逻辑保持不变。

## 核心函数与调用关系

mcp_server.py 中的 get_current_time 读取服务端电脑的真实日期、时间和时区。
@server.tool() 将其注册为 MCP 工具；server.run(transport="stdio") 启动服务并等待请求。

mcp_client.py 中：
- create_mcp_client：指定当前 Python 解释器和同目录下服务端文件的绝对路径，构造客户端；此时尚未启动服务。
- call_time_tool：通过已连接客户端请求 get_current_time，并将返回的文本块拼成字符串。
- get_current_time：给同步 ToolNode 使用的包装函数，调用 asyncio.run 执行内部异步请求，打印日志并返回结果。
- 内层 request_time：在 async with 中建立连接、调用工具，离开上下文时清理连接和服务端子进程。
- main：独立通信测试，连接后列出工具、调用一次时间工具并关闭。

完整一次问答中，模型先请求时间工具，ToolNode 执行客户端包装函数，
客户端通过 MCP 向独立 Server 进程发出请求，Server 读取时间并返回。
客户端将文本交回 ToolNode，ToolNode 生成工具消息加入状态，模型再生成最终回答。
无需用户单独打开服务端终端；目前每次调用都会启动并关闭一个 Server 子进程。

内层 request_time 没有捕获外层局部变量，因此也可以移到模块顶层。
保留嵌套是为了将这段专用异步连接逻辑放在同步包装函数附近，不是语法强制要求。

## 已验证

- 用户第一次查询：2026-10-10 10:02:21 中国标准时间。
- 用户第二次查询：2026-10-10 10:05:18 中国标准时间。
- 两次均出现 MCP 调用日志，最终回答与工具结果一致。
- 输入 exit 正常结束对话。
- 归档时校验快照内容与根目录对应文件一致，并检查 Python 语法和快照内 MCP 通信。

## 快照文件及运行方式

包含 main.py、rag.py、mcp_client.py、mcp_server.py、requirements.txt、
data/agent_notes.md 以及本报告。

不包含 .env、虚拟环境、真实会话数据库、模型缓存或 Python 字节码。
沿用项目根目录 .env；数据库及向量模型缓存按快照文件位置创建，
位于 versions/v5/data，与根目录运行数据分开。首次运行 RAG 快照可能需要下载模型。

在项目根目录使用已有虚拟环境运行：

```powershell
.\.venv\Scripts\python.exe .\versions\v5\main.py
```

只检查快照内 MCP 通信，不启动聊天模型或加载 RAG：

```powershell
.\.venv\Scripts\python.exe .\versions\v5\mcp_client.py
```

现有环境已经安装依赖，不必重复安装。以后重建环境时先确认安装操作，
再使用该快照的 requirements.txt。除 MCP 已固定版本外，其余依赖沿用原清单；
这不是完整的依赖锁定文件，未来安装未必与当前环境完全一致。

## 当前边界与容易混淆的地方

- 这是 MCP 工具服务，不是新建了第二个智能体；Server 内部没有聊天模型。
- 当前只有时间工具走 MCP；计算器与 RAG 仍在 Agent 进程中执行。
- Client 的 call_time_tool 明确写了时间工具名；list_tools 只用于独立测试展示。
- 新增 Server 工具不会自动注册到 Agent，尚未实现通用工具发现与适配。
- stdio 是本机进程通信方式，不是已经部署的远程 HTTP 服务。
- 同步包装函数使用 asyncio.run，不能直接放进同一线程已运行的异步事件循环；
  以后进入异步 Web 服务时，需要重新选择同步或异步调用方式。
- Server 标准输出用于协议通信，不应加入普通 print 提示；本项目日志放在客户端。
- 时区来自运行 Server 的电脑设置，程序没有硬编码中国标准时间。
- wxit 是普通用户文本，不是退出命令；目前只匹配精确的 exit。
- 模型关于“以后不会记得”的说法不能代替实际存储行为：SQLite 保留同一会话历史，
  不同 thread_id 的历史相互隔离，不会自动跨会话共享。
- 尚未实现 FastAPI、正式评估测试集或 Docker 部署。
- 下一阶段是 V6 FastAPI，等待用户明确要求继续下一阶段。

本阶段把时间工具从 Agent 进程内的普通函数，扩展为由 MCP Client 请求独立
MCP Server 执行，为以后复用工具服务做准备；目前还不是全自动的通用 MCP 接入。
