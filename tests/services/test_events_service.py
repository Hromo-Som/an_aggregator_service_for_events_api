from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import codes

from events_aggregator.clients.events_provider.exceptions import ProviderNotFound
from events_aggregator.clients.events_provider.schemas import (
    SProviderAvailableSeats,
)
from events_aggregator.services.cache import seats_cache
from events_aggregator.services.events import EventService
from events_aggregator.services.exceptions import (
    EventNotFound,
    EventNotPublished,
    NoAvailableSeats,
)


@pytest.fixture
def mock_provider() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_session: AsyncMock,
    mock_provider: AsyncMock,
) -> EventService:
    """EventService с мок-репозиторием и мок-провайдером."""
    svc = EventService(mock_session, mock_provider)
    svc._repo = AsyncMock()
    return svc


async def test_list_events_empty(
    service: EventService,
) -> None:
    """Пустой список — count=0, next=None, previous=None."""
    service._repo.count.return_value = 0
    service._repo.events_list.return_value = []

    result = await service.list_events(base_url="http://test/api/events")

    assert result.count == 0
    assert result.next is None
    assert result.previous is None
    assert result.results == []


async def test_list_events_with_results(
    service: EventService,
    event_orm,
) -> None:
    service._repo.count.return_value = 1
    service._repo.events_list.return_value = [event_orm]

    result = await service.list_events(base_url="http://test/api/events")

    assert result.count == 1
    assert len(result.results) == 1
    assert result.results[0].id == event_orm.id
    assert result.results[0].place.city == event_orm.place_city


async def test_list_events_pagination_offset(
    service: EventService,
) -> None:
    """offset = (page - 1) * page_size передаётся в репозиторий."""
    service._repo.count.return_value = 100
    service._repo.events_list.return_value = []

    await service.list_events(
        base_url="http://test/api/events",
        page=3,
        page_size=20,
    )

    service._repo.events_list.assert_awaited_once_with(
        date_from=None,
        limit=20,
        offset=40,
    )


async def test_list_events_passes_date_from(
    service: EventService,
) -> None:
    service._repo.count.return_value = 0
    service._repo.events_list.return_value = []
    d = date(2026, 1, 1)

    await service.list_events(
        base_url="http://test/api/events",
        date_from=d,
    )

    service._repo.count.assert_awaited_once_with(date_from=d)
    service._repo.events_list.assert_awaited_once_with(
        date_from=d,
        limit=20,
        offset=0,
    )


async def test_list_events_next_url(
    service: EventService,
) -> None:
    """next указывает на следующую страницу, если есть ещё данные."""
    service._repo.count.return_value = 150
    service._repo.events_list.return_value = []

    result = await service.list_events(
        base_url="http://test/api/events",
        page=1,
        page_size=20,
    )

    assert result.next == "http://test/api/events?page=2&page_size=20"
    assert result.previous is None


async def test_list_events_previous_url(
    service: EventService,
) -> None:
    service._repo.count.return_value = 150
    service._repo.events_list.return_value = []

    result = await service.list_events(
        base_url="http://test/api/events",
        page=3,
        page_size=20,
    )

    assert result.previous == "http://test/api/events?page=2&page_size=20"
    assert result.next == "http://test/api/events?page=4&page_size=20"


async def test_list_events_next_url_with_date_from(
    service: EventService,
) -> None:
    service._repo.count.return_value = 50
    service._repo.events_list.return_value = []

    result = await service.list_events(
        base_url="http://test/api/events",
        date_from=date(2026, 1, 1),
        page=1,
        page_size=20,
    )

    assert result.next == (
        "http://test/api/events?page=2&page_size=20&date_from=2026-01-01"
    )


async def test_list_events_last_page_no_next(
    service: EventService,
) -> None:
    """На последней странице next=None."""
    service._repo.count.return_value = 40
    service._repo.events_list.return_value = []

    result = await service.list_events(
        base_url="http://test/api/events",
        page=2,
        page_size=20,
    )

    assert result.next is None
    assert result.previous is not None


def test_build_page_url_page_below_one() -> None:
    """page < 1 → None (нет previous)."""
    assert EventService._build_page_url("http://test", None, 0, 20, 100) is None


def test_build_page_url_page_beyond_total() -> None:
    """Страница за пределами → None."""
    assert EventService._build_page_url("http://test", None, 10, 20, 100) is None


def test_build_page_url_valid() -> None:
    result = EventService._build_page_url("http://test/api/events", None, 2, 20, 100)
    assert result == "http://test/api/events?page=2&page_size=20"


def test_build_page_url_with_date() -> None:
    result = EventService._build_page_url(
        "http://test/api/events", date(2026, 1, 1), 2, 20, 100
    )
    assert result == ("http://test/api/events?page=2&page_size=20&date_from=2026-01-01")


async def test_get_event_success(
    service: EventService,
    event_orm,
) -> None:
    service._repo.get_by_id.return_value = event_orm

    result = await service.get_event(event_orm.id)

    assert result.id == event_orm.id
    assert result.place.seats_pattern == event_orm.seats_pattern
    service._repo.get_by_id.assert_awaited_once_with(event_orm.id)


async def test_get_event_not_found(
    service: EventService,
) -> None:
    service._repo.get_by_id.return_value = None

    with pytest.raises(EventNotFound):
        await service.get_event(uuid4())


async def test_get_available_seats_from_provider(
    service: EventService,
    mock_provider: AsyncMock,
    event_orm,
) -> None:
    """Кэш пуст → идём к провайдеру и кэшируем."""
    service._repo.get_by_id.return_value = event_orm
    mock_provider.get_available_seats.return_value = SProviderAvailableSeats(
        seats=["A1", "A2", "A3"],
    )

    result = await service.get_available_seats(event_orm.id)

    assert result.event_id == event_orm.id
    assert result.available_seats == ["A1", "A2", "A3"]
    mock_provider.get_available_seats.assert_awaited_once_with(event_orm.id)

    assert seats_cache.get(str(event_orm.id)) == ["A1", "A2", "A3"]


async def test_get_available_seats_from_cache(
    service: EventService,
    mock_provider: AsyncMock,
    event_orm,
) -> None:
    """Кэш непустой → провайдер не дёргается."""
    service._repo.get_by_id.return_value = event_orm
    seats_cache.set(str(event_orm.id), ["A10", "A11"])

    result = await service.get_available_seats(event_orm.id)

    assert result.available_seats == ["A10", "A11"]
    mock_provider.get_available_seats.assert_not_awaited()


async def test_get_available_seats_event_not_found(
    service: EventService,
) -> None:
    service._repo.get_by_id.return_value = None

    with pytest.raises(EventNotFound):
        await service.get_available_seats(uuid4())


async def test_get_available_seats_finished_event(
    service: EventService,
    event_orm,
) -> None:
    """Событие не published → EventNotPublished."""
    event_orm.status = "finished"
    service._repo.get_by_id.return_value = event_orm

    with pytest.raises(EventNotPublished):
        await service.get_available_seats(event_orm.id)


async def test_get_available_seats_provider_404(
    service: EventService,
    mock_provider: AsyncMock,
    event_orm,
) -> None:
    """Провайдер вернул 404 для published события → EventNotFound."""
    service._repo.get_by_id.return_value = event_orm
    mock_provider.get_available_seats.side_effect = ProviderNotFound(
        "Not found", status_code=codes.NOT_FOUND
    )

    with pytest.raises(NoAvailableSeats):
        await service.get_available_seats(event_orm.id)
