"""Agent V5 的本地 MCP Server：提供当前时间、计算器和文字计数工具。"""

from datetime import datetime

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError


server = MCPServer("agent-tools")


@server.tool()
def get_current_time() -> str:
    """返回运行 MCP Server 的电脑当前日期、时间和时区。"""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


@server.tool()
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
            raise ToolError("除数不能为 0。")
        return left / right

    raise ToolError(f"不支持的运算符：{operator}")


@server.tool()
def count_text_characters(text: str) -> int:
    """按 Python len 统计文本长度，空格、标点和换行也计入。"""
    return len(text)


if __name__ == "__main__":
    # 标准输出用于 MCP 通信，不在这里打印普通提示。
    server.run(transport="stdio")
