"""Agent V5 的本地 MCP Server：提供当前时间工具。"""

from datetime import datetime

from mcp.server import MCPServer


server = MCPServer("agent-time-tools")


@server.tool()
def get_current_time() -> str:
    """返回运行 MCP Server 的电脑当前日期、时间和时区。"""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


if __name__ == "__main__":
    # 标准输出用于 MCP 通信，不在这里打印普通提示。
    server.run(transport="stdio")
