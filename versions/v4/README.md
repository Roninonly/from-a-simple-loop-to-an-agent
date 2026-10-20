# 阶段 4 报告：Agent V4 — RAG Agent

本快照在用户成功运行完整知识库问答流程后保存，便于以后与 V3 对照。

## 当前架构

准备阶段：本地 Markdown 文档 → 按章节切分 → 中文 Embedding → 内存知识库。

问答阶段：用户 → LangGraph 模型节点 → 判断是否调用工具 → ToolNode 执行
search_knowledge → 返回相关原文和来源 → 工具消息加入状态 → 模型生成答案。

SQLite Checkpointer 继续按 thread_id 保存和恢复会话。

## 相比 V3 新增了什么

- 新增 rag.py，将文档读取、切分、向量化和检索放在独立模块中。
- 使用 fastembed 加载 BAAI/bge-small-zh-v1.5，在本机 CPU 上生成 512 维向量。
- 文档按 Markdown 二级标题切成 5 个片段；每条记录包含 text、vector、source。
- 使用 NumPy 计算问题向量与片段向量的余弦相似度，按分数返回 Top-K。
- 默认 top_k=2，表示最多返回前两条片段，不是工具调用次数。
- create_retriever_tool 在启动时建立知识库，再返回 search_knowledge 函数。
- 内层工具通过闭包复用已准备的模型和知识库，工具参数只有 query。
- 模型和 ToolNode 使用同一份工具列表：计算器、当前时间、知识库检索。
- 更新系统提示，要求学习营问题查资料、注明来源、资料不足时说明未知。
- 已有会话按系统消息的原 ID 更新提示，不删除用户或助手的历史。

## 核心函数

- load_knowledge_text：读取本地文档，返回全文字符串。
- split_knowledge_text：按二级标题切分，返回片段字符串列表。
- create_embedding_model：加载本地向量模型，指定 CPU 和缓存目录。
- embed_knowledge_chunks：把每个片段转换成向量，输出顺序与原文一致。
- create_knowledge_store：把原文、向量、来源配对成内存记录。
- cosine_similarity：比较两个向量的方向接近程度，零向量返回 0。
- retrieve_knowledge：问题向量化、逐条打分、排序、返回前 top_k 条。
- create_retriever_tool / search_knowledge：准备资源并提供模型可请求的检索工具。

## 当前最小目录

```text
自学agent/
├── main.py
├── rag.py
├── requirements.txt
├── .env                 # 本机配置，不复制到快照
├── .env.example
├── .gitignore
├── data/
│   ├── agent_notes.md
│   ├── memory.db         # 运行生成，包含会话历史
│   └── embedding_models/ # 下载的模型文件，不是文档向量
└── versions/
    └── v4/
        ├── main.py
        ├── rag.py
        ├── requirements.txt
        ├── README.md
        └── data/agent_notes.md
```

快照不包含 .env、会话数据库、模型缓存或虚拟环境。
独立运行快照时，会在 versions/v4/data 下创建自己的数据库和模型缓存。
因此根目录与快照不是同一份会话历史；快照首次启动可能需要重新下载模型。
内存知识库在每次启动时重新生成，运行中不自动重读修改后的文档。

## 安装与配置

在项目根目录使用现有虚拟环境安装快照依赖：

```powershell
uv pip install --python .\.venv\Scripts\python.exe -r .\versions\v4\requirements.txt
```

本机 uv 位于 C:\Users\滕滕滕\.local\bin\uv.exe；如果 uv 不在 PATH，可使用该完整路径执行。
已经完成安装的当前环境不必重复安装。

继续使用项目根目录的 .env：

```dotenv
MODEL_NAME=你的聊天模型名称
API_KEY=你的聊天模型密钥
BASE_URL=你的聊天接口地址
```

本地向量模型不需要新增 Embedding API Key，不要提交真实 .env。
首次下载模型需要联网；聊天模型调用也需要能访问已配置的接口。
实际验收使用 Python 3.12.14、fastembed 0.9.0；依赖清单沿用项目未固定版本的写法。

## 启动与测试

以下命令都在项目根目录执行；未激活虚拟环境时使用明确的解释器路径。

当前版本：

```powershell
.\.venv\Scripts\python.exe .\main.py
```

V4 历史快照：

```powershell
.\.venv\Scripts\python.exe .\versions\v4\main.py
```

独立检索测试：

```powershell
.\.venv\Scripts\python.exe .\versions\v4\rag.py
```

最简单的完整测试问题：

```text
一个学员可以借用8台吗？请查询学习营资料并注明来源。
```

预期先看到“知识库检索问题”以及设备借用片段，然后模型回答一次最多借 1 台，
并注明 data/agent_notes.md。检索词可能由模型改写，检索次数和答案措辞不固定。
输入 exit 结束；/session 会话名切换仍与 V3 相同。

## 验证结果

- 真实中文向量模型成功产生 5 个向量，每个 512 维，数值有效。
- 文本与向量配对、空输入、数量不一致保护测试通过。
- 余弦相似度、Top-K、空问题及无效 top_k 测试通过。
- 答疑时间、作业截止、设备借用、阶段验收四类问题均首条命中目标片段。
- 临时 SQLite 数据库中的工具循环、旧提示更新、历史恢复和会话隔离通过。
- 真实聊天模型调用检索工具、收到 ToolMessage、引用来源回答通过。
- 真实聊天模型调用计算器计算 123*123=15129 通过。
- 用户成功测试设备申请联系人：检索命中林舟，最终回答并注明资料来源。
- 自动化集成验收使用临时数据库，未把测试对话写进用户的真实数据库。

## 常见问题与边界

- import 报错：优先检查是否使用项目 .venv，而不是系统 Python。
- 找不到文档：确认所运行 rag.py 同级的 data/agent_notes.md 存在。
- 首次加载停留较久：看下载日志；缓存未准备好时不能跳过模型下载。
- Windows 符号链接警告或匿名下载警告不一定意味着失败，以最终结果为准。
- 模型调用失败：检查网络、接口配置和返回错误；不要公开密钥。
- 检索不相关：Top-K 只表示相对排名，目前没有最低分数过滤，也不保证片段有答案。
- 相似度不是概率或正确率，512 个向量数字也不适合逐个解释成具体词义。
- 多次“知识库检索问题”可能是模型请求多次工具调用，不是重新建立知识库。
- RAG 资料默认对所有会话共享；thread_id 隔离的是聊天记录，不是知识库权限。
- SQLite 保存会话历史；文档向量仍在内存中，关闭后丢失，下次启动重新建立。
- 失败可能留下中间检查点，尚未实现完善的重试和会话修复。
- 文档及学习营规则为教学虚构，不代表真实人物、机构或借用政策。

## 当前还不具备

- 持久化向量索引、大规模检索或复杂 PDF 处理。
- 分数阈值、重排序、严格的答案验证或完善的知识库权限隔离。
- 跨会话用户画像、历史摘要和消息裁剪。
- MCP、FastAPI、正式 Evaluation 测试集或 Docker 部署。

下一阶段是阶段 5 MCP：把现有工具的执行扩展为通过 MCP Client 调用本地 MCP Server。
当前快照不包含阶段 5 代码，等待用户明确要求继续下一阶段。
