"""Agent V6 的终端入口：与 HTTP 接口共用智能体服务。"""

from app.agent_service import create_agent_service


def main() -> None:
    """保留终端聊天、会话切换和退出操作。"""
    print("Agent V6 项目已初始化。")

    with create_agent_service() as service:
        current_session_id = "default-session"
        print(f"当前会话：{current_session_id}")
        print("输入 /session 会话名 切换会话。")
        print("输入 exit 结束对话。")

        while True:
            user_input = input("我：")
            if user_input == "exit":
                print("对话结束。")
                break

            if user_input == "/session":
                print("请在 /session 后输入会话名，例如：/session xiaoming")
                continue

            if user_input.startswith("/session "):
                new_session_id = user_input.removeprefix("/session ").strip()
                if not new_session_id:
                    print("会话名不能为空。")
                    continue
                current_session_id = new_session_id
                print(f"已切换到会话：{current_session_id}")
                continue

            try:
                answer = service.ask(user_input, current_session_id)
                print(f"Agent：{answer}")
            except Exception as error:
                print(f"本轮处理失败：{error}")


if __name__ == "__main__":
    main()
