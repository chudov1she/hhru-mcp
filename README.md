# hhru-mcp

MCP-сервер и REST API для интеграции с [hh.ru](https://hh.ru) от имени **работодателя**. Позволяет AI-агентам (Claude Desktop, Claude Code, Hermes, Cursor и др.) работать с вакансиями, откликами, резюме и чатами с кандидатами.

## Возможности

**Чтение:**
- Профиль работодателя (`whoami`)
- Список вакансий
- Отклики на вакансию — с фильтром по этапу (`response`, `consider`, `interview`, ...) и сортировкой (`created_at`, `relevance`, активность соискателя)
- Полные резюме кандидатов: навыки, опыт, описания мест работы
- Переписка по отклику (чат + сопроводительное письмо)
- Допустимые действия по отклику

**Запись:**
- Отправка сообщения кандидату от имени работодателя с переводом отклика на этап (`consider` → `phone_interview` → `interview` → `offer` → `hired` или отказ)

**Токены:**
- OAuth 2.0 authorization code flow
- Автоматический refresh: access_token живёт 14 дней, при истечении или 401/403 клиент сам перевыпускает его по refresh_token
- Принудительный refresh вручную (REST `/token/refresh`, MCP `refresh_token`)

## Структура проекта

| Файл | Назначение |
|---|---|
| `mcp_server.py` | MCP-сервер (stdio) для подключения к AI-клиентам |
| `mcp_common.py` | Описание MCP-tools и логика вызовов (общая для stdio и HTTP) |
| `app.py` | REST API (FastAPI): те же возможности по HTTP |
| `hh_client.py` | Клиент hh.ru: токены, авто-refresh, вызовы API |
| `test_mcp.py` | Тест MCP-сервера (initialize → tools/list → вызовы read-only tools) |
| `fetch_negotiations.py` | Разовая выгрузка откликов в JSON |
| `fetch_details.py` | Разовая выгрузка откликов + резюме + чатов |
| `.env.example` | Шаблон переменных окружения |
| `tokens.json` | Токены (создаётся после авторизации, в git не попадает) |

## MCP-инструменты

| Tool | Описание | Параметры |
|---|---|---|
| `whoami` | Профиль работодателя | — |
| `list_vacancies` | Список вакансий | — |
| `list_negotiations` | Отклики: ФИО, резюме, город, опыт, этап, дата | `vacancy_id`\*, `state`, `order_by` |
| `get_negotiation` | Карточка отклика | `negotiation_id`\* |
| `get_resume` | Полное резюме | `resume_id`\* |
| `get_messages` | Чат по отклику | `negotiation_id`\* |
| `list_allowed_actions` | Допустимые этапы по отклику | `negotiation_id`\* |
| `send_message_to_candidate` | **Реальная отправка сообщения** кандидату + смена этапа | `negotiation_id`\*, `message`\*, `action`, `send_sms` |
| `get_token_status` | Статус токена | — |
| `refresh_token` | Принудительный refresh | — |

`\*` — обязательные параметры.

`order_by`: `created_at` (по дате отклика), `relevance` (лучшие), `last_change_time_except_employer_inbox` (активность).

`action`: `consider`, `phone_interview`, `assessment`, `interview`, `offer`, `hired`, `discard_by_employer`, `discard_no_interaction`, `discard_vacancy_closed`, `discard_to_other_vacancy`.

## Установка

```bash
git clone https://github.com/chudov1she/hhru-mcp.git
cd hhru-mcp
python -m venv .venv

# Windows:
.venv\Scripts\pip install -r requirements.txt
# Linux/macOS:
.venv/bin/pip install -r requirements.txt
```

Создайте [приложение HH](https://dev.hh.ru) (тип: работодатель), укажите redirect URI (например `http://localhost:8000/callback`), затем:

```bash
cp .env.example .env   # Windows: copy .env.example .env
# заполните HH_CLIENT_ID, HH_CLIENT_SECRET, HH_REDIRECT_URI
```

> Важно: `mcp==1.30.0` зафиксирован в requirements.txt — MCP SDK 2.x имеет несовместимый API.

## Авторизация (один раз)

```bash
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8000   # Linux: .venv/bin/python ...
```

1. Откройте `http://localhost:8000/auth` — редирект на hh.ru
2. Подтвердите доступ — hh.ru вернёт на `/callback`, токены сохранятся в `tokens.json`
3. Далее авторизация не нужна: refresh происходит автоматически

## Подключение к AI-клиентам

### Claude Desktop (Windows)

`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hh-connector": {
      "command": "C:\\path\\to\\hhru-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-X", "utf8", "C:\\path\\to\\hhru-mcp\\mcp_server.py"]
    }
  }
}
```

> `-X utf8` обязателен на Windows — иначе кириллица от hh.ru ломается.

### Claude Desktop (macOS / Linux)

```json
{
  "mcpServers": {
    "hh-connector": {
      "command": "/path/to/hhru-mcp/.venv/bin/python",
      "args": ["-X", "utf8", "/path/to/hhru-mcp/mcp_server.py"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add hh-connector -- "/path/to/hhru-mcp/.venv/bin/python" -X utf8 /path/to/hhru-mcp/mcp_server.py
```

### Другие клиенты (Hermes, Cursor, ...)

Любой MCP-клиент со stdio-транспортом: команда — python с путём к `mcp_server.py`.

## Транспорт и авторизация

Сервер поддерживает два транспорта MCP:

- **stdio** (`mcp_server.py`) — для Claude Desktop/Code и локальных клиентов. Ключ не нужен.
- **streamable HTTP** — `POST/GET /mcp` на порту 8000 (в составе `app.py`). Для веб-клиентов и Connectors.

**Авторизация (HTTP/REST):** все запросы, кроме `/`, `/auth`, `/callback`, требуют заголовок:

```
Authorization: Bearer <MCP_API_KEY>
```

Ключ задаётся в `.env` (`MCP_API_KEY`). Без ключа или с неверным — `401`.

Конфиг для HTTP-клиентов (Hermes, Connectors, веб-агенты):

```json
{
  "mcpServers": {
    "hh-connector": {
      "url": "https://ваш-домен/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    }
  }
}
```

## REST API

То же самое по HTTP (порт 8000):

| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | статус |
| GET | `/auth` → `/callback` | OAuth flow |
| GET | `/token/status` | статус токена |
| POST | `/token/refresh` | принудительный refresh |
| GET | `/me` | профиль |
| GET | `/vacancies` | мои вакансии |
| GET | `/vacancies/{id}/negotiations?state=&order_by=` | отклики |
| GET | `/negotiations/{id}` | карточка отклика |
| GET | `/negotiations/{id}/messages` | чат |
| GET | `/negotiations/{id}/actions` | допустимые действия |
| GET | `/resumes/{id}` | резюме |
| POST | `/send-message` | отправка сообщения (JSON: `negotiation_id`, `message`, `action`, `send_sms`) |

## Тесты

```bash
.venv\Scripts\python -X utf8 test_mcp.py   # проверка MCP: initialize, tools, read-only вызовы
```

## ⚠️ Отправка сообщений — это реальная коммуникация

Tool `send_message_to_candidate` и `POST /send-message` отправляют **настоящее сообщение живому человеку** от имени работодателя и меняют этап отклика. В описании tool'а стоит предупреждение для агента: показывать текст пользователю до отправки и отправлять только по явному запросу.

## Лицензия

MIT