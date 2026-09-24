from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.db.models import SyncMetadataORM
from events_aggregator.enums import SyncStatus


class SyncMetadataRepository:
    """Доступ к метаданным синхронизации."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self) -> SyncMetadataORM:
        """Получить метаданные. Создать дефолтную строку, если её нет."""
        meta = await self._session.get(SyncMetadataORM, 1)

        if meta is None:
            meta = SyncMetadataORM(
                id=1,
                last_sync_time=None,
                last_changed_at=None,
                sync_status=SyncStatus.IDLE,
                last_error=None,
                updated_at=datetime.now(UTC),
            )
            self._session.add(meta)
            await self._session.commit()
            await self._session.refresh(meta)

        return meta

    async def mark_running(self) -> None:
        meta = await self.get()
        meta.sync_status = SyncStatus.RUNNING
        meta.last_error = None
        meta.updated_at = datetime.now(UTC)
        await self._session.commit()

    async def mark_success(
        self,
        *,
        synced_at: datetime,
        last_changed_at: datetime,
    ) -> None:
        meta = await self.get()
        meta.sync_status = SyncStatus.SUCCESS
        meta.last_sync_time = synced_at
        meta.last_changed_at = last_changed_at
        meta.last_error = None
        meta.updated_at = datetime.now(UTC)
        await self._session.commit()

    async def mark_failure(self, error: str) -> None:
        meta = await self.get()
        meta.sync_status = SyncStatus.FAILED
        meta.last_error = error[:2000]
        meta.updated_at = datetime.now(UTC)
        await self._session.commit()
