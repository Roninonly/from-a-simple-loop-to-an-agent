# 阶段 7 报告：Evaluation Agent

【当前 Agent 版本】Agent V7：在 V6 智能体服务上增加最小评估题库、执行器和结果报告。

## 一、本阶段解决的问题

V6 已能通过终端或 HTTP 使用模型、MCP 工具、RAG 和会话历史。
V7 把手工随意提问变为固定题库与明确判定条件，重复运行后可以对比结果，
并区分答案、工具调用和检索证据。没有重写智能体，也没有新增网页界面。

本阶段采用本地 Python 规则，不引入评估框架或另一个评分模型。
运行核心仍是 V6 的 AgentService；终端与接口的版本提示也沿用 V6，
V7 表示整个项目增加了评估能力，不表示复制了另一套聊天智能体。

## 二、目录与新增内容

```text
v7/
├── main.py
├── app/
│   ├── __init__.py
│   ├── api.py
│   ├── schemas.py
│   └── agent_service.py
├── rag.py
├── mcp_client.py
├── mcp_server.py
├── requirements.txt
├── data/
│   └── agent_notes.md
├── eval/
│   ├── dataset.json
│   └── evaluator.py
└── README.md
```

本阶段新增 eval/dataset.json、eval/evaluator.py；.gitignore 增加生成报告的忽略规则。
题库定义四类测试和预期要求，执行器负责真实问答、证据采集、检查、汇总和保存。
初期用预设答案、工具名单、检索片段及消息演示，理解规则后移除了演示入口，
改为默认预览题库，显式 --run 才执行真实模型调用。

没有新增依赖，使用已有消息类与 Python 标准库；V6 的业务文件保持不变。
快照共 13 个文件，包含源码、题库、依赖清单、虚构知识文档和本报告。
不复制 .env、聊天数据库、模型缓存、虚拟环境、字节码或 eval/results/ 运行记录。

## 三、题库与规则

| 题目 | 问题数量 | 判定要求 |
| --- | --- | --- |
| chat_exact_reply | 1 | 最终回答为青竹，忽略首尾空白 |
| tool_calculator | 1 | 最终回答包含15129，且calculator成功执行 |
| rag_device_contact | 1 | 回答包含林舟与来源路径，search_knowledge成功执行，检索文字包含目标句子 |
| memory_remember_name | 2 | 同一新会话先告知小红，再追问，最后回答包含小红 |

id、category、questions、expected 等字段由我们设计，不是 FastAPI 或 LangGraph 自动规定。
questions 是按顺序提交的字符串列表，expected 不发给模型，只供执行器评分。
每题使用新的随机会话，题内多次提问共用同一会话。
因此一次运行提交 5 次用户消息；工具循环、重试等可能增加模型 API 调用次数。

## 四、函数调用关系

### main()：组织整次评估

解析 --run，调用 load_dataset()，列出题目；没有 --run 就返回，不加载智能体。
有 --run 时先把项目根目录加入 sys.path，再导入 create_agent_service()。
创建临时 SQLite 数据库，初始化一次智能体服务，逐题调用 evaluate_case()。
收集每题结果，退出上下文关闭并清理临时数据库，然后依次调用：

```python
summary = summarize_results(results)
print_summary(summary)
output_path = save_results(results, summary)
```

这条路径直接调用 AgentService，不经过 FastAPI，不需要启动 Uvicorn 或打开网页。

### evaluate_case()：完成并检查一道题

1. 创建新会话、开始计时，初始化失败列表和检查状态。
2. 按顺序调用 service.ask()，answer 最终保存最后一次回复。
3. get_state() 读取本题的消息状态；这是读取检查点，不是再次请求模型。
4. collect_execution_records() 提取成功工具名单和 RAG 返回文字。
5. 调用 check_answer()、check_tools()、check_retrieval()，合并失败原因。
6. 返回题号、会话、问题与规则、回答、执行证据、分项检查、是否通过及耗时。

单题执行异常记为失败并继续后面的题，不把异常文本中的内部信息直接写进结果。
初始化失败则无法开始整次评估。没有配置某项要求时，对应检查状态是 None；
有要求但执行报错时是 False，成功检查后才更新为 True。

### collect_execution_records()：证据提取，不是内容评分

遍历 AIMessage.tool_calls，以请求 ID 登记工具名；再用 ToolMessage.tool_call_id 配对。
只计入配对成功且 status 为 success 的结果，同一工具名在名单中去重。
只从 search_knowledge 的成功文本结果提取检索资料，并合并多次检索的返回文字。
模型声称使用工具、只提出请求、失败或无法配对的结果，都不算成功证据。

### 三个检查函数

- check_answer()：检查 answer_equals 和 answer_contains。
- check_tools()：检查 required_tools 是否都在成功执行名单中。
- check_retrieval()：检查 retrieved_contains 是否都出现在检索返回文字中。

它们返回失败原因列表，不直接打印，也不执行工具。空列表仅表示该函数检查的条件通过。
每题都会调用三个函数，但没有配置对应条件时不检查该部分。
全部配置条件无失败时，passed 为 True；任何条件失败或执行异常时为 False。

## 五、汇总口径

summarize_results() 计算，print_summary() 显示；百分比格式化不重新执行计算。

| 指标 | 分子与分母 |
| --- | --- |
| 任务成功率 | 整题通过数 / 全部题数 |
| 答案文字条件通过率 | 答案条件通过题数 / 配置了答案条件的题数 |
| 必需工具检查通过率 | 工具条件通过题数 / 配置了必需工具的题数 |
| 目标资料命中率 | 检索条件通过题数 / 配置了检索目标的题数 |
| 平均每题耗时 | 所有题的耗时之和 / 全部题数 |

工具指标包含计算器题和 RAG 题，因此当前分母是 2，不是只有 tool 类别的 1 题。
检索指标当前分母是 1。None 不计入分母，False 必须计入；没有适用题目时，
比例为 None 并显示不适用，不显示虚假的 0% 或 100%。

每题耗时包括题内全部问答和检查，不含智能体初始化，也不含最后的汇总、报告保存。
记忆题含两次提问，不是单次请求延迟；失败题耗时也计入平均值。

## 六、结果保存与安全

save_results() 在当前版本的 eval/results/ 下创建带日期时间及随机编号的新 JSON 文件。
时间明确使用 +08:00；UTF-8 编码保留中文，x 模式拒绝覆盖已存在的同名文件。
报告包含 report_version、created_at、指标范围说明、summary、逐题 results。
每题保存问题和 expected 快照，之后修改题库仍能知道旧成绩使用的判定条件。

保存函数不读取 .env 或数据库，不保存 API Key 或完整应用配置。
但报告包含问题、模型回答和检索资料；以后换成真实业务数据时不要随意公开报告。
开发版与快照的报告目录均加入 .gitignore，原有本地报告不会被删除。
临时会话数据库在运行结束后清理，真实 data/memory.db 不受影响。

## 七、运行方式

以下命令在 D:\agent\自学agent 项目根目录执行，使用现有虚拟环境。
本阶段无新依赖、无需安装新软件；以后重建环境时先确认再按 requirements.txt 安装。
.env 仍使用 MODEL_NAME、API_KEY、BASE_URL，无新增配置。

开发版只预览，不请求模型、不创建评估数据库或结果文件：

```powershell
python eval/evaluator.py
```

开发版真实运行，会调用模型并可能产生费用：

```powershell
python eval/evaluator.py --run
```

预览本历史快照：

```powershell
.\.venv\Scripts\python.exe .\versions\v7\eval\evaluator.py
```

真实运行快照，先由新进程加载原项目 .env，不复制密钥：

```powershell
.\.venv\Scripts\python.exe -c "from dotenv import load_dotenv; import sys, runpy; load_dotenv('.env'); sys.argv=['evaluator.py', '--run']; runpy.run_path('versions/v7/eval/evaluator.py', run_name='__main__')"
```

运行快照的 HTTP 入口可使用：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --app-dir .\versions\v7 --env-file .\.env --host 127.0.0.1 --port 8000
```

快照 service 明确读取自身根目录的 .env，不能假设自动向上查找原配置。
上面的启动方式预先把原配置加载到进程环境；环境变量已存在时，后续配置检查仍能通过。
快照使用自己的 data/embedding_models 缓存，首次真实运行可能下载模型；
日常对话数据库和结果报告也与开发版分开，评估的会话数据库仍只使用临时目录。

## 八、真实验收结果

用户于 2026-10-13 运行真实四题评估，并成功保存：

`eval/results/run-20261013-220249-33cdb208.json`

已读取并核对该开发版 JSON 报告，与用户终端输出一致；该运行文件保留原处，不复制进快照。

- 任务成功率：100.0%（4/4）。
- 答案文字条件通过率：100.0%（4/4）。
- 必需工具检查通过率：100.0%（2/2）。
- 目标资料命中率：100.0%（1/1）。
- 平均每题耗时：约 1.71 秒，不含初始化。

计算器的实际执行与 RAG 检索均有消息和终端证据；记忆题在第二次提问时回答小红。
这是本次四道基础题的结果，不是通用知识准确率，也不是模型能力的稳定统计结论。

开发过程中还用预设模型、工具和临时 SQLite 验证了默认预览不加载智能体、
错误与缺失工具不能通过、会话唯一及题内复用、初始化复用、临时数据库关闭清理、
混合失败的指标分母、不适用项、报告读回、中文编码和拒绝覆盖。
这些离线检查没有请求模型 API 或修改真实聊天数据库，不能冒充真实模型能力评估。

## 九、当前边界与常见问题

- 字符串包含检查不理解语义；包含正确关键词的否定句也可能误判。
- required_tools 只验证成功工具名，不验证参数、计算器原始返回值或是否调用了多余工具。
- 检索检查只验证目标文字出现在返回资料中，不计算排名、Precision、Recall 或通用检索质量。
- 当前普通回复题主要检查遵循格式，不代表广泛知识问答正确性。
- 四题规模很小，单次全通过不能证明真实业务整体可靠；后续应扩展失败题、边界题和多次运行。
- 题库目前只有基础结构检查；修改判定键名时必须对照代码，未实现完整 schema 校验。
- 只评估 Agent 核心，不等于压测 HTTP 服务、鉴权或并发安全。
- 暂未统计 Token、模型调用成本、完整模型配置和依赖锁定信息，不能做精确成本或完全可复现实验比较。
- 单题失败会打印失败原因或异常类型；初始化失败查看启动报错，保存失败检查路径权限或磁盘空间。
- 暂未用失败题控制命令行退出码，自动化接入时应读取 JSON，不应只看进程是否正常结束。
- 不加 --run 只预览；没有生成新报告是预期行为，不是保存故障。

## 十、阶段结论与后续顺序

已具备：固定题库、隔离的真实评估、成功工具与检索证据提取、基础条件检查、
分项通过率、整题耗时、不可覆盖的本地报告，以及原有全部 V6 能力。

尚未实现：生产级评估、语义评分、全面工具参数校验、完整成本观测和 Docker 部署。

下一阶段是 V8 Docker，之后再增加用户要求的极简聊天网页。
本次没有提前实现 Docker 或前端，等待用户明确要求继续下一阶段。
