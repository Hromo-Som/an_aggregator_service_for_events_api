import logging
from datetime import date
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.db.repositories.events import EventRepository
from events_aggregator.schemas.event import SEventPageRead
from events_aggregator.services.converters import event_orm_to_read

logger = logging.getLogger(__name__)


class EventService:
    """Бизнес-логика работы с событиями. Читает из локальной БД."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = EventRepository(session)

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

        results = [event_orm_to_read(e) for e in events]

        return SEventPageRead(
            count=total,
            next=self._build_page_url(base_url, date_from, page + 1, page_size, total),
            previous=self._build_page_url(
                base_url, date_from, page - 1, page_size, total
            ),
            results=results,
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
