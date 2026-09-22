from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query, Request

from events_aggregator.dependencies import EventServiceDep
from events_aggregator.schemas.event import (
    SEventDetailRead,
    SEventPageRead,
    SEventSeatsRead,
)

router = APIRouter(prefix="/events", tags=["events"])


@router.get(
    "",
    response_model=SEventPageRead,
)
async def list_events(
    request: Request,
    service: EventServiceDep,
    date_from: date | None = None,
    page: int = Query(
        default=1,
        ge=1,
        le=100,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
) -> SEventPageRead:
    """Список событий с пагинацией и фильтром по дате."""
    base_url = str(request.url_for("list_events")).rstrip("/")

    return await service.list_events(
        base_url=base_url,
        date_from=date_from,
        page=page,
        page_size=page_size,
    )


@router.get("/{event_id}", response_model=SEventDetailRead)
async def get_event(event_id: UUID, service: EventServiceDep) -> SEventDetailRead:
    """Детали события по ID."""
    return await service.get_event(event_id)


@router.get("/{event_id}/seats", response_model=SEventSeatsRead)
async def get_event_seats(event_id: UUID, service: EventServiceDep) -> SEventSeatsRead:
    """Свободные места. Кэш 30 секунд."""
    return await service.get_available_seats(event_id)
