from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.db.models import EventORM


class EventRepository:
    """Доступ к таблице events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, events: list[dict]) -> int:
        """Вставить или обновить события одним запросом."""
        if not events:
            return 0

        stmt = insert(EventORM).values(events)
        stmt = stmt.on_conflict_do_update(
            index_elements=[EventORM.id],
            set_={
                "name": stmt.excluded.name,
                "status": stmt.excluded.status,
                "place_id": stmt.excluded.place_id,
                "place_name": stmt.excluded.place_name,
                "place_city": stmt.excluded.place_city,
                "place_address": stmt.excluded.place_address,
                "seats_pattern": stmt.excluded.seats_pattern,
                "event_time": stmt.excluded.event_time,
                "registration_deadline": stmt.excluded.registration_deadline,
                "number_of_visitors": stmt.excluded.number_of_visitors,
                "changed_at": stmt.excluded.changed_at,
                "synced_at": stmt.excluded.synced_at,
            },
        )

        await self._session.execute(stmt)
        await self._session.commit()
        return len(events)

    async def get_by_id(self, event_id: UUID) -> EventORM | None:
        """Получить событие по ID."""
        return await self._session.get(EventORM, event_id)

    async def events_list(
        self,
        *,
        date_from: date | None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EventORM]:
        """Список событий с фильтром по дате и пагинацией."""
        stmt = select(EventORM).order_by(EventORM.event_time)

        if date_from is not None:
            stmt = stmt.where(
                EventORM.event_time
                >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
            )

        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        date_from: date | None,
    ) -> int:
        """Количество событий с учётом фильтра."""
        stmt = select(func.count()).select_from(EventORM)

        if date_from is not None:
            stmt = stmt.where(
                EventORM.event_time
                >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
            )

        result = await self._session.execute(stmt)
        return result.scalar_one()
