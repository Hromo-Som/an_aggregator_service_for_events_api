from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from events_aggregator.db.models import EventORM
from events_aggregator.services.cache import seats_cache
from tests.constants import EVENT_ID, PLACE_ID, TICKET_ID


@pytest.fixture
def event_orm() -> EventORM:
    """Готовое событие (ORM) для тестов."""
    now = datetime.now(UTC)
    return EventORM(
        id=EVENT_ID,
        name="Python Conf",
        status="published",
        place_id=PLACE_ID,
        place_name="Технопарк",
        place_city="Москва",
        place_address="ул. Ленина, 1",
        seats_pattern="A1-100,B1-50",
        event_time=now + timedelta(days=10),
        registration_deadline=now + timedelta(days=9),
        number_of_visitors=5,
        changed_at=now,
        synced_at=now,
    )


@pytest.fixture
def event_id() -> UUID:
    return EVENT_ID


@pytest.fixture
def ticket_id() -> UUID:
    return TICKET_ID


@pytest.fixture(autouse=True)
def clear_seats_cache() -> Iterator[None]:
    """Кэш — глобальный singleton. Чистим его до и после каждого теста."""
    seats_cache.clear()
    yield
    seats_cache.clear()


@pytest.fixture
def mock_session_factory() -> Iterator[AsyncMock]:
    """Подменяет async_session_factory на мок."""
    with patch("events_aggregator.services.sync.async_session") as mock:
        session = AsyncMock()
        mock.return_value.__aenter__.return_value = session
        yield session
