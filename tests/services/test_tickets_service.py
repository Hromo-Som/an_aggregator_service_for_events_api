from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
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
from events_aggregator.enums import OutboxEventType
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
def mock_ticket_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_outbox_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_provider: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_ticket_repo: AsyncMock,
    mock_outbox_repo: MagicMock,
    mock_session: AsyncMock,
) -> TicketService:
    return TicketService(
        provider=mock_provider,
        event_repo=mock_event_repo,
        ticket_repo=mock_ticket_repo,
        outbox_repo=mock_outbox_repo,
        session=mock_session,
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
    mock_outbox_repo: MagicMock,
    mock_session: AsyncMock,
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

    await service.register(register_payload)

    mock_ticket_repo.add.assert_called_once()
    ticket_arg = mock_ticket_repo.add.call_args.args[0]
    assert ticket_arg.ticket_id == ticket_id
    assert ticket_arg.seat == "A15"

    mock_outbox_repo.add.assert_called_once()
    outbox_kwargs = mock_outbox_repo.add.call_args.kwargs
    assert outbox_kwargs["event_type"] == OutboxEventType.TICKET_PURCHASED
    assert outbox_kwargs["payload"]["ticket_id"] == str(ticket_id)
    assert outbox_kwargs["payload"]["email"] == "ivan@example.com"
    assert outbox_kwargs["payload"]["event_name"] == event_orm.name

    mock_session.commit.assert_awaited_once()


async def test_register_rollback_on_commit_failure(
    service: TicketService,
    mock_provider: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_ticket_repo: MagicMock,
    mock_outbox_repo: MagicMock,
    mock_session: AsyncMock,
    register_payload: SEventRegistrationCreate,
    event_orm,
) -> None:
    event_orm.id = register_payload.event_id
    mock_event_repo.get_by_id.return_value = event_orm
    mock_provider.get_available_seats.return_value = SProviderAvailableSeats(
        seats=["A15"]
    )
    mock_provider.register.return_value = SProviderRegistration(ticket_id=uuid4())

    mock_session.commit.side_effect = RuntimeError("DB connection lost")

    with pytest.raises(RuntimeError, match="DB connection lost"):
        await service.register(register_payload)

    mock_ticket_repo.add.assert_called_once()
    mock_outbox_repo.add.assert_called_once()


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
