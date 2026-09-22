import logging
from datetime import UTC, datetime
from uuid import UUID

from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.clients.events_provider.exceptions import (
    ProviderBadRequest,
    ProviderNotFound,
)
from events_aggregator.clients.events_provider.schemas import (
    SProviderRegistrationCreate,
)
from events_aggregator.db.repositories.events import EventRepository
from events_aggregator.db.repositories.tickets import TicketRepository
from events_aggregator.schemas.event import (
    SEventCancellationRead,
    SEventRegistrationCreate,
    SEventRegistrationRead,
)
from events_aggregator.services.cache import seats_cache
from events_aggregator.services.exceptions import (
    EventNotFound,
    EventNotPublished,
    NoAvailableSeats,
    RegistrationDeadlinePassed,
    RegistrationNotFound,
    SeatAlreadyTaken,
)

logger = logging.getLogger(__name__)


class TicketService:
    """Регистрация и отмена."""

    def __init__(
        self,
        provider: EventsProviderClient,
        event_repo: EventRepository,
        ticket_repo: TicketRepository,
    ) -> None:
        self._provider = provider
        self._event_repo = event_repo
        self._ticket_repo = ticket_repo

    async def register(
        self,
        payload: SEventRegistrationCreate,
    ) -> SEventRegistrationRead:
        """Зарегистрировать участника."""
        event = await self._event_repo.get_by_id(payload.event_id)
        if event is None:
            raise EventNotFound(f"Event {payload.event_id} not found")

        if event.registration_deadline <= datetime.now(UTC):
            raise RegistrationDeadlinePassed(
                f"Registration deadline passed for event {payload.event_id}"
            )

        available = await self._get_seats(payload.event_id)
        if not available:
            raise NoAvailableSeats(f"No seats available for event {payload.event_id}")
        if payload.seat not in available:
            raise SeatAlreadyTaken(f"Seat {payload.seat} is not available")

        try:
            provider_payload = SProviderRegistrationCreate(
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=payload.email,
                seat=payload.seat,
            )
            result = await self._provider.register(
                event_id=payload.event_id,
                payload=provider_payload,
            )
        except ProviderNotFound as e:
            raise EventNotFound(f"Event {payload.event_id} not found") from e
        except ProviderBadRequest as e:
            raise SeatAlreadyTaken(f"Seat {payload.seat} is not available") from e

        await self._ticket_repo.create(
            ticket_id=result.ticket_id,
            event_id=payload.event_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            seat=payload.seat,
        )

        seats_cache.invalidate(str(payload.event_id))

        return SEventRegistrationRead(ticket_id=result.ticket_id)

    async def unregister(self, ticket_id: UUID) -> SEventCancellationRead:
        """Отменить регистрацию."""
        ticket = await self._ticket_repo.get_by_id(ticket_id)
        if ticket is None:
            raise RegistrationNotFound(f"Ticket {ticket_id} not found")

        try:
            result = await self._provider.unregister(
                event_id=ticket.event_id,
                ticket_id=ticket_id,
            )
        except ProviderNotFound as e:
            logger.warning("Provider says ticket %s not found", ticket_id)
            await self._ticket_repo.delete(ticket)
            raise RegistrationNotFound(f"Ticket {ticket_id} not found") from e

        if not result.success:
            logger.warning("Provider returned success=false for ticket %s", ticket_id)

        await self._ticket_repo.delete(ticket)
        seats_cache.invalidate(str(ticket.event_id))

        return SEventCancellationRead(success=result.success)

    async def _get_seats(self, event_id: UUID) -> list[str]:
        """Свободные места — из кэша или у провайдера."""
        event = await self._event_repo.get_by_id(event_id)
        if event is None:
            raise EventNotFound(f"Event {event_id} not found")

        if event.status != "published":
            raise EventNotPublished(
                f"Event {event_id} is not available for registration "
                f"(status: {event.status})"
            )

        cache_key = str(event_id)
        cached = seats_cache.get(cache_key)
        if cached is not None:
            return cached

        result = await self._provider.get_available_seats(event_id)
        seats_cache.set(cache_key, result.seats)
        return result.seats
