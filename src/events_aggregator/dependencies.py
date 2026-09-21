from typing import Annotated

from fastapi import Depends

from events_aggregator.db.session import SessionDep
from events_aggregator.services.events import EventService


def get_event_service(
    session: SessionDep,
) -> EventService:
    """FastAPI-зависимость: EventService с сессией БД."""
    return EventService(session)


EventServiceDep = Annotated[EventService, Depends(get_event_service)]
