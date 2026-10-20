# 阶段 9 报告：极简聊天网页与会话历史显示

存档日期：2026-10-20。

## 1. 本阶段完成什么

V9 在 V8 的智能体服务基础上增加一个本地聊天网页，让用户直接输入问题、查看回答、切换会话，并从 SQLite 中读取旧消息显示到页面。终端、MCP、RAG、会话持久化、评估和 Docker 构建配置继续保留。

这是现有智能体新增的使用入口，没有重新创建一套模型或工具逻辑。当前 FastAPI 标题和终端输出沿用 Agent V6，项目阶段号 V9 表示新增网页能力。

本阶段按三个小步骤完成：先能展示页面，再接通发送，最后增加会话切换与历史读取。只有页面显示时，并不具备发送请求的功能；后续 JavaScript 才补齐这一过程。

## 2. 相比 V8 的文件变化

| 文件 | 变化与职责 |
| --- | --- |
| `app/static/index.html` | 新增 HTML/CSS/JavaScript 网页，处理发送、显示、切换、历史加载及失败提示 |
| `app/api.py` | 增加首页 GET / 和历史 GET /history，继续复用已有 POST /chat |
| `app/agent_service.py` | 导入 AIMessage，新增 get_history()，过滤并返回可展示的会话文本 |
| `app/schemas.py` | 新增 HistoryMessage、HistoryResponse，用于约束历史响应 |
| `versions/README.md` | 根目录版本索引增加 V9 |
| 根目录 `.gitignore` | 忽略 V9 独立运行生成的数据库、缓存和评估报告 |
| 根目录复习报告 | 同步网页阶段知识点和实现进度 |

未新增 Python 或 JavaScript 第三方依赖；前端使用浏览器提供的功能。当前 Dockerfile 已复制整个 app 目录，构建时自然会包含 HTML，无需为了这个网页另加 COPY。

## 3. 快照结构

```text
v9/
├── README.md
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── main.py
├── rag.py
├── mcp_client.py
├── mcp_server.py
├── app/
│   ├── __init__.py
│   ├── agent_service.py
│   ├── api.py
│   ├── schemas.py
│   └── static/index.html
├── data/agent_notes.md
└── eval/
    ├── dataset.json
    └── evaluator.py
```

本目录保存 15 个应用、构建配置和题库文件，加上本报告。不复制 .env、真实 API Key、聊天数据库、向量模型缓存、虚拟环境、字节码、评估运行结果或 Git 元数据。快照不是运行数据备份。

## 4. 浏览器打开页面时发生什么

```text
浏览器 GET /
→ Uvicorn 接收，FastAPI 调用 homepage()
→ FileResponse 返回 app/static/index.html
→ 浏览器解析 HTML、应用 CSS、执行 script
→ 脚本末尾调用 loadHistory()
→ 浏览器 GET /history?session_id=default-session
→ 后端读取默认会话历史并返回 JSON
→ 前端逐条 addMessage()，把消息加入页面
```

这里是两个 HTTP 请求：第一个取得网页，第二个取得历史数据。自动显示历史的原因是脚本末尾显式调用了 loadHistory()，不是浏览器或 FastAPI 自动猜测要读数据库。

双击本地 HTML 可以展示内容，但当前相对地址 /history 和 /chat 需要通过对应 HTTP 服务访问页面，才能指向正确后端。

## 5. 发送问题的调用关系

```text
点击发送或按回车
→ submit 事件处理函数
→ preventDefault() 阻止表单默认刷新
→ input.value.trim() 取得问题
→ fetch("/chat", {method: "POST", headers: ..., body: ...})
→ 后端校验 ChatRequest
→ 从 app.state.agent_service 取得服务对象
→ service.ask(message, session_id)
→ LangGraph 按会话运行模型和工具
→ ChatResponse 返回 answer 和 session_id
→ FastAPI 转为 JSON 响应，Uvicorn 发回
→ response.json() 解析
→ addMessage("assistant", data.answer)
→ 创建段落、设置 textContent、appendChild 加入页面
```

fetch 是浏览器提供的请求函数；addMessage 是项目自己编写的显示函数。传给 fetch 的对象是请求配置，浏览器负责生成实际 HTTP 报文，不需要在 JavaScript 参数中手写请求头与请求体之间的空行。

前端 response 是 HTTP 响应对象，不是模型 SDK 返回的 response；两者名字相同但处于不同层次。答案收到后也不会自动出现在页面，必须执行 DOM 更新代码。

## 6. 会话与历史恢复

默认会话为 default-session；网页中的 currentSessionId 记录当前选择，发送时作为 JSON 中的 session_id 交给后端，再由 AgentService 作为 thread_id 使用。

切换按钮先校验和修剪会话名，更新当前会话，清空未发送草稿并调用 loadHistory()。loadHistory() 使用 encodeURIComponent 编码查询参数，支持中文、空格、/ 等字符。

历史接口：

```http
GET /history?session_id=web-a
```

响应结构示意：

```json
{
  "session_id": "web-a",
  "messages": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好，有什么可以帮你？"}
  ]
}
```

get_history() 使用进程内锁，调用 agent_graph.get_state() 读取检查点；不调用 invoke、不产生模型推理或工具执行。只展示 HumanMessage 与不包含 tool_calls 的 AIMessage 文本，过滤系统提示、工具调用请求和 ToolMessage。

新会话返回空 messages，页面给出开始提问的提示。当前历史一次性返回，暂未分页。接口与请求均禁用缓存，避免切回会话时读取过时的 HTTP 缓存。

刷新页面会回到默认会话并加载它的历史；当前选择未保存到浏览器存储，但再次输入原会话 ID 可以恢复对应会话。页面显示与数据库记录是两件事，清空显示不会删除会话。

## 7. 等待与错误处理

- sending 标记问答请求进行中；loadingHistory 标记历史读取中；historyReady 表示已可继续问答。
- updateControls() 统一控制输入、发送和切换按钮，防止请求期间重复发送或混入其他会话。
- 问答失败时保留输入并显示提示，恢复按钮；手动重试仍会再次提交问题。
- 历史加载失败时禁止发送，但允许点击切换按钮重试，同一会话也可重试。
- 历史响应检查 session_id、消息列表与角色/文本格式，避免显示不匹配的结果。
- 用户输入和回答通过 textContent 作为普通文本显示，不把其内容作为 HTML 执行；Markdown 也暂不渲染。
- 接口异常在服务端记录日志，返回给客户端的是简要提示。

## 8. 验证记录及范围

用户已提供或明确反馈的结果：

1. 根路径 GET / 返回 200，多次 POST /chat 返回 200。
2. 网页提问过程中真实执行 MCP get_current_time，终端打印时间结果。
3. 用户反馈网页会话切换测试成功。
4. 加入历史功能后，用户反馈首次打开页面会自动显示历史，并学习了 GET / 后再 GET /history 的流程。

代码开发期间的隔离检查：

- 使用真实 FastAPI 路由配合模拟服务，检查页面请求与响应字段。
- 使用模拟 DOM/fetch 检查空白拦截、重复提交、异常响应、网络失败、输入恢复、会话 ID 传递与切换保护。
- 使用临时 SQLite 保存测试消息，关闭并重新打开后，检查会话隔离、消息过滤、新会话空列表、中文参数、422/500/503 和 no-store。
- 检查首次历史加载、切换加载、响应会话不匹配拒绝、失败后同会话重试和加载期间发送保护。

这些检查没有请求付费模型或改写日常 memory.db。用户对页面的反馈不等于受控浏览器的完整视觉测试；错误分支、窄屏排版、切换历史恢复与刷新后的具体显示仍可按下一节进一步验收。

V8 的容器验收与 V7 四题成绩属于历史记录，不能当作 V9 镜像已经重新构建或容器内全套评估已通过的证据。本次存档不会启动容器、构建镜像、提交或推送 Git。

## 9. 本地复现与验收

下列命令是以后运行时的参考，不要求为了阅读报告重复启动。先确保目标端口没有被另一个服务占用。

运行当前根目录版本，在项目根目录的已激活虚拟环境中使用：

```powershell
uvicorn app.api:app --port 8001
```

uvicorn 是服务器入口，app.api:app 指模块和对象，--port 8001 指本机服务端口；默认监听 127.0.0.1。执行会初始化模型客户端、知识库、MCP 和数据库连接，初次准备可能下载向量模型。看到 Application startup complete 后访问 http://127.0.0.1:8001/，终端保持运行；Ctrl+C 停止服务。

如果需要独立复现 V9 快照，以下命令在 D:\agent\自学agent 执行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --app-dir .\versions\v9 --env-file .\.env --host 127.0.0.1 --port 8002
```

各参数的意义：指定项目 Python；-m 运行 Uvicorn 模块；--app-dir 优先导入 V9 快照代码；--env-file 把原项目配置加载到进程环境；--host 与 --port 选择本机 8002 地址。

快照会使用 versions/v9/data/memory.db 与自己的模型缓存，不会显示根目录原有会话；首次问答会请求模型并可能产生费用。配置仅加载到环境，不复制密钥文件。打开 http://127.0.0.1:8002/ 访问快照网页。

建议验收顺序：

1. 新建 test-a 会话，说“记住本会话测试代号是纸船42”。
2. 切到 test-b，确认页面没有 test-a 的消息，提问也不应凭 test-a 的记忆回答。
3. 切回 test-a，确认旧的提问与回答重新显示，继续提问能延续上下文。
4. 刷新后回到默认会话，再切 test-a，确认仍能加载历史。
5. 停止再启动同一版本服务，重复读取 test-a，检查持久化；不要删除数据库。

读取历史只查存储，发送问题才会触发智能体。使用测试数据即可，测试代号不是用户身份。

## 10. 当前边界与后续

当前是本地教学用的极简网页：没有用户登录、权限校验、历史分页、会话列表、流式输出、Markdown 渲染或消息删除。thread_id 隔离数据不等于鉴权。

本机运行的新版代码已经含网页，旧的 agent-study:v8 镜像不会自动更新。后续若验证 Docker 网页版，需要从 V9 代码构建新标签并创建新容器，按需要接回原卷；镜像、容器和持久化数据仍需分别管理。

本阶段不要求立即发布公网或加入 Nginx。先完成上述本地验收，再决定是否验证新版容器或增加其他功能。
