"""Тест авторизации и HTTP-MCP: без ключа 401, с ключом MCP работает."""

import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "http://127.0.0.1:8000"
KEY = os.getenv("MCP_API_KEY")
H = {"Authorization": f"Bearer {KEY}"}

# 1) REST без ключа -> 401
r = requests.get(f"{BASE}/me", timeout=15)
print("1) REST /me без ключа:", r.status_code, "(ожидали 401)")

# 2) REST с ключом -> 200
r = requests.get(f"{BASE}/me", headers=H, timeout=15)
print("2) REST /me с ключом:", r.status_code)
me = r.json()
print("   name:", me.get("first_name"), me.get("last_name"), "| employer:", me.get("employer", {}).get("name"))

# 3) MCP без ключа -> 401
r = requests.get(f"{BASE}/mcp", timeout=15)
print("3) MCP /mcp без ключа (GET):", r.status_code, "(ожидали 401)")
r = requests.post(f"{BASE}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, timeout=15)
print("   MCP /mcp без ключа (POST initialize):", r.status_code, "(ожидали 401)")

# 4) MCP через SDK-клиент с ключом
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

url = f"{BASE}/mcp"


async def mcp_test():
    async with streamablehttp_client(url, headers=H) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("4) MCP initialize:", "OK, server =", init.serverInfo.name)

            tools = await session.list_tools()
            print("   tools:", [t.name for t in tools.tools])

            result = await session.call_tool("get_token_status", {})
            print("   get_token_status:", result.content[0].text.replace("\n", " ")[:120])

            result = await session.call_tool("whoami", {})
            print("   whoami:", result.content[0].text.replace("\n", " ")[:150])


import asyncio

asyncio.run(mcp_test())
print("AUTH + HTTP-MCP TEST OK")