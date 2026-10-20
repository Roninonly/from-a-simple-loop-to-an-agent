# 使用带 Python 3.12 的轻量 Linux 环境，不复制 Windows 的 .venv。
FROM python:3.12-slim-bookworm

# 日志及时输出、不生成字节码，并为时间工具设置容器时区。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 这是容器内的项目目录，不是电脑上的 D 盘路径。
WORKDIR /app

# 为 CPU 推理准备 OpenMP 运行库，并安装时区资料；仅在构建镜像时执行。
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libgomp1 tzdata \
    && rm -rf /var/lib/apt/lists/*

# 先安装依赖；源码变化但清单不变时，可复用这一层的构建缓存。
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

# 只复制当前应用、评估代码和知识文档，不复制密钥或历史聊天数据库。
COPY app/ ./app/
COPY main.py rag.py mcp_client.py mcp_server.py ./
COPY eval/ ./eval/
COPY data/agent_notes.md ./data/agent_notes.md

# 运行阶段使用普通用户，允许程序在项目目录写入数据库、缓存和评估报告。
RUN useradd --create-home --uid 10001 agent \
    && chown -R agent:agent /app
USER agent

# 声明容器内服务端口；这行不会自动映射到宿主机或开放公网。
EXPOSE 8000

# 容器内监听全部接口，宿主机的访问范围由后续端口映射决定。
# 当前会话处理按单进程设计，明确只启动一个工作进程。
CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
