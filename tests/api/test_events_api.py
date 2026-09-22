from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

from httpx import AsyncClient, codes

from events_aggregator.schemas.event import (
    SEventDetailRead,
    SEventPageRead,
    SEventPlaceDetailRead,
    SEventSeatsRead,
)
from events_aggregator.services.exceptions import EventNotFound, NoAvailableSeats
from tests.constants import EVENT_ID


async def test_list_events_empty(
    api_client: AsyncClient,
    mock_event_service: AsyncMock,
) -> None:
    mock_event_service.list_events.return_value = SEventPageRead(
        count=0,
        next=None,
        previous=None,
        results=[],
    )

    response = await api_client.get("/api/events")

    assert response.status_code == codes.OK
    body = response.json()
    assert body == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


async def test_list_events_passes_query_params(
    api_client: AsyncClient,
    mock_event_service: AsyncMock,
) -> None:
    """Query-параметры доходят до сервиса."""
    mock_event_service.list_events.return_value = SEventPageRead(
        count=0, next=None, previous=None, results=[]
    )

    await api_client.get("/api/events?page=2&page_size=50&date_from=2026-01-01")

    call_kwargs = mock_event_service.list_events.await_args.kwargs
    assert call_kwargs["page"] == 2
    assert call_kwargs["page_size"] == 50
    assert call_kwargs["date_from"] == date(2026, 1, 1)


async def test_list_events_page_zero_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/api/events?page=0")
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


async def test_list_events_page_size_too_large_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/api/events?page_size=1000")
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


async def test_list_events_invalid_date_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/api/events?date_from=not-a-date")
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


async def test_get_event_success(
    api_client: AsyncClient,
    mock_event_service: AsyncMock,
) -> None:
    mock_event_service.get_event.return_value = SEventDetailRead(
        id=EVENT_ID,
        name="Python Conf",
        place=SEventPlaceDetailRead(
            id=uuid4(),
            name="Технопарк",
            city="Москва",
            address="ул. Ленина, 1",
            seats_pattern="A1-100",
        ),
        event_time="2026-09-01T10:00:00+00:00",
        registration_deadline="2026-08-31T10:00:00+00:00",
        status="published",
        number_of_visitors=5,
    )

    response = await api_client.get(f"/api/events/{EVENT_ID}")

    assert response.status_code == codes.OK
    body = response.json()
    assert body["id"] == str(EVENT_ID)
    assert body["name"] == "Python Conf"
    assert body["place"]["seats_pattern"] == "A1-100"


async def test_get_event_not_found(
    api_client: AsyncClient,
    mock_event_service: AsyncMock,
) -> None:
    mock_event_service.get_event.side_effect = EventNotFound("Event not found")

    response = await api_client.get(f"/api/events/{EVENT_ID}")

    assert response.status_code == codes.NOT_FOUND
    assert "Event not found" in response.json()["detail"]


async def test_get_event_invalid_uuid_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/api/events/not-a-uuid")
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


async def test_get_seats_success(
    api_client: AsyncClient,
    mock_event_service: AsyncMock,
) -> None:
    mock_event_service.get_available_seats.return_value = SEventSeatsRead(
        event_id=EVENT_ID,
        available_seats=["A1", "A2", "A3"],
    )

    response = await api_client.get(f"/api/events/{EVENT_ID}/seats")

    assert response.status_code == codes.OK
    body = response.json()
    assert body["event_id"] == str(EVENT_ID)
    assert body["available_seats"] == ["A1", "A2", "A3"]


async def test_get_seats_event_not_found(
    api_client: AsyncClient,
    mock_event_service: AsyncMock,
) -> None:
    mock_event_service.get_available_seats.side_effect = EventNotFound(
        "Event not found"
    )

    response = await api_client.get(f"/api/events/{EVENT_ID}/seats")

    assert response.status_code == codes.NOT_FOUND


async def test_get_seats_no_available_seats(
    api_client: AsyncClient,
    mock_event_service: AsyncMock,
) -> None:
    """Завершённое событие."""
    mock_event_service.get_available_seats.side_effect = NoAvailableSeats(
        "Event is not available"
    )

    response = await api_client.get(f"/api/events/{EVENT_ID}/seats")

    assert response.status_code == codes.BAD_REQUEST
    assert "not available" in response.json()["detail"]
