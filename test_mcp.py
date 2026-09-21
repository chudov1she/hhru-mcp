"""Тест MCP-сервера через stdio: initialize, tools/list, вызов read-only tools."""

import json
import subprocess
import sys

PROC = [
    sys.executable,
    "-X",
    "utf8",
    "mcp_server.py",
]

p = subprocess.Popen(
    PROC,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
)


def send(msg):
    p.stdin.write(json.dumps(msg) + "\n")
    p.stdin.flush()


def recv():
    return json.loads(p.stdout.readline())


# 1. initialize
send(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    }
)
resp = recv()
print("initialized:", resp["result"]["serverInfo"])

# 2. initialized notification
send({"jsonrpc": "2.0", "method": "notifications/initialized"})

# 3. tools/list
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
resp = recv()
tools = [t["name"] for t in resp["result"]["tools"]]
print("tools:", tools)

# 4. call read-only tools
def call(id_, name, args):
    send({"jsonrpc": "2.0", "id": id_, "method": "tools/call",
          "params": {"name": name, "arguments": args}})
    return recv()


r = call(3, "get_token_status", {})
print("token_status:", r["result"]["content"][0]["text"][:120])

r = call(4, "whoami", {})
print("whoami:", r["result"]["content"][0]["text"][:200])

r = call(5, "list_vacancies", {})
print("vacancies:", r["result"]["content"][0]["text"][:300])

r = call(6, "list_negotiations", {"vacancy_id": "137210083"})
txt = r["result"]["content"][0]["text"]
data = json.loads(txt)
print("negotiations count:", len(data))
print("first:", json.dumps(data[0], ensure_ascii=False)[:250])

r = call(7, "get_messages", {"negotiation_id": "5592373665"})
msgs = json.loads(r["result"]["content"][0]["text"])
print("messages:", len(msgs), "| first text:", msgs[0]["text"][:80].replace("\n", " "))

p.stdin.close()
p.wait(timeout=10)
print("MCP test OK")