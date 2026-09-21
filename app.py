import os

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import hh_client

load_dotenv()

app = FastAPI(title="HH Connector API", version="1.0.0")

CLIENT_ID = os.getenv("HH_CLIENT_ID")
CLIENT_SECRET = os.getenv("HH_CLIENT_SECRET")
REDIRECT_URI = os.getenv("HH_REDIRECT_URI", "http://localhost:8000/callback")


class SendMessageRequest(BaseModel):
    negotiation_id: str
    message: str
    action: str = "consider"
    send_sms: bool = False


@app.get("/")
def index():
    return {"status": "ok", "message": "HH Connector API + MCP"}


@app.get("/auth")
def auth():
    url = "https://hh.ru/oauth/authorize"
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
    }
    response = requests.Request("GET", url, params=params).prepare()
    return RedirectResponse(response.url)


@app.get("/callback")
def callback(code: str):
    try:
        token = hh_client.exchange_code_for_token(code)
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return token


@app.get("/token/status")
def token_status():
    import json
    import time

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


@app.post("/token/refresh")
def token_refresh():
    try:
        tokens = hh_client._load_tokens()
        if not tokens.get("refresh_token"):
            raise HTTPException(status_code=400, detail="No refresh_token. Re-authorize at /auth")
        d = hh_client.refresh_access_token(tokens["refresh_token"])
        return {"ok": True, "expires_at": d.get("expires_at")}
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/me")
def me():
    try:
        return hh_client.get_me()
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.get("/vacancies")
def vacancies(employer_id: str = Query(default=None)):
    try:
        if employer_id is None:
            me_data = hh_client.get_me()
            employer_id = me_data.get("employer", {}).get("id")
        items = hh_client.get_employer_vacancies(str(employer_id))
        return {
            "count": len(items),
            "items": [
                {
                    "id": v.get("id"),
                    "name": v.get("name"),
                    "area": v.get("area", {}).get("name"),
                    "status": v.get("type", {}).get("name") if v.get("type") else None,
                    "alternate_url": v.get("alternate_url"),
                }
                for v in items
            ],
        }
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.get("/vacancies/{vacancy_id}/negotiations")
def negotiations(vacancy_id: str, state: str = Query(default=None), order_by: str = Query(default=None)):
    try:
        items = hh_client.get_negotiations(vacancy_id, state, order_by=order_by)
        return {
            "count": len(items),
            "items": [
                {
                    "negotiation_id": n.get("id"),
                    "state": n.get("state", {}).get("name"),
                    "employer_state": n.get("employer_state", {}).get("name") if n.get("employer_state") else None,
                    "created_at": n.get("created_at"),
                    "updated_at": n.get("updated_at"),
                    "candidate": {
                        "name": "{} {}".format(
                            n.get("resume", {}).get("last_name", ""),
                            n.get("resume", {}).get("first_name", ""),
                        ).strip(),
                        "resume_id": n.get("resume", {}).get("id"),
                        "resume_title": n.get("resume", {}).get("title"),
                        "city": n.get("resume", {}).get("area", {}).get("name"),
                        "experience_months": (n.get("resume", {}).get("total_experience") or {}).get("months"),
                    },
                }
                for n in items
            ],
        }
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.get("/negotiations/{negotiation_id}")
def negotiation(negotiation_id: str):
    try:
        return hh_client.get_negotiation(negotiation_id)
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.get("/negotiations/{negotiation_id}/messages")
def messages(negotiation_id: str):
    try:
        return hh_client.get_messages(negotiation_id)
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.get("/negotiations/{negotiation_id}/actions")
def allowed_actions(negotiation_id: str):
    try:
        return {"actions": hh_client.get_allowed_actions(negotiation_id)}
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.get("/resumes/{resume_id}")
def resume(resume_id: str):
    try:
        return hh_client.get_resume(resume_id)
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@app.post("/send-message")
def send_message(req: SendMessageRequest):
    """
    ВАЖНО: отправляет реальное сообщение кандидату от имени работодателя!
    Меняет этап отклика (по умолчанию 'consider' — Подумать).
    """
    try:
        return hh_client.send_negotiation_action(
            negotiation_id=req.negotiation_id,
            action_id=req.action,
            message=req.message,
            send_sms=req.send_sms,
        )
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)