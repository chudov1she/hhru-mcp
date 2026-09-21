"""Тест MCP на проде: https://hhru.chickenkiller.com/mcp"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "https://hhru.chickenkiller.com/mcp"
KEY = os.getenv("MCP_API_KEY")
H = {"Authorization": f"Bearer {KEY}"}


async def main():
    async with streamablehttp_client(URL, headers=H) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("initialize:", init.serverInfo.name)

            tools = await session.list_tools()
            print("tools:", len(tools.tools))

            result = await session.call_tool("whoami", {})
            print("whoami:", result.content[0].text.replace("\n", " ")[:120])

            result = await session.call_tool(
                "list_negotiations",
                {"vacancy_id": "137210083", "order_by": "created_at"},
            )
            data = result.content[0].text
            print("negotiations ok, length:", len(data))


asyncio.run(main())
print("PROD MCP TEST OK")