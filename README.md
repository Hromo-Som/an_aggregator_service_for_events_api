# Events Aggregator

Сервис-агрегатор событий: собирает данные о мероприятиях из внешнего Events Provider API, хранит их в PostgreSQL и отдаёт клиентам через REST API. Поддерживает регистрацию на события и отмену регистрации.

## 📋 Возможности

- **Синхронизация событий** из внешнего провайдера — фоновая (раз в сутки) и ручная
- **Инкрементальная синхронизация** через параметр `changed_at` — забираются только изменённые события
- **Чтение из локальной БД** — быстрые ответы без обращения к провайдеру на каждый запрос
- **Пагинация и фильтрация** списка событий
- **Свободные места** с кэшированием на 30 секунд
- **Регистрация и отмена** с проверкой дедлайна, доступности места и сохранением `ticket_id → event_id`
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
│   └── events_provider/    # Клиент Events Provider API
│       ├── client.py
│       ├── schemas.py
│       └── exceptions.py
├── db/                     # Работа с БД
│   ├── models.py           # ORM-модели
│   ├── base.py             # Базовая модель
│   ├── session.py          # Engine, SessionDep
│   └── repositories/       # Репозитории
├── schemas/                # Pydantic-схемы (внутренние)
├── services/               # Бизнес-логика
│   ├── events.py
│   ├── tickets.py
│   ├── sync.py
│   ├── cache.py
│   ├── converters.py
│   └── exceptions.py
├── config.py               # Настройки (pydantic-settings)
├── dependencies.py         # FastAPI-зависимости
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
  "seat": "A15"
}
```

### Синхронизация

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/sync/trigger` | Запустить синхронизацию вручную |

Query-параметр `full` (`true`/`false`) — полная синхронизация с `2000-01-01` вместо инкрементальной.

## 🔄 Синхронизация

Сервис синхронизирует события из провайдера в локальную БД:

- **Первая синхронизация** — забирает всё с `changed_at=2000-01-01`
- **Последующие** — только события, изменённые после `last_changed_at` из метаданных
- **Фоновая** — раз в сутки в `SYNC_HOUR` (по умолчанию 03:00)
- **Ручная** — через `POST /api/sync/trigger`
- **Защита от параллельных запусков** — `asyncio.Lock` в пределах процесса
- **Батчи по 200** — `upsert_many` через PostgreSQL `ON CONFLICT`

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

- `tests/unit/` — конвертеры, кэш
- `tests/services/` — `EventService`, `TicketService`, `SyncService` (с моками)
- `tests/api/` — ручки FastAPI через `ASGITransport`
- `tests/clients/` — HTTP-клиент через `respx`

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

## 🚢 CI/CD

GitHub Actions (`.github/workflows/main.yml`):

1. **tests** — установка через uv, `ruff format --check`, `ruff check`, `pytest` с Postgres-сервисом
2. **build** — multi-arch Docker-образ, пуш в `ghcr.io`
3. **deploy** — отправка запроса в LMS API с указанием образа

## ⚠️ Известные ограничения

- **Планировщик и `asyncio.Lock`** работают в пределах одного процесса. При `uvicorn --workers N > 1` синхронизация запустится N раз. Для production нужен `pg_advisory_lock` или отдельный процесс планировщика.
- **Кэш свободных мест** — in-memory, не разделяется между воркерами. Для multi-worker стоит перейти на Redis.
- **`ticket_id` привязан к месту**, а не к пользователю. При отмене регистрации и повторной регистрации другого пользователя на то же место провайдер вернёт **тот же** `ticket_id`. Это особенность контракта провайдера.

## 📄 Лицензия

Проект создан в учебных целях.