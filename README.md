# 阶段 5 报告：Agent V5 — MCP 多工具自动发现版

于 2026-10-10 在用户成功验证新增文字计数工具后保存。
原 versions/v5 保留为单工具接入的基础快照，本目录保存后续多工具与自动接入版本。

## 本阶段结果

保留 LangGraph 工具循环、SQLite 会话记忆、本地 RAG。
MCP Server 提供 get_current_time、calculator、count_text_characters 三个工具。
客户端启动时读取清单，将工具转换为 StructuredTool，和本地 search_knowledge 一起
交给聊天模型与 ToolNode。当前智能体共四个工具，只有 RAG 不走 MCP。

## 相比原 V5 基础快照的改动

- mcp_server.py 的服务名改为 agent-tools，新增计算器和文字计数工具。
- 计算器从主程序迁移到 Server；除零和非法运算符使用 MCP ToolError 返回明确提示。
- 文字计数使用 Python len，空格、标点和换行也计入；严格含义是 Unicode 码点数量，
  不保证与复杂 emoji 或组合字符的视觉字符数量相同。
- mcp_client.py 删除原来的专用时间包装，后续增加的专用计算器包装也被通用代码替代。
- 新增 call_mcp_tool：创建连接，按名称和参数调用，关闭连接后读取文本及检查 is_error。
- 新增 create_mcp_tool：根据 Server 的名称、说明和输入 JSON Schema 创建 StructuredTool。
- 新增 load_mcp_tools：读取全部工具清单（包括分页），逐个转换；只发现，不执行业务工具。
- main.py 新增 asyncio 导入，调用 load_mcp_tools，合并 MCP 工具与本地 RAG 工具，
  不再手动列出时间和计算器函数。模型和 ToolNode 使用同一份工具列表。
- 客户端独立 main 只展示工具清单及参数，不自动执行任何工具。
- 依赖、RAG 模块和会话存储逻辑不变；未引入新适配包。

## 核心调用关系

启动时，main.py 的 main 调用 create_retriever_tool 准备 RAG，
再通过 asyncio.run(load_mcp_tools()) 发现 MCP 工具。
load_mcp_tools 连接 Server，使用 list_tools 获取定义，对每份定义执行 create_mcp_tool。
每次工厂调用创建自己的 request_tool 与 invoke_tool，并在闭包中保存自己的工具名。
返回的是 StructuredTool 对象，不是执行结果；内层函数此时不执行。
随后绑定聊天模型、创建 ToolNode 与状态图，打开 SQLite 会话，等待用户输入。

收到工具请求后，LangGraph 路由至 ToolNode。
ToolNode 按工具名找到已登记对象，调用库提供的工具 invoke 方法。
StructuredTool 内部执行 func 保存的 invoke_tool，后者用 asyncio.run 执行 request_tool。
request_tool 调用通用 call_mcp_tool，后者连接 Server 并发送 client.call_tool(name, arguments)。
Server 执行对应函数并返回。连接关闭后，客户端检查结果、提取文本，并逐层返回。
库将结果包装成对应 ToolMessage，ToolNode 返回状态更新，LangGraph 合并消息并再次调用模型。
模型不再请求工具时，本轮图执行结束，主程序打印回答。

invoke 是库方法，invoke_tool 是项目定义的函数，两者靠 func=invoke_tool 关联。
coroutine=request_tool 为异步工具调用提供入口；当前终端使用同步入口。
handle_tool_error=True 将 ToolException 转成错误工具消息，可让模型看到工具执行失败。
连接故障等非工具执行错误仍可能中断本轮，不代表实现了所有故障恢复。

## 已验证

- 用户两次实时查询成功，证明原单工具 MCP 接入有效。
- 自动发现三个 MCP 工具，名称、描述和参数规则均可用于模型绑定。
- 通过真实 MCP 通信测试计算器四则运算、除零和非法运算符。
- 通过真实 MCP 通信测试文字计数：普通中文、空文本、空格标点、换行和单码点 emoji。
- 用户运行主程序后自动发现 count_text_characters，模型传入 text=我爱学习，
  工具返回 4，模型最终回答长度为 4，exit 正常退出。
- 确认添加文字计数时 main.py 和 mcp_client.py 的哈希未改变。
- LangGraph 集成测试使用预设模型响应，真实执行三个 MCP 工具，验证工具消息及最终回路。
- 临时测试 Server 中未预先写入客户端的工具，也能自动转换、调用并转发默认参数。
- 同步与异步调用、工具错误消息、工具发现分页均测试通过。
- 归档时检查快照与对应运行文件一致、Python 语法通过，并独立执行快照内的 MCP 工具。
- 自动化测试不使用用户真实会话数据库；预设模型测试不调用聊天模型 API。

## 文件与运行方式

快照包含 main.py、rag.py、mcp_client.py、mcp_server.py、requirements.txt、
data/agent_notes.md 和本报告，不包含真实 .env、会话数据库、模型缓存、虚拟环境。

在项目根目录用已有环境运行历史版本：

```powershell
.\.venv\Scripts\python.exe .\versions\v5-auto\main.py
```

只查看工具发现：

```powershell
.\.venv\Scripts\python.exe .\versions\v5-auto\mcp_client.py
```

历史版本继续读取项目根目录 .env。自己的数据库和模型缓存位于 versions/v5-auto/data，
不与根目录真实会话混用；第一次运行此快照可能需要下载向量模型。
依赖已经在现有虚拟环境安装，不必重复安装。只有 MCP 固定版本，
requirements.txt 不是完整锁文件，未来重建环境可能得到不同依赖版本。

## 当前边界与注意事项

- 新增兼容文本工具时，在当前 Server 添加带 @server.tool() 的函数，重启智能体即可重新发现。
- 自动发现是 MCP 工具清单与项目客户端适配代码共同实现的，不是 LangGraph 自动扫描文件。
- 不支持运行中热更新工具，不是任意远程 Server 的自动连接器。
- 仅提取文本结果，不处理图片、音频或完整 MCP 资源、提示词等能力。
- 只应接入可信 Server；新增有外部写入等副作用的工具应先设计权限和审批。
- 新工具名需要与本地 RAG 等工具保持唯一；目前没有工具名冲突检测。
- 仍然每次实际调用启动并关闭本地 Server 子进程，没有实现常驻连接或连接池。
- 同批次工具可并行执行，不会自动用前一个结果改写后一个参数。
  依赖前一个结果时，模型需要在后续回合生成请求；强制顺序应另写流程编排。
- StateGraph 控制工具后返回模型；MCP 只负责工具发现和通信，不替代 LangGraph。
- Server 标准输出用于 MCP 通信，普通日志应放客户端或标准错误。
- 会话恢复依赖 SQLite 与 thread_id，不依赖模型自己对“记忆能力”的描述。
- 尚未实现 FastAPI、正式评估测试集或 Docker 部署。

下一阶段为 V6 FastAPI，等待用户明确要求进入下一阶段。
