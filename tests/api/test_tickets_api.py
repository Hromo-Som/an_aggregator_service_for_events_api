from unittest.mock import AsyncMock
from uuid import uuid4

from httpx import AsyncClient, codes

from events_aggregator.schemas.event import (
    SEventCancellationRead,
    SEventRegistrationRead,
)
from events_aggregator.services.exceptions import (
    EventNotFound,
    RegistrationDeadlinePassed,
    RegistrationNotFound,
    SeatAlreadyTaken,
)
from tests.constants import TICKET_ID


def _payload(**overrides) -> dict:
    base = {
        "event_id": str(uuid4()),
        "first_name": "Ivan",
        "last_name": "Ivanov",
        "email": "ivan@example.com",
        "seat": "A15",
    }
    base.update(overrides)
    return base


async def test_register_success(
    api_client: AsyncClient,
    mock_ticket_service: AsyncMock,
) -> None:
    mock_ticket_service.register.return_value = SEventRegistrationRead(
        ticket_id=TICKET_ID,
    )

    response = await api_client.post("/api/tickets", json=_payload())

    assert response.status_code == codes.CREATED
    assert response.json() == {"ticket_id": str(TICKET_ID)}
    mock_ticket_service.register.assert_awaited_once()


async def test_register_event_not_found(
    api_client: AsyncClient,
    mock_ticket_service: AsyncMock,
) -> None:
    mock_ticket_service.register.side_effect = EventNotFound("Event not found")

    response = await api_client.post("/api/tickets", json=_payload())

    assert response.status_code == codes.NOT_FOUND


async def test_register_seat_already_taken(
    api_client: AsyncClient,
    mock_ticket_service: AsyncMock,
) -> None:
    mock_ticket_service.register.side_effect = SeatAlreadyTaken(
        "Seat A15 is not available"
    )

    response = await api_client.post("/api/tickets", json=_payload())

    assert response.status_code == codes.BAD_REQUEST
    assert "A15" in response.json()["detail"]


async def test_register_deadline_passed(
    api_client: AsyncClient,
    mock_ticket_service: AsyncMock,
) -> None:
    mock_ticket_service.register.side_effect = RegistrationDeadlinePassed(
        "Deadline passed"
    )

    response = await api_client.post("/api/tickets", json=_payload())

    assert response.status_code == codes.BAD_REQUEST


async def test_register_invalid_email_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/tickets", json=_payload(email="not-an-email")
    )
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


async def test_register_missing_field_returns_422(
    api_client: AsyncClient,
) -> None:
    payload = _payload()
    del payload["seat"]

    response = await api_client.post("/api/tickets", json=payload)

    assert response.status_code == codes.UNPROCESSABLE_ENTITY


async def test_register_invalid_event_id_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/tickets", json=_payload(event_id="not-a-uuid")
    )
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


async def test_register_empty_first_name_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post("/api/tickets", json=_payload(first_name=""))
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


async def test_unregister_success(
    api_client: AsyncClient,
    mock_ticket_service: AsyncMock,
) -> None:
    mock_ticket_service.unregister.return_value = SEventCancellationRead(
        success=True,
    )

    response = await api_client.delete(f"/api/tickets/{TICKET_ID}")

    assert response.status_code == codes.OK
    assert response.json() == {"success": True}
    mock_ticket_service.unregister.assert_awaited_once_with(TICKET_ID)


async def test_unregister_not_found(
    api_client: AsyncClient,
    mock_ticket_service: AsyncMock,
) -> None:
    mock_ticket_service.unregister.side_effect = RegistrationNotFound(
        "Ticket not found"
    )

    response = await api_client.delete(f"/api/tickets/{TICKET_ID}")

    assert response.status_code == codes.NOT_FOUND


async def test_unregister_invalid_uuid_returns_422(
    api_client: AsyncClient,
) -> None:
    response = await api_client.delete("/api/tickets/not-a-uuid")
    assert response.status_code == codes.UNPROCESSABLE_ENTITY
