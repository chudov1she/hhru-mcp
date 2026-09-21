"""
MCP-сервер "hh-connector" (транспорт stdio) для работы с hh.ru от имени работодателя.

Используется для подключения через конфиг клиента (Claude Desktop, Claude Code,
Hermes, Cursor и др.). Описание tools — в mcp_common.py.

Запуск:
  python mcp_server.py
"""

import sys

from dotenv import load_dotenv

load_dotenv()

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError:
    print("MCP SDK не установлен: pip install mcp", file=sys.stderr)
    raise

import mcp_common


async def main():
    server = Server("hh-connector")

    @server.list_tools()
    async def handle_list_tools(*_) -> list:
        return mcp_common.TOOLS

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list:
        return await mcp_common.call_tool(name, arguments)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())