from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.db.models import IdempotencyRecordORM


class IdempotencyRepository:
    """Доступ к таблице idempotency_keys."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> IdempotencyRecordORM | None:
        return await self._session.get(IdempotencyRecordORM, key)

    def add(
        self,
        *,
        key: str,
        request_hash: str,
        response_body: dict,
        status_code: int,
    ) -> IdempotencyRecordORM:
        """Добавить запись. НЕ коммитит — коммит в сервисе."""
        record = IdempotencyRecordORM(
            key=key,
            request_hash=request_hash,
            response_body=response_body,
            status_code=status_code,
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        return record

    async def lock_key(self, key: str) -> None:
        """Advisory lock по ключу — защита от race condition."""
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": key},
        )
