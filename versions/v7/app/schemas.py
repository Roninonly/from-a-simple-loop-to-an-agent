"""聊天接口的输入、输出格式；这里的数据模型不是大语言模型。"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """客户端提交的问题，以及后续用于定位对话的会话 ID。"""

    # 至少包含一个非空白字符，避免只输入空格或换行也触发模型调用。
    message: str = Field(
        min_length=1, pattern=r"\S", description="要提交的问题，不能仅包含空白字符。"
    )
    session_id: str = Field(
        default="default-session",
        min_length=1,
        pattern=r"\S",
        description="对应 LangGraph thread_id；相同 ID 复用对话，省略时使用 default-session。",
    )


class ChatResponse(BaseModel):
    """接口返回的回答和本轮使用的会话 ID。"""

    answer: str
    session_id: str
