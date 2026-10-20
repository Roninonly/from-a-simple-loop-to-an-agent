# 阶段 8 报告：Docker 本地运行与数据持久化

【当前 Agent 版本】Agent V8：保留 V7 的聊天、MCP 工具、RAG、会话记忆、HTTP 接口和评估能力，增加 Linux 容器镜像及本地 Docker 验证。

## 一、本阶段解决的问题

此前项目依赖 Windows 上的 Python 虚拟环境。V8 用 Dockerfile 描述另一套可重建的 Linux 运行环境，让项目可以构建成镜像，再从镜像启动容器。镜像保存程序和依赖；运行时产生的会话数据库与向量模型缓存交给命名卷保存。

本阶段验证的是**在 Windows 主机的 Docker Desktop 中运行 Linux 容器**，不是发布到公网。Docker Desktop 使用 WSL 2 后端；没有要求安装 Ubuntu。业务源码、题库与 V7 相同，没有重新实现智能体或加入网页前端。
由于终端入口和 HTTP 接口的业务代码未修改，它们显示的 `Agent V6` 名称仍沿用原版本；`V8` 表示整个项目增加了 Docker 运行能力，不表示另写了一套聊天智能体。

## 二、快照内容与文件作用

```text
v8/
├── Dockerfile              # 构建镜像的步骤
├── .dockerignore           # 排除密钥、数据库、缓存和历史快照
├── main.py                 # 终端入口
├── app/                    # FastAPI 接口与共享智能体服务
├── rag.py                  # 知识库加载与检索
├── mcp_client.py           # MCP 客户端与工具适配
├── mcp_server.py           # MCP 工具服务端
├── eval/                   # 评估题库与执行器，不含运行报告
├── data/agent_notes.md     # 虚构的知识库测试资料
├── requirements.txt        # Python 依赖清单
└── README.md               # 本报告
```

快照包含根目录当前的 14 个源码和构建配置文件，以及本报告。除 Dockerfile、.dockerignore 之外，其余业务源码、依赖和题库与 V7 对应文件一致。没有复制 `.env`、真实 API Key、SQLite 数据库、模型缓存、虚拟环境、字节码或评估运行报告。

Dockerfile 以 `python:3.12-slim-bookworm` 为基础，安装系统和 Python 依赖，仅复制应用所需文件；创建普通用户 `agent`，用单个 Uvicorn 进程监听容器内部 8000 端口。`EXPOSE 8000` 只是声明端口；能否从电脑访问，由 `docker run -p` 决定。

`.dockerignore` 阻止把 `.env`、`data/*.db*`、`data/embedding_models/`、`eval/results/`、`.venv/` 和 `versions/` 放入构建上下文。`.env` 的值在启动容器时通过 `--env-file` 提供，**不写进镜像**；不过有权限管理本机 Docker 的人仍可能查看容器环境变量，不能把带真实密钥的容器交给不可信的人。

## 三、镜像、容器和卷的关系

```text
Dockerfile + 项目文件 → agent-study:v8 镜像
                              ↓ docker run
                        一次运行的容器
                              ↓ /app/data
                      agent-study-v8-data 命名卷
```

- `docker build` 制作镜像；`docker image ls` 只查看镜像。
- `docker run` 每执行一次就创建一个新容器；`--name` 指定容器名。
- `--rm` 使容器停止后自动删除，**不会删除挂载的命名卷**。
- `--mount type=volume,source=agent-study-v8-data,target=/app/data` 把卷接到容器内部 `/app/data`。该目录下的 `memory.db` 和 `embedding_models/` 因而独立于容器保存。
- `-p 127.0.0.1:8000:8000` 只把本机的 8000 端口转给容器的 8000 端口；其他电脑不能靠访问它们自己的 `127.0.0.1` 连接这台电脑。

新建空卷第一次接到 `/app/data` 时，Docker 会把镜像中已有的 `agent_notes.md` 复制进卷。这保证首次启动仍能读取知识文档；但**以后更新镜像中的知识文档，不会自动覆盖已有卷中的旧文档**。正式部署前应把静态知识文档与可变数据库、缓存分开，或制定知识文档更新流程。

`docker inspect` 显示的卷 `Source` 如 `/var/lib/docker/volumes/...` 是 Docker 的 Linux 内部路径，不是 Windows 盘符。本次用户在 Docker Desktop 设置中确认数据磁盘位于 D 盘；卷由 Docker 管理，不表现为一个普通的同名 Windows 文件夹。换电脑时，镜像和卷不会自动一起转移，卷需要单独备份或迁移。

## 四、从快照复现

下面的命令在项目根目录 `D:\agent\自学agent` 执行；仅供以后复现，当前已完成的验证不需要再重复运行。构建需要 Docker 引擎和下载依赖的网络；首次启动可能下载向量模型。`POST /chat` 会请求模型并可能产生 API 费用。

```powershell
docker build --progress=plain -t agent-study:v8-snapshot ".\versions\v8"
```

其中 `build` 制作镜像，`--progress=plain` 显示普通文字日志，`-t` 指定镜像名，最后的路径指定构建目录，Docker 默认读取该目录下的 Dockerfile。快照镜像使用新标签，不覆盖已经验证的 `agent-study:v8` 标签。

```powershell
docker volume create agent-study-v8-snapshot-data
```

这会创建独立的 Docker 命名卷，不复用开发版的会话数据库；输出卷名表示卷可用。

```powershell
docker run --rm --name agent-study-v8-snapshot --env-file ".\.env" --mount "type=volume,source=agent-study-v8-snapshot-data,target=/app/data" -p 127.0.0.1:8000:8000 agent-study:v8-snapshot
```

这会从快照镜像启动新容器，把项目根目录的 `.env` 值在运行时交给程序，挂载快照专用卷，并仅允许本机访问 8000 端口。终端保持打开；看到 `Application startup complete` 后可访问 `http://127.0.0.1:8000/health` 和 `http://127.0.0.1:8000/docs`。停止容器会使本机接口暂时不可用，但命名卷继续保留。不要在现有服务占用 8000 端口时同时运行此命令。

## 五、真实验收记录

用户于 2026-10-14 至 2026-10-15 在 Windows 上完成了以下本地验证：

1. `docker build` 成功生成 `agent-study:v8`；`docker image ls` 可查询到镜像。
2. 无挂载的临时容器启动成功，`GET /health` 返回 `200` 和 `{"status":"ok"}`；`POST /chat` 返回 `200` 和模型回答。
3. `docker inspect --format '{{json .Mounts}}'` 对无挂载容器返回 `[]`。
4. 创建 `agent-study-v8-data` 命名卷后，新容器启动成功；挂载信息包含 `Type=volume`、卷名和 `Destination=/app/data`、`RW=true`。
5. 在会话 `docker-volume-check` 中告知测试代号“小蓝”，停止并自动删除容器，再用同一个镜像和同一个卷创建新容器；新容器用相同会话回答“你的测试代号是小蓝”。这验证了会话数据库跨**容器重建**保留。
6. Docker Desktop 设置显示数据磁盘在 D 盘。根目录原有的 `data/memory.db` 没有挂进容器，也没有被这次测试覆盖。

验收说明：这证明了本机镜像构建、容器启动、HTTP 问答及会话持久化；没有重新构建并运行本历史快照，也没有验证公网部署、跨电脑迁移、并发、备份恢复或生产安全性。V7 的四题评估结果不等于 V8 的容器内评估；本阶段未在容器中重新运行整套评估。

## 六、当前边界和后续

- 现在只有 API 文档页面，不是最终给普通用户使用的聊天前端；按照学习计划，网页前端放在后面。
- 当前端口仅绑定 `127.0.0.1`，未开放公网，也没有鉴权、HTTPS 或反向代理。
- 卷保存数据库和模型缓存，但还没有做备份与跨电脑恢复演练；删除卷会丢失其中的数据。
- 同一个卷内同时放静态知识文档和可变数据，后续更新资料时要处理旧文档问题。
- 重新构建镜像不会自动更新已经创建的容器；需要用新镜像重新创建容器，挂回原卷。
- 后续可以整理更易复用的启动配置，并在保证数据安全的前提下验证部署流程；不需要为了本阶段结果立刻增加复杂编排。
