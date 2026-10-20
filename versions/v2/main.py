"""Agent V2：使用 LangGraph 管理模型与工具之间的循环。

本阶段使用 StateGraph、模型节点、工具节点和条件路线，
代替 V1 中手写的内部 Agent Loop。
"""

import os
from datetime import datetime
from typing import Annotated, Callable, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


class AgentState(TypedDict):
    """LangGraph 中各个节点共同读取和更新的状态。"""

    messages: Annotated[list, add_messages]


def load_config() -> bool:
    """加载 .env，并检查模型连接所需的配置是否齐全。"""
    load_dotenv()

    required_names = ["MODEL_NAME", "API_KEY", "BASE_URL"]
    missing_names = []

    for name in required_names:
        if not os.getenv(name):
            missing_names.append(name)

    if missing_names:
        print(".env 配置不完整，缺少：" + ", ".join(missing_names))
        return False

    return True


def calculator(left: float, operator: str, right: float) -> float:
    """计算两个数字的加、减、乘、除。"""
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        if right == 0:
            raise ValueError("除数不能为 0。")
        return left / right

    raise ValueError(f"不支持的运算符：{operator}")


def get_current_time() -> str:
    """返回运行本程序的电脑当前日期、时间和时区。"""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


LANGGRAPH_TOOLS = [calculator, get_current_time]


def create_langgraph_model() -> Runnable:
    """创建已绑定本地工具的 LangGraph 聊天模型。"""
    model = ChatOpenAI(
        model=os.getenv("MODEL_NAME"),
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL"),
    )
    return model.bind_tools(LANGGRAPH_TOOLS)


def create_agent_node(model: Runnable) -> Callable[[AgentState], dict]:
    """创建负责调用模型并更新消息状态的节点。"""

    def agent_node(state: AgentState) -> dict:
        response = model.invoke(state["messages"])
        return {"messages": [response]}

    return agent_node


def create_tool_node() -> ToolNode:
    """创建负责执行本地工具并返回执行结果的节点。"""
    return ToolNode(LANGGRAPH_TOOLS)


def route_after_agent(state: AgentState) -> str:
    """根据模型是否请求工具，决定下一步路线。"""
    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return END


def create_agent_graph(model: Runnable) -> Runnable:
    """创建并编译模型节点与工具节点组成的状态图。"""
    graph = StateGraph(AgentState)

    graph.add_node("agent", create_agent_node(model))
    graph.add_node("tools", create_tool_node())

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "agent")

    return graph.compile()


def main() -> None:
    """程序入口。"""
    print("Agent V2 项目已初始化。")

    if not load_config():
        return

    model = create_langgraph_model()
    agent_graph = create_agent_graph(model)
    state: AgentState = {
        "messages": [
            SystemMessage(
                content="你是一个乐于助人的 AI 助手。请使用简洁的中文回答。"
            )
        ]
    }

    print("模型连接配置已加载。")
    print("LangGraph 状态图已创建。")
    print("对话状态已初始化。")
    print("输入 exit 结束对话。")

    while True:
        user_input = input("我：")

        if user_input == "exit":
            print("对话结束。")
            break

        turn_state: AgentState = {
            "messages": [
                *state["messages"],
                HumanMessage(content=user_input),
            ]
        }
        print("用户消息已加入对话状态。")

        try:
            state = agent_graph.invoke(
                turn_state,
                config={"recursion_limit": 10},
            )
            assistant_reply = (
                state["messages"][-1].content or "模型未返回文本内容。"
            )
            print(f"Agent：{assistant_reply}")
        except Exception as error:
            print(f"本轮处理失败：{error}")


if __name__ == "__main__":
    main()
