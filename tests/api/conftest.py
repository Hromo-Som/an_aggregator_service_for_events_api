from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from events_aggregator.api.endpoints import events, health, sync, tickets
from events_aggregator.api.exception_handlers import register_exception_handlers
from events_aggregator.dependencies import (
    get_event_service,
    get_sync_service,
    get_ticket_service,
)


@pytest.fixture
def mock_event_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_ticket_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_sync_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def api_app(
    mock_event_service: AsyncMock,
    mock_ticket_service: AsyncMock,
    mock_sync_service: AsyncMock,
) -> FastAPI:
    """Тестовое FastAPI-приложение с подменёнными сервисами."""
    app = FastAPI()

    app.include_router(health.router, prefix="/api")
    app.include_router(events.router, prefix="/api")
    app.include_router(tickets.router, prefix="/api")
    app.include_router(sync.router, prefix="/api")

    register_exception_handlers(app)

    app.dependency_overrides[get_event_service] = lambda: mock_event_service
    app.dependency_overrides[get_ticket_service] = lambda: mock_ticket_service
    app.dependency_overrides[get_sync_service] = lambda: mock_sync_service

    return app


@pytest.fixture
async def api_client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент, работающий с приложением в памяти."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client
