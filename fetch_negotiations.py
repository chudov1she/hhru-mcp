import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = json.load(open("tokens.json", encoding="utf-8"))["access_token"]
HEADERS = {
    "Authorization": "Bearer " + TOKEN,
    "HH-User-Agent": "api-test-agent",
}

VACANCIES = ("137210083", "137107620")

out = {}
for vac_id in VACANCIES:
    items = []
    page = 0
    while True:
        r = requests.get(
            "https://api.hh.ru/negotiations/response",
            headers=HEADERS,
            params={
                "vacancy_id": vac_id,
                "per_page": 50,
                "page": page,
                "order_by": "created_at",
            },
        )
        d = r.json()
        items.extend(d.get("items", []))
        page += 1
        if page >= d.get("pages", 1):
            break
    out[vac_id] = [
        {
            "negotiation_id": n["id"],
            "state": n.get("state", {}).get("name"),
            "created_at": n["created_at"],
            "name": "{} {}".format(
                n["resume"].get("last_name", ""),
                n["resume"].get("first_name", ""),
            ).strip(),
            "resume_title": n["resume"].get("title"),
            "city": n["resume"].get("area", {}).get("name"),
            "experience_months": (n["resume"].get("total_experience") or {}).get("months"),
        }
        for n in items
    ]

with open("negotiations.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("saved; counts:", {k: len(v) for k, v in out.items()})