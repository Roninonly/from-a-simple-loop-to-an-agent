"""Agent V5 的 MCP Client：自动发现工具，并转换成 LangGraph 可执行的工具。"""

import asyncio
import sys
from pathlib import Path

from langchain_core.tools import StructuredTool, ToolException
from mcp import Client, StdioServerParameters
from mcp.types import Tool


def create_mcp_client() -> Client:
    """创建客户端配置，连接时才启动同目录下的 MCP Server。"""
    server_path = Path(__file__).resolve().parent / "mcp_server.py"
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    return Client(server_params, raise_exceptions=True, read_timeout_seconds=15)


async def call_mcp_tool(name: str, arguments: dict) -> str:
    """建立连接并按名称调用，关闭连接后提取文本及检查工具错误。"""
    async with create_mcp_client() as client:
        result = await client.call_tool(name, arguments)

    # 在连接关闭后抛出工具错误，避免被连接上下文包装成异常组。
    texts = []
    for content in result.content:
        if content.type == "text":
            texts.append(content.text)

    if result.is_error:
        raise ToolException(f"MCP 工具 {name} 调用失败：" + "\n".join(texts))
    if not texts:
        raise ToolException(f"MCP 工具 {name} 没有返回文本内容。")
    return "\n".join(texts)


def create_mcp_tool(definition: Tool) -> StructuredTool:
    """将一份 MCP 工具定义转换成带执行入口的 LangChain 工具。"""
    name = definition.name

    async def request_tool(**arguments) -> str:
        print(f"正在通过 MCP 调用工具：{name}，参数：{arguments}")
        value = await call_mcp_tool(name, arguments)
        print(f"MCP 工具 {name} 执行结果：{value}")
        return value

    def invoke_tool(**arguments) -> str:
        return asyncio.run(request_tool(**arguments))

    return StructuredTool(
        name=name,
        description=definition.description or f"调用 MCP 工具 {name}。",
        args_schema=definition.input_schema,
        func=invoke_tool,
        coroutine=request_tool,
        # 把工具执行失败交回模型，并将对应工具消息标记为错误。
        handle_tool_error=True,
    )


async def load_mcp_tools() -> list[StructuredTool]:
    """读取 Server 的全部工具定义，逐个转换；这里只登记，不执行工具。"""
    tools = []
    async with create_mcp_client() as client:
        cursor = None
        while True:
            result = await client.list_tools(cursor=cursor)
            for definition in result.tools:
                tools.append(create_mcp_tool(definition))
                print(f"已发现 MCP 工具：{definition.name}")

            cursor = result.next_cursor
            if not cursor:
                break

    if not tools:
        raise RuntimeError("MCP Server 没有提供可用工具。")
    return tools


async def main() -> None:
    """独立测试：发现并转换工具，展示参数规则，不自动执行工具。"""
    tools = await load_mcp_tools()
    print(f"MCP 工具已自动加载，共 {len(tools)} 个。")
    for tool in tools:
        print(f"- {tool.name}：{tool.description}")
        print(f"  参数规则：{tool.args_schema}")
    print("工具发现连接已关闭，Server 子进程已结束。")


if __name__ == "__main__":
    asyncio.run(main())
