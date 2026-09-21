"""
Общая часть MCP-сервера hh-connector: описание tools и обработка вызовов.
Используется обоими транспортами: stdio (mcp_server.py) и HTTP (app.py, /mcp).
"""

import json
import time
import traceback

from mcp.types import TextContent, Tool

import hh_client

TOOLS = [
    Tool(
        name="whoami",
        description="Возвращает профиль авторизованного пользователя hh.ru (работодателя).",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="list_vacancies",
        description="Список вакансий работодателя (id, название, город, ссылка).",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="list_negotiations",
        description=(
            "Отклики на вакансию. vacancy_id можно узнать через list_vacancies. "
            "state — необязательный фильтр этапа (например 'response' — новые отклики). "
            "order_by — сортировка: 'created_at' (по дате отклика), "
            "'last_change_time_except_employer_inbox' (по дате и активности), 'relevance' (лучшие). "
            "Возвращает кандидатов: ФИО, резюме, город, опыт, этап, дату."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "vacancy_id": {"type": "string"},
                "state": {"type": "string"},
                "order_by": {"type": "string"},
            },
            "required": ["vacancy_id"],
        },
    ),
    Tool(
        name="get_negotiation",
        description="Карточка отклика по его id.",
        inputSchema={
            "type": "object",
            "properties": {"negotiation_id": {"type": "string"}},
            "required": ["negotiation_id"],
        },
    ),
    Tool(
        name="get_resume",
        description="Полное резюме кандидата по resume_id: навыки, опыт, описания мест работы.",
        inputSchema={
            "type": "object",
            "properties": {"resume_id": {"type": "string"}},
            "required": ["resume_id"],
        },
    ),
    Tool(
        name="get_messages",
        description="Переписка (чат) по отклику: сопроводительное письмо и сообщения.",
        inputSchema={
            "type": "object",
            "properties": {"negotiation_id": {"type": "string"}},
            "required": ["negotiation_id"],
        },
    ),
    Tool(
        name="list_allowed_actions",
        description="Допустимые этапы/действия по отклику (без выполнения).",
        inputSchema={
            "type": "object",
            "properties": {"negotiation_id": {"type": "string"}},
            "required": ["negotiation_id"],
        },
    ),
    Tool(
        name="send_message_to_candidate",
        description=(
            "ОТПРАВЛЯЕТ РЕАЛЬНОЕ СООБЩЕНИЕ кандидату от имени работодателя и переводит "
            "отклик на этап action (по умолчанию 'consider' — Подумать). "
            "Допустимые action: consider, phone_interview, assessment, interview, offer, hired, "
            "discard_by_employer, discard_no_interaction, discard_vacancy_closed. "
            "ВНИМАНИЕ: это реальная коммуникация с человеком! Вызывать только по явному "
            "запросу пользователя, предварительно показав ему текст сообщения."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "negotiation_id": {"type": "string"},
                "message": {"type": "string"},
                "action": {"type": "string", "default": "consider"},
                "send_sms": {"type": "boolean", "default": False},
            },
            "required": ["negotiation_id", "message"],
        },
    ),
    Tool(
        name="get_token_status",
        description="Статус токена hh.ru: авторизован ли, когда истекает.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="refresh_token",
        description="Принудительно обновить access-токен по refresh_token.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
]


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _token_status_dict():
    try:
        with open(hh_client.TOKENS_FILE, encoding="utf-8") as f:
            t = json.load(f)
    except FileNotFoundError:
        return {"authorized": False}
    expires_at = t.get("expires_at")
    return {
        "authorized": True,
        "expires_at": expires_at,
        "expires_in_sec": int(expires_at - time.time()) if expires_at else None,
        "expired": bool(expires_at and time.time() > expires_at),
    }


def _summarize_negotiation(n):
    resume = n.get("resume", {}) or {}
    return {
        "negotiation_id": n.get("id"),
        "state": (n.get("state") or {}).get("name"),
        "created_at": n.get("created_at"),
        "candidate": {
            "name": "{} {}".format(
                resume.get("last_name", ""), resume.get("first_name", "")
            ).strip(),
            "resume_id": resume.get("id"),
            "resume_title": resume.get("title"),
            "city": (resume.get("area") or {}).get("name"),
            "experience_months": (resume.get("total_experience") or {}).get("months"),
        },
    }


async def call_tool(name: str, arguments: dict | None) -> list:
    """Единый обработчик вызова tool для обоих транспортов."""
    args = dict(arguments or {})

    try:
        if name == "whoami":
            me = hh_client.get_me()
            out = {
                "id": me.get("id"),
                "name": f"{me.get('first_name', '')} {me.get('last_name', '')}".strip(),
                "employer": me.get("employer"),
            }

        elif name == "list_vacancies":
            me = hh_client.get_me()
            emp_id = me.get("employer", {}).get("id")
            items = hh_client.get_employer_vacancies(str(emp_id))
            out = [
                {
                    "id": v.get("id"),
                    "name": v.get("name"),
                    "area": (v.get("area") or {}).get("name"),
                    "alternate_url": v.get("alternate_url"),
                }
                for v in items
            ]

        elif name == "list_negotiations":
            items = hh_client.get_negotiations(
                args["vacancy_id"], args.get("state") or None, order_by=args.get("order_by") or None
            )
            out = [_summarize_negotiation(n) for n in items]

        elif name == "get_negotiation":
            out = hh_client.get_negotiation(args["negotiation_id"])

        elif name == "get_resume":
            out = hh_client.get_resume(args["resume_id"])

        elif name == "get_messages":
            out = hh_client.get_messages(args["negotiation_id"])

        elif name == "list_allowed_actions":
            out = hh_client.get_allowed_actions(args["negotiation_id"])

        elif name == "send_message_to_candidate":
            out = hh_client.send_negotiation_action(
                negotiation_id=args["negotiation_id"],
                action_id=args.get("action") or "consider",
                message=args["message"],
                send_sms=bool(args.get("send_sms", False)),
            )

        elif name == "get_token_status":
            out = _token_status_dict()

        elif name == "refresh_token":
            tokens = hh_client._load_tokens()
            d = hh_client.refresh_access_token(tokens["refresh_token"])
            out = {"ok": True, "expires_at": d.get("expires_at")}

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=_json(out))]

    except Exception as e:
        tb = traceback.format_exc()
        return [
            TextContent(
                type="text",
                text=f"ERROR: {e}\n\n{tb}",
            )
        ]