from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import codes

from events_aggregator.clients.events_provider.exceptions import (
    ProviderBadRequest,
    ProviderNotFound,
)
from events_aggregator.clients.events_provider.schemas import (
    SProviderAvailableSeats,
    SProviderCancellationResponse,
    SProviderRegistration,
)
from events_aggregator.db.models import TicketORM
from events_aggregator.schemas.event import SEventRegistrationCreate
from events_aggregator.services.exceptions import (
    EventNotFound,
    NoAvailableSeats,
    RegistrationDeadlinePassed,
    RegistrationNotFound,
    SeatAlreadyTaken,
)
from events_aggregator.services.tickets import TicketService


@pytest.fixture
def mock_provider() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_event_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_ticket_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_provider: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_ticket_repo: AsyncMock,
) -> TicketService:
    return TicketService(
        provider=mock_provider,
        event_repo=mock_event_repo,
        ticket_repo=mock_ticket_repo,
    )


@pytest.fixture
def register_payload() -> SEventRegistrationCreate:
    return SEventRegistrationCreate(
        event_id=uuid4(),
        first_name="Ivan",
        last_name="Ivanov",
        email="ivan@example.com",
        seat="A15",
    )


async def test_register_success(
    service: TicketService,
    mock_provider: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_ticket_repo: AsyncMock,
    register_payload: SEventRegistrationCreate,
    event_orm,
) -> None:
    event_orm.id = register_payload.event_id
    mock_event_repo.get_by_id.return_value = event_orm
    mock_provider.get_available_seats.return_value = SProviderAvailableSeats(
        seats=["A15", "A16"]
    )

    ticket_id = uuid4()
    mock_provider.register.return_value = SProviderRegistration(ticket_id=ticket_id)

    result = await service.register(register_payload)

    assert result.ticket_id == ticket_id
    mock_ticket_repo.create.assert_awaited_once()
    call_kwargs = mock_ticket_repo.create.await_args.kwargs
    assert call_kwargs["ticket_id"] == ticket_id
    assert call_kwargs["event_id"] == register_payload.event_id
    assert call_kwargs["seat"] == "A15"


async def test_register_event_not_found(
    service: TicketService,
    mock_event_repo: AsyncMock,
    register_payload: SEventRegistrationCreate,
) -> None:
    mock_event_repo.get_by_id.return_value = None

    with pytest.raises(EventNotFound):
        await service.register(register_payload)


async def test_register_deadline_passed(
    service: TicketService,
    mock_event_repo: AsyncMock,
    register_payload: SEventRegistrationCreate,
    event_orm,
) -> None:
    event_orm.registration_deadline = datetime.now(UTC) - timedelta(hours=1)
    mock_event_repo.get_by_id.return_value = event_orm

    with pytest.raises(RegistrationDeadlinePassed):
        await service.register(register_payload)


async def test_register_no_available_seats(
    service: TicketService,
    mock_provider: AsyncMock,
    mock_event_repo: AsyncMock,
    register_payload: SEventRegistrationCreate,
    event_orm,
) -> None:
    event_orm.id = register_payload.event_id
    mock_event_repo.get_by_id.return_value = event_orm
    mock_provider.get_available_seats.return_value = SProviderAvailableSeats(seats=[])

    with pytest.raises(NoAvailableSeats):
        await service.register(register_payload)


async def test_register_seat_already_taken(
    service: TicketService,
    mock_provider: AsyncMock,
    mock_event_repo: AsyncMock,
    register_payload: SEventRegistrationCreate,
    event_orm,
) -> None:
    event_orm.id = register_payload.event_id
    mock_event_repo.get_by_id.return_value = event_orm

    mock_provider.get_available_seats.return_value = SProviderAvailableSeats(
        seats=["A16", "A17"]
    )

    with pytest.raises(SeatAlreadyTaken):
        await service.register(register_payload)


async def test_register_provider_race_condition(
    service: TicketService,
    mock_provider: AsyncMock,
    mock_event_repo: AsyncMock,
    register_payload: SEventRegistrationCreate,
    event_orm,
) -> None:
    event_orm.id = register_payload.event_id
    mock_event_repo.get_by_id.return_value = event_orm

    mock_provider.get_available_seats.return_value = SProviderAvailableSeats(
        seats=["A15"]
    )
    mock_provider.register.side_effect = ProviderBadRequest(
        "Seat taken", status_code=codes.BAD_REQUEST
    )

    with pytest.raises(SeatAlreadyTaken):
        await service.register(register_payload)


async def test_unregister_success(
    service: TicketService,
    mock_provider: AsyncMock,
    mock_ticket_repo: AsyncMock,
    ticket_id,
) -> None:
    ticket = TicketORM(
        ticket_id=ticket_id,
        event_id=uuid4(),
        first_name="Ivan",
        last_name="Ivanov",
        email="ivan@example.com",
        seat="A15",
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    mock_ticket_repo.get_by_id.return_value = ticket
    mock_provider.unregister.return_value = SProviderCancellationResponse(success=True)

    result = await service.unregister(ticket_id)

    assert result.success is True
    mock_ticket_repo.delete.assert_awaited_once_with(ticket)


async def test_unregister_ticket_not_found(
    service: TicketService,
    mock_ticket_repo: AsyncMock,
    ticket_id,
) -> None:
    mock_ticket_repo.get_by_id.return_value = None

    with pytest.raises(RegistrationNotFound):
        await service.unregister(ticket_id)


async def test_unregister_provider_not_found(
    service: TicketService,
    mock_provider: AsyncMock,
    mock_ticket_repo: AsyncMock,
    ticket_id,
) -> None:
    ticket = TicketORM(
        ticket_id=ticket_id,
        event_id=uuid4(),
        first_name="Ivan",
        last_name="Ivanov",
        email="ivan@example.com",
        seat="A15",
        created_at=datetime.now(UTC),
    )
    mock_ticket_repo.get_by_id.return_value = ticket
    mock_provider.unregister.side_effect = ProviderNotFound(
        "Not found", status_code=codes.NOT_FOUND
    )

    with pytest.raises(RegistrationNotFound):
        await service.unregister(ticket_id)

    mock_ticket_repo.delete.assert_awaited_once_with(ticket)
