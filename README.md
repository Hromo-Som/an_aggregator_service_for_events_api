# Events Aggregator

Сервис-агрегатор событий: собирает данные о мероприятиях из внешнего Events Provider API, хранит их в PostgreSQL и отдаёт клиентам через REST API. Поддерживает регистрацию на события с гарантированной доставкой уведомлений через Transactional Outbox и защитой от дублей через идемпотентность.

## 📋 Возможности

- **Синхронизация событий** из внешнего провайдера — фоновая (раз в сутки) и ручная
- **Инкрементальная синхронизация** через параметр `changed_at` — забираются только изменённые события
- **Чтение из локальной БД** — быстрые ответы без обращения к провайдеру на каждый запрос
- **Пагинация и фильтрация** списка событий
- **Свободные места** с кэшированием на 30 секунд
- **Регистрация и отмена** с проверкой дедлайна, доступности места и сохранением `ticket_id → event_id`
- **Идемпотентность регистрации** — повторный запрос с тем же ключом не создаёт дубль билета
- **Transactional Outbox** — гарантированная доставка уведомлений даже при падении или недоступности внешнего сервиса
- **Интеграция с Capashino** — уведомления пользователям через Notification-сервис
- **Отслеживание ошибок** через GlitchTip (Sentry SDK) — все необработанные исключения в production
- **Глобальная обработка ошибок** — доменные исключения превращаются в понятные HTTP-статусы
- **Docker-образ** и **CI** с тестами, линтером и публикацией в GHCR

## 🛠️ Технологии

| Слой | Стек |
|---|---|
| Язык | Python 3.14 |
| Веб-фреймворк | FastAPI + Uvicorn |
| БД | PostgreSQL + SQLAlchemy 2.0 (async) + asyncpg |
| Миграции | Alembic |
| HTTP-клиент | httpx |
| Валидация | Pydantic v2 + pydantic-settings |
| Планировщик | APScheduler |
| Кэш | cachetools (in-memory TTLCache) |
| Мониторинг | sentry-sdk → GlitchTip |
| Менеджер зависимостей | uv |
| Линтер и форматтер | ruff |
| Тесты | pytest, pytest-asyncio, respx |

## 📁 Структура

```
src/events_aggregator/
├── api/                    # FastAPI-слой
│   ├── endpoints/          # Ручки: events, tickets, sync, health
│   ├── router.py           # Корневой роутер с /api
│   └── exception_handlers.py
├── clients/                # Внешние HTTP-клиенты
│   ├── base.py             # Базовый async-клиент
│   ├── exceptions.py
│   ├── events_provider/    # Клиент Events Provider API
│   │   ├── client.py
│   │   ├── schemas.py
│   │   └── exceptions.py
│   └── capashino/          # Клиент Notification-сервиса
│       ├── client.py
│       ├── schemas.py
│       └── exceptions.py
├── db/                     # Работа с БД
│   ├── models.py           # ORM-модели
│   ├── base.py             # Базовая модель
│   ├── session.py          # Engine, SessionDep
│   └── repositories/       # Репозитории
│       ├── events.py
│       ├── tickets.py
│       ├── outbox.py           # Transactional Outbox
│       ├── idempotency.py      # Ключи идемпотентности
│       └── sync.py
├── schemas/                # Pydantic-схемы (внутренние)
├── services/               # Бизнес-логика
│   ├── events.py
│   ├── tickets.py
│   ├── sync.py
│   ├── outbox_publisher.py # Фоновый воркер отправки
│   ├── cache.py
│   ├── converters.py
│   └── exceptions.py
├── enums.py                # EventStatus, SyncStatus, Outbox
├── config.py               # Настройки (pydantic-settings)
├── dependencies.py         # FastAPI-зависимости
├── monitoring.py               # Инициализация GlitchTip
├── scheduler.py            # APScheduler
└── main.py                 # Точка входа
```

## 🚀 Быстрый старт

### Требования

- Python 3.14+
- PostgreSQL 16+
- [uv](https://docs.astral.sh/uv/)
- Docker (опционально)

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/hromo-som/an_aggregator_service_for_events_api.git
cd an_aggregator_service_for_events_api

# Установить зависимости
uv sync

# Создать .env из шаблона
cp .env.example .env
```

Отредактируйте `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/events
EVENTS_PROVIDER_BASE_URL=https://events-provider.dev-2.python-labs.ru/api
EVENTS_PROVIDER_API_KEY=your_real_key
CAPASHINO_BASE_URL=http://student-system-capashino-web.student-system-capashino.svc:8000
CAPASHINO_API_KEY=your_capashino_token
```

### Подготовка БД

```bash
# Создать БД
psql -h localhost -U postgres -c "CREATE DATABASE events;"

# Применить миграции
uv run alembic upgrade head
```

### Запуск

```bash
uv run uvicorn events_aggregator.main:app --reload
```

Сервис доступен на `http://127.0.0.1:8000`. При старте запускается:

- Первичная синхронизация событий в фоне
- Планировщик ежедневной синхронизации
- Фоновый **OutboxPublisher** (отправка накопленных событий)

## 🐳 Docker

### Сборка и запуск

```bash
docker build -t events-aggregator .

docker run -p 8000:8000 \
  --env-file .env \
  -e DATABASE_URL="postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/events" \
  events-aggregator
```

## 📖 API

Все ручки доступны под префиксом `/api`. Интерактивная документация — `/docs` (Swagger) и `/redoc`.

### Health

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/health` | Проверка, что приложение живо |

### События

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/events` | Список событий с пагинацией и фильтром по дате |
| GET | `/api/events/{event_id}` | Детали события |
| GET | `/api/events/{event_id}/seats` | Свободные места (кэш 30 сек) |

**Query-параметры `GET /api/events`:**

- `date_from` (опционально) — события после указанной даты (`YYYY-MM-DD`)
- `page` (опционально, по умолчанию 1) — номер страницы
- `page_size` (опционально, по умолчанию 20, максимум 100) — размер страницы

### Регистрация

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/tickets` | Зарегистрировать участника |
| DELETE | `/api/tickets/{ticket_id}` | Отменить регистрацию |

**Тело `POST /api/tickets`:**

```json
{
  "event_id": "e5edfd1b-e26b-457b-a82b-652cac651301",
  "first_name": "Иван",
  "last_name": "Иванов",
  "email": "ivan@example.com",
  "seat": "A15",
  "idempotency_key": "optional-unique-key"
}
```

### Синхронизация

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/sync/trigger` | Запустить синхронизацию вручную |

Query-параметр `full` (`true`/`false`) — полная синхронизация с `2000-01-01` вместо инкрементальной.

## 🔒 Идемпотентность регистрации

Для защиты от двойных кликов и retry клиент может передать `idempotency_key` в теле `POST /api/tickets`.

**Поведение:**

| Сценарий | Ответ |
|---|---|
| Ключ не передан | Обычная регистрация (как в части 1) |
| Ключ новый | Регистрация, `201 Created`, ключ → результат сохраняется |
| Ключ уже был, те же данные | `201 Created`, тот же `ticket_id`, провайдер не вызывается |
| Ключ уже был, другие данные | `409 Conflict`, новый билет не создаётся |
| Ошибка провайдера | Ключ не сохраняется, можно повторить |

**Реализация:**

- Таблица `idempotency_keys`: `key` (PK), `request_hash` (SHA-256 от значимых полей), `response_body`, `status_code`.
- `pg_advisory_xact_lock` сериализует параллельные запросы с одним ключом.
- Запись в `idempotency_keys` идёт **в той же транзакции**, что тикет и outbox-событие.

## 📤 Transactional Outbox

При регистрации на событие кроме тикета в БД атомарно записывается событие `ticket.purchased` в таблицу `outbox_events`. Фоновый воркер `OutboxPublisher` периодически читает неотправленные записи и вызывает Capashino.

**Гарантии:**

- **Атомарность** — тикет и outbox в одной транзакции. Если commit падает — откатывается всё.
- **At-least-once** — при ошибке отправки запись остаётся `pending` и повторяется.
- **Exactly-once на стороне Capashino** — `idempotency_key = outbox_event.id`. При повторной отправке Capashino вернёт ранее созданное уведомление.
- **Ограничение попыток** — после `OUTBOX_MAX_ATTEMPTS` запись помечается `failed`, не крутится вечно.

**Схема таблицы `outbox_events`:**

| Поле | Тип | Описание |
|---|---|---|
| `id` | UUID | PK |
| `event_type` | String(100) | `ticket.purchased` |
| `payload` | JSON | данные для уведомления |
| `status` | String(20) | `pending` / `sent` / `failed` |
| `attempts` | Integer | счётчик попыток |
| `last_error` | Text | последняя ошибка |
| `created_at` | Timestamptz | время создания |
| `sent_at` | Timestamptz | время успешной отправки |

## 🔔 Интеграция с Capashino

После успешной регистрации воркер отправляет уведомление через Capashino API:

```
POST {CAPASHINO_BASE_URL}/api/notifications
X-API-Key: {CAPASHINO_API_KEY}

{
  "message": "Вы успешно зарегистрированы на мероприятие - Python Conf. Место: A15.",
  "reference_id": "<ticket_id>",
  "idempotency_key": "<outbox_event_id>"
}
```

**Обработка ошибок в воркере:**

| Ответ Capashino | Действие |
|---|---|
| 201 Created | `mark_sent` |
| 409 Conflict (idempotency) | `mark_sent` — уведомление уже создано |
| 400/401/403/422 | `mark_failed_attempt(max_attempts=1)` — сразу `failed` |
| 5xx, таймауты | `mark_failed_attempt(max_attempts=N)` — retry |

## 📊 Отслеживание ошибок (GlitchTip)

Сервис подключён к **GlitchTip** через `sentry-sdk` (Sentry-совместимый API).

**Что отслеживается:**

- Все **необработанные** исключения в FastAPI-ручках → автоматически.
- Бизнес-ошибки (`DomainError`, 4xx) → **не отправляются**, они обработаны и превращены в JSON.

**Конфигурация:**

```dotenv
SENTRY_DSN=https://<public_key>@<host>/<project_id>
ENVIRONMENT=production
RELEASE=<git-sha>
SENTRY_TRACES_SAMPLE_RATE=0.0
```

Если `SENTRY_DSN` пуст — отправка отключена, приложение работает как обычно (удобно для локальной разработки и тестов).

## 🔄 Синхронизация

Сервис синхронизирует события из провайдера в локальную БД:

- **Первая синхронизация** — забирает всё с `changed_at=2000-01-01`
- **Последующие** — только события, изменённые после `last_changed_at` из метаданных
- **Фоновая** — раз в сутки в `SYNC_HOUR` (по умолчанию 03:00)
- **Ручная** — через `POST /api/sync/trigger`
- **Защита от параллельных запусков** — `asyncio.Lock` в пределах процесса
- **Батчи по 200** — `upsert_many` через PostgreSQL `ON CONFLICT`
- **Пагинация** — обход через `next` в `EventsPaginator` с защитой от бесконечных циклов и SSRF

Метаданные синхронизации хранятся в таблице `sync_metadata`: `last_sync_time`, `last_changed_at`, `sync_status`, `last_error`.

## ⚙️ Конфигурация

Все настройки — через переменные окружения или `.env`:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/events` | URL подключения к БД |
| `EVENTS_PROVIDER_BASE_URL` | — | Базовый URL провайдера |
| `EVENTS_PROVIDER_API_KEY` | `""` | API-ключ провайдера |
| `EVENTS_PROVIDER_TIMEOUT` | `10.0` | Таймаут запросов к провайдеру (сек) |
| `EVENTS_PROVIDER_MAX_RETRIES` | `3` | Максимум ретраев |
| `CAPASHINO_BASE_URL` | — | Базовый URL Capashino |
| `CAPASHINO_API_KEY` | `""` | API-токен Capashino |
| `CAPASHINO_TIMEOUT` | `10.0` | Таймаут Capashino |
| `OUTBOX_POLL_INTERVAL` | `5.0` | Интервал опроса outbox (сек) |
| `OUTBOX_BATCH_SIZE` | `100` | Размер батча |
| `OUTBOX_MAX_ATTEMPTS` | `5` | Лимит попыток до `failed` |
| `GLITCHTIP_DSN` | `""` | DSN для GlitchTip (пустой = отключено) |
| `ENVIRONMENT` | `development` | Окружение для событий в GlitchTip |
| `RELEASE` | `dev` | Версия (обычно git SHA) |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Доля трейсов (0 = отключено) |
| `DB_ECHO` | `false` | Логировать SQL-запросы |
| `DB_POOL_SIZE` | `20` | Размер пула соединений |
| `DB_MAX_OVERFLOW` | `10` | Дополнительные соединения |
| `SYNC_ENABLED` | `true` | Включить планировщик |
| `SYNC_HOUR` | `3` | Час запуска фоновой синхронизации (0–23) |
| `SYNC_BATCH_SIZE` | `200` | Размер батча upsert |
| `DEBUG` | `false` | Debug-режим |
| `PORT` | `8000` | Порт приложения |

## 🧪 Тесты

```bash
# Все тесты
uv run pytest

# С покрытием
uv run pytest --cov=events_aggregator --cov-report=term-missing

# Только юниты
uv run pytest tests/unit/ -v

# Только API
uv run pytest tests/api/ -v

# Только клиенты (respx)
uv run pytest tests/clients/ -v
```

Покрыто:

- `tests/unit/` — конвертеры, кэш, enums
- `tests/services/` — `EventService`, `TicketService` (включая идемпотентность), `SyncService`, `OutboxPublisher`
- `tests/api/` — ручки FastAPI через `ASGITransport` с подменёнными сервисами
- `tests/clients/` — HTTP-клиенты (`EventsProviderClient`, `CapashinoClient`, `EventsPaginator`) через `respx`

## 🧹 Линтер

```bash
# Форматирование
uv run ruff format src/ tests/

# Проверка
uv run ruff check src/ tests/

# Автофикс
uv run ruff check --fix src/ tests/
```

## 🗄️ Миграции

```bash
# Создать миграцию (автогенерация)
uv run alembic revision --autogenerate -m "describe change"

# Применить
uv run alembic upgrade head

# Откатить на одну
uv run alembic downgrade -1

# Текущая ревизия
uv run alembic current

# Проверить, нет ли неприменённых изменений
uv run alembic check
```

**Таблицы в БД:**

| Таблица | Назначение |
|---|---|
| `events` | Синхронизированные события |
| `tickets` | Регистрации (тикеты) |
| `sync_metadata` | Метаданные синхронизации (одна строка) |
| `outbox_events` | События для гарантированной доставки |
| `idempotency_keys` | Ключи идемпотентности → результат |

## 🚢 CI/CD

GitHub Actions (`.github/workflows/main.yml`):

1. **tests** — установка через uv, `ruff format --check`, `ruff check`, `pytest` с Postgres-сервисом
2. **build** — multi-arch Docker-образ, пуш в `ghcr.io`
3. **deploy** — отправка запроса в LMS API с указанием образа

## ⚠️ Известные ограничения

- **Планировщик, `asyncio.Lock` и `OutboxPublisher`** работают в пределах одного процесса. При `uvicorn --workers N > 1` синхронизация запустится N раз, но `FOR UPDATE SKIP LOCKED` в outbox не даст дублей при отправке. Для планировщика нужен `pg_advisory_lock` или отдельный процесс.
- **Кэш свободных мест** — in-memory, не разделяется между воркерами. Для multi-worker стоит перейти на Redis.
- **`ticket_id` привязан к месту**, а не к пользователю. При отмене регистрации и повторной регистрации другого пользователя на то же место провайдер вернёт **тот же** `ticket_id`. Это особенность контракта провайдера.
- **`idempotency_keys` не чистятся**. Для долгой работы нужен фоновый cleanup старых записей (TTL 7–30 дней).

## 📄 Лицензия

Проект создан в учебных целях.