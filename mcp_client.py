"""Agent V5 的 MCP Client：提供 Agent 可调用的时间工具及独立通信测试。"""

import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


def create_mcp_client() -> Client:
    """创建客户端配置，连接时才启动同目录下的 MCP Server。"""
    server_path = Path(__file__).resolve().parent / "mcp_server.py"
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    return Client(server_params, raise_exceptions=True, read_timeout_seconds=15)


async def call_time_tool(client: Client) -> str:
    """通过已连接的客户端调用时间工具，将文本内容提取成字符串。"""
    result = await client.call_tool("get_current_time", {})
    texts = []
    for content in result.content:
        if content.type == "text":
            texts.append(content.text)

    if not texts:
        raise RuntimeError("MCP 时间工具没有返回文本内容。")
    return "\n".join(texts)


def get_current_time() -> str:
    """通过本地 MCP Server 查询当前日期、时间和时区。"""
    async def request_time() -> str:
        async with create_mcp_client() as client:
            return await call_time_tool(client)

    print("正在通过 MCP 调用当前时间工具。")
    value = asyncio.run(request_time())
    print(f"MCP 时间工具执行结果：{value}")
    return value


async def main() -> None:
    """独立测试：发现工具并调用一次，然后关闭连接。"""
    async with create_mcp_client() as client:
        print("MCP Client 已连接本地 Server。")
        tool_list = await client.list_tools()
        print("Server 提供的工具：")
        for tool in tool_list.tools:
            print(f"- {tool.name}：{tool.description}")

        value = await call_time_tool(client)
        print(f"MCP 时间工具返回：{value}")

    print("MCP 连接已关闭，Server 子进程已结束。")


if __name__ == "__main__":
    asyncio.run(main())
