from typing import Annotated

from fastapi import Depends, Request

from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.db.repositories.events import EventRepository
from events_aggregator.db.repositories.tickets import TicketRepository
from events_aggregator.db.session import SessionDep
from events_aggregator.services.events import EventService
from events_aggregator.services.sync import SyncService
from events_aggregator.services.tickets import TicketService


def get_provider(request: Request) -> EventsProviderClient:
    return request.app.state.provider


ProviderDep = Annotated[EventsProviderClient, Depends(get_provider)]


def get_event_service(
    session: SessionDep,
    provider: ProviderDep,
) -> EventService:
    """FastAPI-зависимость: EventService с сессией БД."""
    return EventService(session, provider)


def get_sync_service(provider: ProviderDep) -> SyncService:
    return SyncService(provider)


def get_ticket_service(
    provider: ProviderDep,
    session: SessionDep,
) -> TicketService:
    return TicketService(
        provider=provider,
        event_repo=EventRepository(session),
        ticket_repo=TicketRepository(session),
    )


EventServiceDep = Annotated[EventService, Depends(get_event_service)]
SyncServiceDep = Annotated[SyncService, Depends(get_sync_service)]
TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]
