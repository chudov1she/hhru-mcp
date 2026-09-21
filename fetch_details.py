import json
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

import os

TOKEN = json.load(open("tokens.json", encoding="utf-8"))["access_token"]
HEADERS = {
    "Authorization": "Bearer " + TOKEN,
    "HH-User-Agent": "api-test-agent",
}

VACANCIES = ("137210083", "137107620")


def get_with_retry(url, params=None):
    for attempt in range(5):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
            return r
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"retry {attempt + 1} ({e.__class__.__name__}), wait {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"failed after retries: {url}")


def fetch_all(vac_id):
    items, page = [], 0
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
    return items


def fetch_resume(rid):
    r = get_with_retry(f"https://api.hh.ru/resumes/{rid}")
    if r.status_code != 200:
        return {"_error": r.status_code}
    d = r.json()
    return {
        "title": d.get("title"),
        "skills": (d.get("skills") or "").split(", ") if isinstance(d.get("skills"), str) else (d.get("skills") or []),
        "experience": [
            {
                "company": e.get("company"),
                "position": e.get("position"),
                "start": e.get("start"),
                "end": e.get("end"),
                "description": e.get("description"),
            }
            for e in (d.get("experience") or [])
        ],
    }


def fetch_messages(neg_id):
    r = get_with_retry(
        f"https://api.hh.ru/negotiations/{neg_id}/messages",
    )
    if r.status_code != 200:
        return []
    return [
        {
            "text": m.get("text", ""),
            "created_at": m.get("created_at"),
        }
        for m in r.json().get("items", [])
    ]


def main(limit=None):
    out = {}
    for vac_id in VACANCIES:
        rows = []
        for n in fetch_all(vac_id):
            rec = {
                "negotiation_id": n["id"],
                "state": n.get("state", {}).get("name"),
                "created_at": n["created_at"],
                "name": "{} {}".format(
                    n["resume"].get("last_name", ""),
                    n["resume"].get("first_name", ""),
                ).strip(),
                "resume_title": n["resume"].get("title"),
                "resume_id": n["resume"].get("id"),
            }
            if limit is None or len(rows) < limit:
                rid = rec["resume_id"]
                rec["resume"] = fetch_resume(rid) if rid else None
                time.sleep(0.05)
                rec["messages"] = fetch_messages(rec["negotiation_id"])
                time.sleep(0.05)
            rows.append(rec)
            print("done", vac_id, rec["negotiation_id"], rec["name"])
        out[vac_id] = rows

    with open("negotiations_full.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved negotiations_full.json; counts:", {k: len(v) for k, v in out.items()})


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)