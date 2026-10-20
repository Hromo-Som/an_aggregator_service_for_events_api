import logging
from datetime import date
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.db.repositories.events import EventRepository
from events_aggregator.schemas.event import (
    SEventDetailRead,
    SEventPageRead,
    SEventSeatsRead,
)
from events_aggregator.services.converters import Converter
from events_aggregator.services.exceptions import (
    EventNotFound,
)
from events_aggregator.services.seats import resolve_available_seats

logger = logging.getLogger(__name__)


class EventService:
    """Бизнес-логика работы с событиями. Читает из локальной БД."""

    def __init__(self, session: AsyncSession, provider: EventsProviderClient) -> None:
        self._repo = EventRepository(session)
        self._provider = provider

    async def list_events(
        self,
        *,
        date_from: date | None = None,
        page: int = 1,
        page_size: int = 20,
        base_url: str,
    ) -> SEventPageRead:
        """Список событий с пагинацией и фильтром по дате."""
        offset = (page - 1) * page_size

        total = await self._repo.count(date_from=date_from)
        events = await self._repo.events_list(
            date_from=date_from,
            limit=page_size,
            offset=offset,
        )

        results = [Converter.event_orm_to_read(e) for e in events]

        return SEventPageRead(
            count=total,
            next=self._build_page_url(base_url, date_from, page + 1, page_size, total),
            previous=self._build_page_url(
                base_url, date_from, page - 1, page_size, total
            ),
            results=results,
        )

    async def get_event(self, event_id: UUID) -> SEventDetailRead:
        """Детали события из БД."""
        event = await self._repo.get_by_id(event_id)
        if event is None:
            raise EventNotFound(f"Event {event_id} not found")

        return Converter.event_orm_to_detail_read(event)

    async def get_available_seats(self, event_id: UUID) -> SEventSeatsRead:
        """Свободные места. Сначала из кэша, потом от провайдера."""
        event = await self._repo.get_by_id(event_id)
        if event is None:
            raise EventNotFound(f"Event {event_id} not found")

        seats = await resolve_available_seats(
            event=event,
            provider=self._provider,
        )

        return SEventSeatsRead(
            event_id=event_id,
            available_seats=seats,
        )

    @staticmethod
    def _build_page_url(
        base_url: str,
        date_from: date | None,
        page: int,
        page_size: int,
        total: int,
    ) -> str | None:
        """Построить URL для next/previous. None, если страница вне диапазона."""
        if page < 1:
            return None
        if (page - 1) * page_size >= total:
            return None

        params: dict[str, str] = {
            "page": str(page),
            "page_size": str(page_size),
        }

        if date_from is not None:
            params["date_from"] = date_from.isoformat()

        return f"{base_url}?{urlencode(params)}"
