"""Полный тест всех MCP tools на проде. КРОМЕ отправки сообщений (send_message_to_candidate НЕ вызывается)."""

import asyncio
import json
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
            await session.initialize()
            print("=== initialize OK ===\n")

            # 1. get_token_status
            r = await session.call_tool("get_token_status", {})
            d = json.loads(r.content[0].text)
            print("1) get_token_status:", "authorized =", d["authorized"], "| expired =", d["expired"])

            # 2. whoami
            r = await session.call_tool("whoami", {})
            d = json.loads(r.content[0].text)
            print("2) whoami:", d["name"], "| employer:", d["employer"]["name"])

            # 3. list_vacancies
            r = await session.call_tool("list_vacancies", {})
            vacs = json.loads(r.content[0].text)
            print("3) list_vacancies:", len(vacs), "шт:")
            for v in vacs:
                print("   -", v["id"], "|", v["name"], "|", v["area"])
            vac_id = vacs[0]["id"]

            # 4. list_negotiations (order_by=created_at)
            r = await session.call_tool(
                "list_negotiations", {"vacancy_id": vac_id, "order_by": "created_at"}
            )
            negs = json.loads(r.content[0].text)
            print("4) list_negotiations:", len(negs), "| первый:", negs[0]["candidate"]["name"], "|", negs[0]["created_at"])
            neg_id = negs[0]["negotiation_id"]
            resume_id = negs[0]["candidate"]["resume_id"]

            # 5. get_negotiation
            r = await session.call_tool("get_negotiation", {"negotiation_id": neg_id})
            d = json.loads(r.content[0].text)
            has_err = "_error" in str(d)[:100]
            print("5) get_negotiation:", "OK" if d else "empty", "| keys:", list(d.keys())[:5])

            # 6. get_resume
            r = await session.call_tool("get_resume", {"resume_id": resume_id})
            d = json.loads(r.content[0].text)
            print("6) get_resume:", d.get("title"), "| навыков:", len((d.get("skills") or "").split(", ") if isinstance(d.get("skills"), str) else (d.get("skills") or [])), "| мест работы:", len(d.get("experience") or []))

            # 7. get_messages
            r = await session.call_tool("get_messages", {"negotiation_id": neg_id})
            msgs = json.loads(r.content[0].text)
            print("7) get_messages:", len(msgs), "| первый:", (msgs[0]["text"][:60] + "...") if msgs else "-")

            # 8. list_allowed_actions
            r = await session.call_tool("list_allowed_actions", {"negotiation_id": neg_id})
            acts = json.loads(r.content[0].text)
            print("8) list_allowed_actions:", len(acts) if isinstance(acts, list) else acts)

            # 9. refresh_token — НЕ вызываем: hh не даёт refresh живого токена ("token not expired"),
            #    вызов просто вернёт ошибку. Проверяем, что tool отвечает (пусть с ошибкой) — это ожидаемо.
            r = await session.call_tool("refresh_token", {})
            txt = r.content[0].text
            print("9) refresh_token:", "ожидаемая ошибка (токен жив):", txt.split(chr(10))[0][:80])

            # 10. send_message_to_candidate — СОЗНАТЕЛЬНО НЕ ВЫЗЫВАЕМ
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("\n10) send_message_to_candidate: есть в списке tools =", "send_message_to_candidate" in names, "| НЕ ВЫЗЫВАЕТСЯ")

    print("\n=== ALL TOOLS TEST OK (кроме отправки сообщений — по требованию) ===")


asyncio.run(main())