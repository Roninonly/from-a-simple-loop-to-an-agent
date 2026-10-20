"""Agent V6 的 HTTP 入口：接收请求并调用共享智能体服务。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import contextmanager_in_threadpool

from app.agent_service import create_agent_service
from app.schemas import ChatRequest, ChatResponse


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """服务启动时准备智能体，关闭时退出上下文、释放数据库连接。"""
    # 库提供的线程池桥接：同步初始化中的 asyncio.run 不进入 HTTP 事件循环。
    async with contextmanager_in_threadpool(create_agent_service()) as service:
        application.state.agent_service = service
        try:
            yield
        finally:
            application.state.agent_service = None


app = FastAPI(title="Agent V6 API", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """仅检查 HTTP 服务是否能响应，不检查模型、知识库或 MCP。"""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    """按会话调用智能体；普通 def 由 FastAPI 在线程池中执行。"""
    service = getattr(http_request.app.state, "agent_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="智能体服务尚未就绪。")

    try:
        answer = service.ask(request.message, request.session_id)
    except Exception:
        logger.exception("智能体处理失败。")
        # 不向接口调用方暴露模型配置、底层报错或其他内部信息。
        raise HTTPException(
            status_code=500, detail="智能体处理失败，请查看服务终端日志。"
        ) from None

    return ChatResponse(answer=answer, session_id=request.session_id)
