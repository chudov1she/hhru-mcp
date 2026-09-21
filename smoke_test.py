"""Быстрый smoke-тест MCP на проде: initialize + whoami через чистый JSON-RPC."""

import json

import requests

URL = "https://hhru.chickenkiller.com/mcp"
KEY = "BQGSH2k1N1r5Un1coTIK3jUyz8OnhyhWPZwVdaVk"
H = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

r = requests.post(
    URL,
    headers=H,
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "opencode-test", "version": "0"},
        },
    },
    timeout=20,
)
print("initialize:", r.status_code)
init = json.loads(r.text.split("data: ")[-1].strip())
print("server:", init["result"]["serverInfo"])

# notifications/initialized + tools/call whoami
r = requests.post(
    URL,
    headers=H,
    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    timeout=20,
)
r = requests.post(
    URL,
    headers=H,
    json={
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "whoami", "arguments": {}},
    },
    timeout=30,
)
resp = json.loads(r.text.split("data: ")[-1].strip())
text = resp["result"]["content"][0]["text"]
who = json.loads(text)
print("whoami:", who["name"], "| employer:", who["employer"]["name"])