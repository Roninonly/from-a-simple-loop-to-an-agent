"""Agent V1：支持 Tool Calling 的手写 Agent Loop。

本阶段不使用 Agent 框架，由 Python 代码负责执行模型请求的工具，
再把工具结果放回 messages，直到模型生成最终回答。
"""

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI


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


def create_llm_client() -> OpenAI:
    """创建一个可连接 OpenAI-compatible 模型服务的客户端。"""
    return OpenAI(
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL"),
    )


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


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "计算两个数字的加、减、乘、除。",
            "parameters": {
                "type": "object",
                "properties": {
                    "left": {"type": "number", "description": "左边的数字。"},
                    "operator": {
                        "type": "string",
                        "enum": ["+", "-", "*", "/"],
                        "description": "要执行的运算符。",
                    },
                    "right": {"type": "number", "description": "右边的数字。"},
                },
                "required": ["left", "operator", "right"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取运行本程序的电脑当前日期、时间和时区。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def main() -> None:
    """程序入口。"""
    print("Agent V1 项目已初始化。")

    if load_config():
        client = create_llm_client()
        messages = [
            {
                "role": "system",
                "content": "你是一个乐于助人的 AI 助手。请使用简洁的中文回答。",
            }
        ]
        print("模型连接配置已加载。")
        print("模型客户端已创建。")
        print("对话历史已初始化。")
        print("输入 exit 结束对话。")

        while True:
            user_input = input("我：")

            if user_input == "exit":
                print("对话结束。")
                break

            messages.append({"role": "user", "content": user_input})
            print("用户消息已加入对话历史。")

            try:
                model_call_count = 0
                # 围绕当前用户问题继续处理工具请求，最多请求模型 5 次。
                while model_call_count < 5:
                    model_call_count += 1
                    response = client.chat.completions.create(
                        model=os.getenv("MODEL_NAME"),
                        messages=messages,
                        tools=TOOLS,
                    )
                    assistant_message = response.choices[0].message
                    tool_calls = assistant_message.tool_calls or []

                    if not tool_calls:
                        assistant_reply = assistant_message.content or "模型未返回文本内容。"
                        messages.append({"role": "assistant", "content": assistant_reply})
                        print(f"Agent：{assistant_reply}")
                        break

                    # 一条模型消息可以包含多个工具请求，只保存一次。
                    messages.append(assistant_message)
                    for tool_call in tool_calls:
                        print(f"模型请求调用工具：{tool_call.function.name}")
                        print(f"模型传入参数：{tool_call.function.arguments}")

                        try:
                            tool_arguments = json.loads(tool_call.function.arguments)
                            if tool_call.function.name == "calculator":
                                tool_result = calculator(
                                    left=tool_arguments["left"],
                                    operator=tool_arguments["operator"],
                                    right=tool_arguments["right"],
                                )
                            elif tool_call.function.name == "get_current_time":
                                tool_result = get_current_time()
                            else:
                                raise ValueError("当前程序暂不支持执行这个工具。")

                            print(f"本地工具执行结果：{tool_result}")
                        except (ValueError, KeyError, TypeError) as error:
                            tool_result = f"工具执行失败：{error}"
                            print(tool_result)

                        # 成功或失败，都把结果与本次请求编号对应起来。
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": str(tool_result),
                            }
                        )
                    print("工具结果已加入对话历史。")

                if model_call_count == 5 and tool_calls:
                    print("本轮已达到 5 次模型请求上限，暂未获得最终回答。请简化问题后重试。")
            except Exception as error:
                print(f"本轮处理失败：{error}")


if __name__ == "__main__":
    main()
