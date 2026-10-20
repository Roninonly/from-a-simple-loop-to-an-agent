"""Agent V0：手写最基础的 Agent Loop。"""

import os

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


def main() -> None:
    """程序入口。"""
    print("Agent V0 项目已初始化。")

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
                response = client.chat.completions.create(
                    model=os.getenv("MODEL_NAME"),
                    messages=messages,
                )
                assistant_reply = response.choices[0].message.content or "模型未返回文本内容。"
                messages.append({"role": "assistant", "content": assistant_reply})
                print(f"Agent：{assistant_reply}")
            except Exception as error:
                print(f"模型调用失败：{error}")


if __name__ == "__main__":
    main()
