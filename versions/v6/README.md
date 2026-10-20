# 阶段 6 报告：FastAPI Agent Service

【当前 Agent 版本】Agent V6：可通过 HTTP 接口调用的智能体服务。

## 一、本阶段解决了什么

V5 已有 LangGraph、SQLite 会话历史、本地 RAG、MCP 多工具自动发现，
但主要通过终端 input() 接收问题。V6 保留这些能力，增加 HTTP 入口，
让网页或其他程序提交问题并取得回答，没有重写另一套智能体。

本阶段不实现聊天网页、账号系统、公网发布、Evaluation 或 Docker。
`/docs` 是 FastAPI 自带的接口测试页面，不是我们开发的聊天产品界面。

## 二、快照目录与文件职责

```text
v6/
├── main.py                 # 终端入口
├── app/
│   ├── __init__.py          # 后端应用包
│   ├── api.py               # HTTP 入口与生命周期
│   ├── schemas.py           # 请求、响应的数据格式
│   └── agent_service.py     # 终端与 HTTP 共用的智能体逻辑
├── rag.py                  # 本地文档向量检索
├── mcp_client.py           # MCP 工具发现、转换和调用
├── mcp_server.py           # 时间、计算器、文字计数工具
├── requirements.txt        # 当前阶段依赖声明
├── data/
│   └── agent_notes.md       # 教学虚构知识文档
└── README.md               # 本报告
```

快照不包含真实 `.env`、聊天数据库、模型缓存、虚拟环境或 Python 字节码。
Python 文件、依赖清单和知识文档与完成 V6 时的开发版内容一致。
快照运行后使用自己的 `data/memory.db` 和 `data/embedding_models/`，
不会恢复根目录版本的真实聊天记录。首次运行快照可能下载向量模型。

## 三、相比 V5 的全部核心变化

- 新增 `app/__init__.py`，将后端代码组织成包。
- 新增 `app/schemas.py`，用 Pydantic 定义 ChatRequest、ChatResponse。
  输入包含 message、session_id，输出包含 answer、session_id；
  不传 session_id 时默认为 default-session，空字符串和纯空白输入会被拒绝。
- 新增 `app/api.py`，创建 FastAPI 应用，提供 GET /health 和 POST /chat。
  `/chat` 最初用于回显测试，最终改为调用真实 AgentService.ask()。
- 新增 `app/agent_service.py`，接收原 main.py 中的配置、系统提示、
  AgentState、模型、节点和状态图构建函数，以及初始化、单轮问答逻辑。
- 新增 AgentService 类，保存状态图；ask() 按会话取得历史、提交问题、
  运行图并返回最终回答。加入单进程锁，串行保护完整问答过程。
- 新增 create_agent_service() 上下文流程，准备 RAG、发现 MCP 工具、
  创建模型客户端、打开 SQLite、编译状态图，退出时关闭数据库连接。
- main.py 仅保留终端入口、会话切换、退出和打印回答，问答调用共享服务。
- api.py 的 lifespan() 在应用启动时初始化一次，在正常关闭时清理；
  用库提供的线程池桥接执行同步初始化，避免 asyncio.run() 进入正在运行的 HTTP 事件循环。
  同步 chat() 由框架在线程池执行，仍沿用同步 graph.invoke()。
- 配置仍是 MODEL_NAME、API_KEY、BASE_URL；移动模块后明确从项目根目录读取 .env。
  默认数据库路径仍是当前版本根目录的 data/memory.db。
- 新增未就绪 503、处理失败 500；内部错误记录在终端，不直接返回底层报错给调用方。
- requirements.txt 新增 fastapi、uvicorn 的直接依赖声明。
  本阶段安装 FastAPI 及其辅助依赖，已有 Uvicorn 未重复安装。

RAG、MCP Client、MCP Server 的业务实现没有改变；旧版本目录保持不变。
没有新增手工拼接工具消息的逻辑，原来的 LangGraph 工具循环继续工作。

## 四、名字辨认

| 写法 | 含义 |
| --- | --- |
| AgentService | 我们定义的类，不是模型本身 |
| service | 指向某个 AgentService 对象的局部变量 |
| application.state.agent_service | FastAPI 应用中保存同一对象引用的属性 |
| create_agent_service() | 准备资源、交出对象并在退出时清理的上下文流程 |
| service.ask(...) | 我们自己写的单轮问答方法 |
| ChatRequest、ChatResponse | 数据格式类，不是大语言模型 |

`yield AgentService(...)` 创建并交出对象，由外面的 `as service` 接住。
保存到 application.state 不会创建第二个对象，也不会自动开始问答。
真正连接接口和智能体的是 `answer = service.ask(...)`。

FastAPI 的应用 state 保存共享对象，不等于 LangGraph 的 AgentState；
前者在进程关闭后消失，对话历史则由 SQLite Checkpointer 持久保存。

## 五、启动、问答与关闭的调用关系

### 启动时

Uvicorn 加载 api.py 中的 app，FastAPI 调用我们登记的 lifespan()。
进入 create_agent_service()，依次执行 load_config()、create_retriever_tool()、
load_mcp_tools()、create_langgraph_model()，打开 SQLite，再创建状态图。
create_agent_graph() 调用 create_agent_node() 和 create_tool_node()，
登记节点、路由和边并编译，但此时还没有调用模型回答问题。
创建 AgentService 后保存在 application.state.agent_service，开始接收请求。

### 每次提问时

1. 浏览器打开 /docs，只获取框架提供的测试页面，不会调用 chat()。
2. 在 POST /chat 点击 Execute，浏览器提交 JSON。
3. FastAPI 配合 Pydantic 检查输入，构造 ChatRequest；错误输入返回 422。
4. 框架调用 chat()；我们取出保存的服务对象，调用 service.ask()。
5. ask() 以 session_id 设置 thread_id，读取历史、准备本轮 HumanMessage。
   新会话补系统提示，旧提示变化时按同一消息 ID 更新，不删除原历史。
6. graph.invoke() 启动图；LangGraph 调用内层 agent_node()，它调用 model.invoke()。
7. route_after_agent() 判断 tool_calls；需要工具时由 ToolNode 执行，
   结果进入消息状态，再回到模型。无需工具时结束本轮。
8. Checkpointer 继续负责按会话保存检查点。ask() 提取最终文本并返回给 chat()。
9. chat() 构造 ChatResponse，FastAPI 转换为 JSON，通过 Uvicorn 返回客户端。

网页入口不调用 main.py 的 main()。执行 python main.py 时，main() 通过
input() 收集问题，同样调用 service.ask()，但使用 print() 显示回答。
两个入口共用代码逻辑，不表示两个进程会共用同一个内存对象。

### 正常关闭时

lifespan() 从 yield 后继续，清空 application.state.agent_service，
再退出上下文，让 create_agent_service() 内的数据库 with 结束并关闭连接。
清空引用和关闭连接都不等于删除数据库或聊天记录。
强制杀进程、断电不保证执行这套正常清理流程。

## 六、运行方式

以下命令均在 `D:\agent\自学agent` 项目根目录执行。
已有依赖无需重新安装；以后重建环境前先确认，再用 requirements.txt 安装。
本阶段验证环境为 Python 3.12.14、FastAPI 0.143.0、Uvicorn 0.54.0；
依赖清单不是完整锁文件，不保证以后解析出完全相同的间接依赖版本。

开发版启动：

```powershell
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

运行当前 V6 快照，使用项目虚拟环境，并由 Uvicorn 预先读取原 .env：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --app-dir .\versions\v6 --env-file .\.env --host 127.0.0.1 --port 8000
```

`--app-dir` 选择快照模块，`--env-file` 将原配置加载到进程环境，
没有复制密钥到快照。因为快照中的配置函数明确读取它自己根目录的 .env，
不能假设直接运行快照会自动向上查找原项目配置。

如需运行快照的终端入口，可在新进程中先加载原配置、再选择快照路径：

```powershell
.\.venv\Scripts\python.exe -c "from dotenv import load_dotenv; import sys, runpy; load_dotenv('.env'); sys.path.insert(0, 'versions/v6'); runpy.run_path('versions/v6/main.py', run_name='__main__')"
```

这些启动方式任选一个，先停止旧服务以避免端口占用或同时写入同一会话。
目前只运行一个服务进程，不添加多个 workers。停止服务按 Ctrl+C。

浏览器访问 `http://127.0.0.1:8000/health`，应返回 `{"status":"ok"}`。
访问 `http://127.0.0.1:8000/docs`，展开 POST /chat，点击 Try it out 后提交：

```json
{
  "message": "你好",
  "session_id": "v6-test"
}
```

返回包含模型回答的 answer，以及相同的 session_id，不再是固定回显。
浏览器地址栏直接访问 /chat 会发 GET，因此返回 405，应在 /docs 发送 POST。

.env 沿用三个配置项 MODEL_NAME、API_KEY、BASE_URL，不需要增加新的密钥。
不要将真实配置内容贴进报告、源码或聊天截图。

## 七、完成验收的证据

用户通过真实服务完成以下验收：

- GET /health 正常；POST /chat 得到模型回答和 200 响应。
- 查询当前时间：终端确实记录 MCP get_current_time 的调用和结果，
  网页回答与工具结果一致，不只依赖模型声称已查时间。
- 同一 session_id：先告知名字与学习内容，再只发送新问题，正确恢复历史。
- 不同 session_id：新会话不混用原会话的信息。
- Ctrl+C 停止并重启后，用原 session_id 仍可恢复历史。
- HTTP 提交学习营设备规则问题，确认 RAG 检索和带来源回答正常。

开发过程中另以临时 SQLite 数据库、预设模型和 RAG 测试替身检查了：
HTTP 接线、默认会话、隔离与重启恢复、真实 MCP 三工具和除零错误、
串行保护、正常关闭数据库、终端兼容、无效输入及失败响应。
这些自动检查没有调用真实模型 API、下载向量模型或修改真实聊天数据库；
预设回复测试不冒充真实模型的工具选择能力或真实向量检索质量评估。
归档时另检查快照内容一致、语法和模块路径。

## 八、当前边界与常见问题

- /health 仅表示 HTTP 服务可响应，不是每次探测模型、RAG、MCP 的健康检查。
- 422 多为输入格式问题；405 是请求方式不匹配；500 查看服务终端日志。
  配置、知识库或 MCP 初始化失败时应用可能无法完成启动，不应假装服务就绪。
- 本版只监听本机。没有登录鉴权，session_id 不是身份凭证；省略 ID 的请求
  共用 default-session，不能据此提供安全的多用户服务，也不应直接开放公网。
- 锁仅保护同一个服务对象内的问答，不解决多个进程同时修改历史的问题。
  目前不同会话的问答也排队执行，未做高并发、流式输出或全链路超时治理。
- 失败响应不代表自动回滚已经保存的检查点，尚未实现完整失败恢复机制。
- MCP 仍是每次调用建立连接、启动本地子进程；没有常驻连接池或工具热更新。
- RAG 索引仍在启动时建立于内存，没有升级向量数据库或持久索引。
- 尚未加入用户画像、历史摘要、系统性 Evaluation、Docker 或生产部署。

## 九、阶段结论

已具备：终端与 HTTP 双入口、共享智能体服务、工具调用、知识库检索、
按会话隔离的 SQLite 对话恢复、基本请求校验和错误响应。

下一阶段 V7 解决 Evaluation：建立测试集，衡量工具选择、检索和任务成功率等。
本快照没有提前实现 V7；等待用户明确要求继续下一阶段。
