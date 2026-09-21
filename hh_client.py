import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

import requests

TOKENS_FILE = os.getenv("TOKENS_FILE", "tokens.json")
HH_CLIENT_ID = os.getenv("HH_CLIENT_ID")
HH_CLIENT_SECRET = os.getenv("HH_CLIENT_SECRET")
HH_REDIRECT_URI = os.getenv("HH_REDIRECT_URI", "http://localhost:8000/callback")

UA = os.getenv("HH_USER_AGENT", "hh-mcp-connector/1.0 (claude-hhru project)")

_lock = threading.Lock()


def get_api_key() -> Optional[str]:
    return os.getenv("MCP_API_KEY")


def check_api_key(authorization: Optional[str]) -> bool:
    """
    Проверяет заголовок Authorization: Bearer <MCP_API_KEY>.
    Если MCP_API_KEY не задан в окружении — доступ запрещён всегда.
    """
    expected = get_api_key()
    if not expected or not authorization:
        return False
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return value.strip() == expected


def check_api_key_raw(key: Optional[str]) -> bool:
    """Проверяет ключ напрямую (например, из query-параметра ?api_key=...)."""
    expected = get_api_key()
    if not expected or not key:
        return False
    return key.strip() == expected


def _load_tokens() -> Dict[str, Any]:
    with open(TOKENS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_tokens(tokens: Dict[str, Any]) -> None:
    with _lock:
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    r = requests.post(
        "https://hh.ru/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": HH_CLIENT_ID,
            "client_secret": HH_CLIENT_SECRET,
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    d["expires_at"] = time.time() + d.get("expires_in", 0)
    _save_tokens(d)
    return d


def _valid_access_token(tokens: Dict[str, Any]) -> Optional[str]:
    tok = tokens.get("access_token")
    if not tok:
        return None
    expires_at = tokens.get("expires_at")
    if expires_at and time.time() > expires_at - 300:
        return None
    return tok


def get_access_token(force_refresh: bool = False) -> str:
    tokens = _load_tokens()
    if not force_refresh:
        tok = _valid_access_token(tokens)
        if tok:
            return tok
    rt = tokens.get("refresh_token")
    if not rt:
        raise RuntimeError(
            "No valid access_token and no refresh_token. Re-authorize at /auth"
        )
    d = refresh_access_token(rt)
    return d["access_token"]


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "HH-User-Agent": UA}


def _request(method: str, url: str, **kwargs) -> requests.Response:
    """
    Делает запрос к api.hh.ru. При 401/403 один раз обновляет токен и повторяет.
    """
    token = get_access_token()
    kwargs.setdefault("timeout", 30)
    r = requests.request(method, url, headers=_headers(token), **kwargs)
    if r.status_code in (401, 403):
        token = get_access_token(force_refresh=True)
        r = requests.request(method, url, headers=_headers(token), **kwargs)
    return r


def _request_with_retries(method: str, url: str, retries: int = 4, **kwargs) -> requests.Response:
    last_exc: Exception = None
    for attempt in range(retries):
        try:
            return _request(method, url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_exc = e
            time.sleep(2 ** attempt)
    raise last_exc


# ---------- API-методы ----------


def get_me() -> Dict[str, Any]:
    r = _request_with_retries("GET", "https://api.hh.ru/me")
    r.raise_for_status()
    return r.json()


def get_my_vacancies(per_page: int = 20) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    page = 0
    while True:
        r = _request_with_retries(
            "GET",
            "https://api.hh.ru/vacancies",
            params={"employer_id": os.getenv("HH_EMPLOYER_ID"), "per_page": per_page, "page": page},
        )
        r.raise_for_status()
        d = r.json()
        out.extend(d.get("items", []))
        page += 1
        if page >= d.get("pages", 1):
            break
    return out


def get_employer_vacancies(employer_id: str, per_page: int = 20) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    page = 0
    while True:
        r = _request_with_retries(
            "GET",
            "https://api.hh.ru/vacancies",
            params={"employer_id": employer_id, "per_page": per_page, "page": page},
        )
        r.raise_for_status()
        d = r.json()
        out.extend(d.get("items", []))
        page += 1
        if page >= d.get("pages", 1):
            break
    return out


def get_negotiation_collections(vacancy_id: str) -> Dict[str, Any]:
    r = _request_with_retries(
        "GET",
        "https://api.hh.ru/negotiations",
        params={"vacancy_id": vacancy_id},
    )
    r.raise_for_status()
    return r.json()


def get_negotiations(vacancy_id: str, state: Optional[str] = None, per_page: int = 50, order_by: Optional[str] = None) -> List[Dict[str, Any]]:
    url = "https://api.hh.ru/negotiations/" + (state or "response")
    items: List[Dict[str, Any]] = []
    page = 0
    params: Dict[str, Any] = {"vacancy_id": vacancy_id, "per_page": per_page}
    if order_by:
        params["order_by"] = order_by
    while True:
        r = _request_with_retries("GET", url, params={**params, "page": page})
        r.raise_for_status()
        d = r.json()
        items.extend(d.get("items", []))
        page += 1
        if page >= d.get("pages", 1):
            break
    return items


def get_resume(resume_id: str) -> Dict[str, Any]:
    r = _request_with_retries("GET", f"https://api.hh.ru/resumes/{resume_id}")
    r.raise_for_status()
    return r.json()


def get_messages(negotiation_id: str) -> List[Dict[str, Any]]:
    r = _request_with_retries("GET", f"https://api.hh.ru/negotiations/{negotiation_id}/messages")
    r.raise_for_status()
    return r.json().get("items", [])


def get_negotiation(negotiation_id: str) -> Dict[str, Any]:
    r = _request_with_retries("GET", f"https://api.hh.ru/negotiations/{negotiation_id}")
    if r.status_code == 404:
        # прямого GET отклика нет — ищем в списках по вакансиям (там полная карточка с actions)
        found = _find_negotiation(negotiation_id)
        if found:
            return found[0]
        msgs = get_messages(negotiation_id)
        return {"id": negotiation_id, "messages": msgs}
    r.raise_for_status()
    return r.json()


def get_message_templates(negotiation_id: str, action_id: str = "invite") -> Dict[str, Any]:
    r = _request_with_retries(
        "GET",
        f"https://api.hh.ru/message_templates/{action_id}",
        params={"topic_id": negotiation_id},
    )
    r.raise_for_status()
    return r.json()


# ---------- Действия работодателя (изменяют данные!) ----------


def send_negotiation_action(
    negotiation_id: str,
    action_id: str,
    message: str,
    send_sms: bool = False,
    extra_args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Отправляет сообщение кандидату от имени работодателя, переводя отклик в состояние action_id.
    Допустимые action_id (этапы): consider, phone_interview, assessment, interview, offer, hired,
    discard_by_employer, discard_no_interaction, discard_vacancy_closed, discard_to_other_vacancy.
    ВАЖНО: реальное действие в чате с кандидатом! Не вызывать без явного запроса пользователя.
    """
    args: Dict[str, Any] = {"message": message}
    if send_sms:
        args["send_sms"] = "true"
    if extra_args:
        args.update(extra_args)
    r = _request_with_retries(
        "PUT",
        f"https://api.hh.ru/negotiations/{action_id}/{negotiation_id}",
        data=args,
    )
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return {"status_code": r.status_code, "ok": True}


def get_allowed_actions(negotiation_id: str) -> List[Dict[str, Any]]:
    """
    Возвращает список допустимых действий (этапов) для отклика без их выполнения.
    Ищет отклик по всем вакансиям работодателя (автопоиск, без переменных окружения).
    """
    for n in _find_negotiation(negotiation_id):
        return [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "enabled": a.get("enabled"),
                "arguments": [ar.get("id") for ar in a.get("arguments", [])],
            }
            for a in n.get("actions", [])
        ]
    return []


def _find_negotiation(negotiation_id: str) -> List[Dict[str, Any]]:
    """
    Ищет отклик по id во всех вакансиях работодателя. Возвращает список из 0/1 элементов
    (полный item с actions). Перебор идёт по страницам, лимит ~10 вакансий на цикл.
    """
    me = get_me()
    emp_id = me.get("employer", {}).get("id")
    vacancies = get_employer_vacancies(str(emp_id))
    for v in vacancies:
        vac_id = str(v.get("id"))
        page = 0
        while page < 10:  # предохранитель: максимум 10 страниц (500 откликов) на вакансию
            r = _request_with_retries(
                "GET",
                "https://api.hh.ru/negotiations/response",
                params={"vacancy_id": vac_id, "per_page": 50, "page": page},
            )
            if r.status_code != 200:
                break
            d = r.json()
            for n in d.get("items", []):
                if str(n.get("id")) == str(negotiation_id):
                    return [n]
            page += 1
            if page >= d.get("pages", 1):
                break
    return []


def exchange_code_for_token(code: str) -> Dict[str, Any]:
    r = requests.post(
        "https://hh.ru/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": HH_CLIENT_ID,
            "client_secret": HH_CLIENT_SECRET,
            "code": code,
            "redirect_uri": HH_REDIRECT_URI,
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    d["expires_at"] = time.time() + d.get("expires_in", 0)
    _save_tokens(d)
    return d