from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.db.models import OutboxEventORM
from events_aggregator.enums import OutboxStatus


class OutboxRepository:
    """Доступ к таблице outbox_events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(
        self,
        *,
        event_type: str,
        payload: dict,
    ) -> OutboxEventORM:
        """Добавить событие в outbox без коммита."""
        event = OutboxEventORM(
            event_type=event_type,
            payload=payload,
            status=OutboxStatus.PENDING,
            attempts=0,
            created_at=datetime.now(UTC),
        )

        self._session.add(event)
        return event

    async def fetch_pending(
        self,
        *,
        limit: int = 100,
    ) -> list[OutboxEventORM]:
        """Получить pending-записи с блокировкой FOR UPDATE SKIP LOCKED."""
        stmt = (
            select(OutboxEventORM)
            .where(OutboxEventORM.status == OutboxStatus.PENDING)
            .order_by(OutboxEventORM.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_sent(self, event: OutboxEventORM) -> None:
        event.status = OutboxStatus.SENT
        event.sent_at = datetime.now(UTC)
        await self._session.commit()

    async def mark_failed_attempt(
        self,
        event: OutboxEventORM,
        *,
        error: str,
        max_attempts: int,
    ) -> None:
        """Увеличить счётчик попыток. Если превысили — пометить FAILED."""
        event.attempts += 1
        event.last_error = error[:2000]
        if event.attempts >= max_attempts:
            event.status = OutboxStatus.FAILED
        await self._session.commit()
