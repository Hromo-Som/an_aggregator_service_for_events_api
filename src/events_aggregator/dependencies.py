from typing import Annotated

from fastapi import Depends, Request

from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.db.session import SessionDep
from events_aggregator.services.events import EventService
from events_aggregator.services.sync import SyncService


def get_provider(request: Request) -> EventsProviderClient:
    return request.app.state.provider


ProviderDep = Annotated[EventsProviderClient, Depends(get_provider)]


def get_event_service(
    session: SessionDep,
) -> EventService:
    """FastAPI-зависимость: EventService с сессией БД."""
    return EventService(session)


def get_sync_service(provider: ProviderDep) -> SyncService:
    return SyncService(provider)


EventServiceDep = Annotated[EventService, Depends(get_event_service)]
SyncServiceDep = Annotated[SyncService, Depends(get_sync_service)]
