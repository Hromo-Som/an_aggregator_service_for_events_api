from datetime import date

from fastapi import APIRouter, Query, Request

from events_aggregator.dependencies import EventServiceDep
from events_aggregator.schemas.event import SEventPageRead

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
