# From a Simple Loop to an Agent

从一个最小的对话循环开始，逐步构建具备工具调用、会话记忆、知识库检索、MCP、HTTP 接口和网页界面的 AI 智能体。

> Building an AI agent step by step—from a simple loop to a full-stack application with tools, memory, RAG, MCP, and Docker.

这是一个循序渐进的学习项目，而不是直接使用封装好的完整应用。根目录保留当前版本，`versions/` 保存各阶段代码与说明，方便比较实现方式、复现和复习。

## 版本历史说明

项目早期是在多个阶段完成后才统一纳入 Git。为便于按阶段比较代码，本仓库于 2026-10-20 依据 `versions/` 中已有的快照，重新整理了 V0～V9 的阶段提交；它们是事后重建的学习记录，提交时间不是各阶段最初开发的时间，也没有还原每一个开发小步骤。

重建保留了当前业务源码和原有快照内容。查看某阶段的提交可以比较当时的根目录实现，查看 `versions/` 则可以直接阅读各阶段存档；历史阶段的依赖与运行方式应以对应说明为准。

## 当前功能

- **对话入口**：既可在终端聊天，也可通过网页或 HTTP 接口使用。
- **工具调用**：模型选择工具与参数，由 LangGraph 执行工具并将结果交回模型，支持继续调用和生成最终回答。
- **会话记忆**：通过 `session_id` 对应 LangGraph 的 `thread_id`，使用 SQLite 保存状态，支持重启后继续同一会话。
- **RAG 检索**：读取本地 Markdown，切分、向量化、计算余弦相似度，将检索片段和来源提供给模型。
- **MCP 接入**：自动发现本地 MCP Server 的工具，转换成 LangChain 工具，交给 ToolNode 管理。
- **最小评估**：检查答案文字、成功工具调用和检索内容，生成通过率、耗时与 JSON 报告。
- **容器运行**：使用 Docker 构建镜像，通过命名卷保存会话数据库与向量模型缓存。
- **聊天网页**：支持发送问题、切换会话和重新加载历史消息。

当前 MCP 工具包括：

| 工具 | 功能 |
| --- | --- |
| `get_current_time` | 查询 MCP Server 所在环境的日期、时间和时区 |
| `calculator` | 两个数字的加、减、乘、除 |
| `count_text_characters` | 按 Python `len()` 统计文本长度 |

知识库工具 `search_knowledge` 在智能体进程内执行，不经过 MCP。示例文档中的“青竹 Agent 学习营”、人物与规则均为教学虚构。

## 从 V0 到 V9

| 阶段 | 核心实现 | 主要学习内容 |
| --- | --- | --- |
| [V0](versions/v0/) | 最小连续聊天程序 | 模型客户端、环境变量、消息角色、对话历史、异常处理 |
| [V1](versions/v1/) | 手写工具调用循环 | 工具描述、JSON 参数、执行分发、多工具结果、循环上限 |
| [V2](versions/v2/) | LangGraph 状态图 | State、节点、边、ToolNode、条件路由、消息合并 |
| [V3](versions/v3/) | 可持久化会话记忆 | Checkpointer、`thread_id`、SQLite、会话切换与恢复 |
| [V4](versions/v4/) | 本地中文 RAG | 文档切分、Embedding、向量存储、相似度检索、引用来源 |
| [V5](versions/v5-auto/) | MCP 工具自动发现 | Server / Client、stdio、工具定义、StructuredTool、同步与异步入口 |
| [V6](versions/v6/) | FastAPI 服务 | 请求与响应模型、生命周期、共享服务对象、HTTP 接口 |
| [V7](versions/v7/) | 最小自动评估 | 题库、实际执行记录、分项检查、汇总指标、结果保存 |
| [V8](versions/v8/) | Docker 打包与运行 | Dockerfile、构建上下文、镜像、容器、端口映射、数据卷 |
| [V9](versions/v9/) | 极简聊天网页 | HTML / CSS / JavaScript、fetch、DOM 更新、历史加载 |

另保留 [V3 内存版](versions/v3-memory/) 和 [V5 基础接入版](versions/v5/)，用于对比持久化前后、自动发现前后的区别。

完整版本说明见 [版本索引](versions/README.md)；逐阶段知识点与复习问题见 [项目知识复习报告](项目知识复习报告_V0至当前.md)。

## 当前调用流程

```text
浏览器网页 / 其他 HTTP 客户端
    → Uvicorn 接收请求
    → FastAPI 校验请求、匹配接口
    → AgentService.ask(message, session_id)
    → LangGraph 读取该 thread_id 的会话状态
    → 模型节点生成回答或工具调用请求
        ├─ 不需要工具：结束，返回回答
        └─ 需要工具：ToolNode 执行
            ├─ MCP 工具：Client → 本地 Server → 执行结果
            └─ RAG 工具：本地向量检索 → 文档片段与来源
            → 工具结果加入状态 → 再次调用模型
    → SQLite Checkpointer 保存状态
    → HTTP JSON 响应 → 前端更新聊天内容
```

图执行期间的检查点也会保存，并非只在最后保存一次。终端入口直接调用同一套 `AgentService`，不需要经过 HTTP。

打开网页时，浏览器先请求 `GET /` 取得 HTML，再由页面脚本请求 `GET /history` 加载默认会话；读取历史不触发模型推理。

## 项目结构

```text
.
├── main.py                  # 终端入口
├── app/
│   ├── agent_service.py      # 初始化资源、构建状态图、问答与历史读取
│   ├── api.py                # FastAPI 生命周期与路由
│   ├── schemas.py            # 请求、响应的数据结构
│   └── static/index.html     # 原生 HTML / CSS / JavaScript 聊天网页
├── mcp_client.py             # MCP 工具发现、转换与执行桥接
├── mcp_server.py             # 本地工具定义与 stdio 服务
├── rag.py                    # 文档读取、切分、向量化与检索
├── data/agent_notes.md       # 虚构知识库资料
├── eval/
│   ├── dataset.json          # 最小评估题库
│   └── evaluator.py          # 检查、真实评估与报告生成
├── versions/                # 各阶段代码快照与报告
├── requirements.txt         # Python 依赖
├── .env.example             # 不含真实密钥的配置示例
├── .gitignore               # 忽略密钥和本地运行数据
├── .dockerignore            # 排除不应进入构建上下文的文件
└── Dockerfile               # 镜像构建与容器启动配置
```

运行后会生成 `data/memory.db`、SQLite 辅助文件和 `data/embedding_models/`，这些是本地数据，不随 Git 仓库分发。

## 本地运行

以下以 **Windows PowerShell、Python 3.12** 为例。需要可用的模型 API 配置；首次启动还需要联网下载向量模型。

### 1. 获取代码并安装依赖

```powershell
git clone https://github.com/Roninonly/from-a-simple-loop-to-an-agent.git
cd from-a-simple-loop-to-an-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

依次下载仓库、进入目录、创建虚拟环境、向该虚拟环境安装依赖。这里直接指定虚拟环境的 Python，不需要先激活它；本机 `python` 应指向准备使用的 Python 3.12。

### 2. 配置模型

将 `.env.example` 复制为本地 `.env`；已有配置时不要覆盖。PowerShell 中可以运行：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

此命令仅在 `.env` 不存在时创建它。随后在编辑器中填写：

| 配置项 | 含义 |
| --- | --- |
| `MODEL_NAME` | 服务商提供的、支持工具调用的模型名称 |
| `API_KEY` | 该服务商的 API 密钥 |
| `BASE_URL` | 对应的 OpenAI-compatible API 地址 |

项目通过兼容接口连接模型，不限定只能使用某一家服务商；不同模型对工具调用、参数格式的支持可能不同。

**不要提交或分享真实 `.env`，也不要把密钥写进源码、截图或 README。**

### 3. 启动聊天网页

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8001
```

此命令使用项目虚拟环境运行 Uvicorn，加载 `app/api.py` 中的 `app` 对象，只在本机的 8001 端口监听。看到 `Application startup complete` 后访问：

- 聊天网页：<http://127.0.0.1:8001/>
- 接口文档：<http://127.0.0.1:8001/docs>
- HTTP 健康检查：<http://127.0.0.1:8001/health>

首次启动会准备本地知识库、下载并缓存 `BAAI/bge-small-zh-v1.5` 中文向量模型，然后发现 MCP 工具、打开 SQLite。下载完成前请等待启动日志，不要反复创建新进程。

终端需保持运行，`Ctrl+C` 停止。当前不需要额外启动 MCP Server，客户端会管理它的子进程。

### 4. 其他学习入口

以下命令分别运行终端聊天、独立 RAG 检索、MCP 工具发现，不需要全部同时启动：

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe rag.py
.\.venv\Scripts\python.exe mcp_client.py
```

终端聊天中使用 `/session 会话名` 切换，输入 `exit` 退出。运行 MCP Client 的独立入口只展示发现的工具，不会自动执行它们。

## 网页使用与接口

网页默认会话是 `default-session`。输入新的会话 ID 并切换，可以开始另一段对话；切回原 ID 会读取原来的聊天历史。

刷新页面会回到默认会话；当前选择尚未存入浏览器，因此查看其他会话时需要再次切换。页面只展示用户消息和最终文本回答，不展示系统提示、工具请求或工具结果。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/` | 返回聊天 HTML 页面 |
| `GET` | `/health` | 检查 HTTP 服务是否响应，不验证模型或工具可用性 |
| `POST` | `/chat` | 按会话提交问题，返回 `answer` 与 `session_id` |
| `GET` | `/history?session_id=demo` | 读取指定会话的可展示历史，不调用模型 |
| `GET` | `/docs` | FastAPI 自动生成的交互式接口文档 |

`POST /chat` 的请求体示例：

```json
{
  "message": "请调用计算器计算 123 乘以 123，并查询当前时间。",
  "session_id": "demo"
}
```

可以在 `/docs` 中提交，不要通过浏览器地址栏直接打开 `/chat` 来发送问题：地址栏通常发送 GET，而问答接口需要 POST 和 JSON 请求体。

## 自动评估

预览题库，不请求模型：

```powershell
.\.venv\Scripts\python.exe eval/evaluator.py
```

执行真实智能体评估：

```powershell
.\.venv\Scripts\python.exe eval/evaluator.py --run
```

`--run` 会提交当前题库的 5 次用户消息，工具循环可能产生额外模型请求和费用。当前共 4 道题，覆盖普通回复、计算器、RAG 和同会话记忆。

评估使用临时 SQLite 数据库，结束后清理，不修改日常会话数据库；模型缓存仍可在本地保留。结果保存到 `eval/results/`，包含任务成功率、答案文字条件通过率、必需工具检查通过率、目标资料命中率及平均每题耗时。

这些指标只代表当前题库与检查条件，不代表通用准确率，也不等于完整的安全、并发或持久化测试。

## Docker 运行

先安装并启动 Docker Engine；Windows 可使用 Docker Desktop 的 WSL2 后端。以下命令仍在项目根目录执行，并使用已经填写的本地 `.env`。

### 构建镜像

```powershell
docker build --progress=plain -t agent-study:v9 .
```

`build` 按 Dockerfile 构建镜像，`--progress=plain` 显示文本日志，`-t` 指定名称和标签，最后的 `.` 是当前构建上下文。镜像包含代码与依赖，不包含本机 `.venv`、真实 `.env`、聊天数据库或向量模型缓存。

### 创建数据卷并运行

```powershell
docker volume create agent-study-v9-data
docker run -d --name agent-study-v9-web --env-file .env --mount "type=volume,source=agent-study-v9-data,target=/app/data" -p 127.0.0.1:8002:8000 agent-study:v9
```

第一行创建或复用命名卷。第二行从镜像创建并启动容器：

- `-d`：在后台运行。
- `--name`：指定容器名称，同一 Docker 环境中不能重名。
- `--env-file`：将本地配置作为环境变量传入，不把密钥打包进镜像。
- `--mount`：将命名卷挂载到 `/app/data`，保留 SQLite 和模型缓存。
- `-p 127.0.0.1:8002:8000`：将本机 8002 端口映射到容器 8000，只允许本机访问。
- `agent-study:v9`：使用的镜像，不是要创建的容器名称。

查看启动日志：

```powershell
docker logs --tail 30 agent-study-v9-web
```

此命令读取最后 30 行日志，不会重新启动容器。等待初始化完成后，打开 <http://127.0.0.1:8002/>。

停止和再次启动同一容器，可分别使用：

```powershell
docker stop agent-study-v9-web
docker start agent-study-v9-web
```

这两条命令停止或恢复已有容器，不会删除命名卷。不要为了再次启动而重复 `docker run`，否则同名容器会冲突。首次使用新卷仍需下载向量模型，之后同卷可复用缓存。

源码修改后，需要重新构建镜像并创建使用新版镜像的容器；已有容器不会自动更新。已存在的数据卷也会覆盖镜像中的 `/app/data` 内容，因此更新知识文档时需单独考虑卷内文件，不要直接删除保存聊天记录的卷。

## 实现边界与安全说明

- **学习项目，不是生产就绪服务**：没有登录、鉴权、限流或用户权限；知道会话 ID 就可能读取其记录，`thread_id` 隔离不等于安全隔离，请勿直接暴露到公网。
- **单进程设计**：服务内使用锁串行处理问答与历史读取；启动时保持一个工作进程，不把当前 SQLite 方案当作多实例并发方案。
- **有网络与费用依赖**：大语言模型通过远程 API 调用；本地 RAG 不代表整个智能体离线运行，模型服务会接收提交的对话和相关工具结果。
- **记忆不是训练模型**：SQLite 保存会话状态并在后续调用时提供上下文，不是修改模型权重；当前没有跨会话用户画像、历史摘要或上下文裁剪。
- **RAG 是最小实现**：知识库启动时在内存重建，默认取相似度最高的 2 个片段，没有相似度拒答阈值、持久化向量数据库或重排模型。
- **网页保持极简**：当前无流式输出、历史分页、会话列表、Markdown 渲染或消息删除；输出按普通文本展示。
- **日志与数据需自行保护**：终端可能打印工具参数与检索片段，评估报告也包含执行内容，不应放入真实隐私资料。
- **依赖可复现性仍可改进**：多数依赖未锁定版本，未来重新安装或构建可能受上游变更影响，历史快照不等于完整环境锁定。

接口文档和终端部分文字仍沿用“Agent V6”，表示这些入口最初加入的阶段，不代表当前仓库缺少 V7～V9 的功能。GitHub 保存源码，Docker 镜像保存构建产物，数据卷保存运行数据，三者需要分别管理。

## 后续方向

可在这个结课版本上继续练习流式响应、登录鉴权、历史摘要、更丰富的 RAG 和自动化测试；这些是后续方向，不是当前已实现功能。

本仓库的核心目标是理解每一步为什么存在、数据怎样流动，以及如何从一个小循环逐步构建完整应用。
