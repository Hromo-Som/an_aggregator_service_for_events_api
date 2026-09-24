import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.clients.events_provider.paginator import EventsPaginator
from events_aggregator.clients.events_provider.schemas import SProviderEvent
from events_aggregator.config import settings
from events_aggregator.db.repositories.events import EventRepository
from events_aggregator.db.repositories.sync import SyncMetadataRepository
from events_aggregator.db.session import async_session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    """Результат синхронизации."""

    synced_count: int
    started_at: datetime
    finished_at: datetime
    last_changed_at: datetime
    full: bool


class SyncAlreadyRunning(Exception):
    """Синхронизация уже выполняется."""


class SyncService:
    """Синхронизация событий из провайдера в БД."""

    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        provider: EventsProviderClient,
        paginator: EventsPaginator | None = None,
    ):
        self._provider = provider
        self._paginator = paginator or EventsPaginator(provider)

    async def sync(self, *, full: bool = False) -> SyncResult:
        """Запустить синхронизацию."""
        if self._lock.locked():
            raise SyncAlreadyRunning()

        async with self._lock:
            return await self._do_sync(full=full)

    async def _do_sync(self, *, full: bool) -> SyncResult:
        started_at = datetime.now(UTC)
        async with async_session() as session:
            meta_repo = SyncMetadataRepository(session)
            meta = await meta_repo.get()

            if full or meta.last_changed_at is None:
                changed_at = datetime.fromisoformat(
                    f"{settings.sync_first_date}T00:00:00+00:00"
                )
                logger.info("sync_started mode=full changed_at=%s", changed_at)
            else:
                changed_at = meta.last_changed_at
                logger.info("sync_started mode=incremental changed_at=%s", changed_at)

            await meta_repo.mark_running()

        try:
            count, max_changed_at = await self._fetch_and_store(
                changed_at=changed_at,
                synced_at=started_at,
            )
        except Exception as e:
            logger.exception("sync_failed")
            async with async_session() as session:
                await SyncMetadataRepository(session).mark_failure(str(e))
            raise

        new_changed_at = max_changed_at or changed_at
        finished_at = datetime.now(UTC)

        async with async_session() as session:
            await SyncMetadataRepository(session).mark_success(
                synced_at=finished_at,
                last_changed_at=new_changed_at,
            )

        logger.info(
            "sync_completed count=%s duration=%.2fs last_changed_at=%s",
            count,
            (finished_at - started_at).total_seconds(),
            new_changed_at,
        )

        return SyncResult(
            synced_count=count,
            started_at=started_at,
            finished_at=finished_at,
            last_changed_at=new_changed_at,
            full=full,
        )

    async def _fetch_and_store(
        self,
        *,
        changed_at: datetime,
        synced_at: datetime,
    ) -> tuple[int, datetime | None]:
        """Пройти по всем страницам провайдера и upsert'ить события."""
        total = 0
        max_changed_at: datetime | None = None
        batch: list[SProviderEvent] = []

        async with async_session() as session:
            event_repo = EventRepository(session)

            async for event in self._paginator.iter_all_events(
                changed_at=changed_at.date().isoformat(),
            ):
                batch.append(event)
                if event.changed_at and (
                    max_changed_at is None or event.changed_at > max_changed_at
                ):
                    max_changed_at = event.changed_at

                if len(batch) >= settings.sync_batch_size:
                    await event_repo.upsert_many(
                        [self._to_row(e, synced_at) for e in batch]
                    )
                    total += len(batch)
                    batch.clear()

            if batch:
                await event_repo.upsert_many(
                    [self._to_row(e, synced_at) for e in batch]
                )
                total += len(batch)

        return total, max_changed_at

    @staticmethod
    def _to_row(event: SProviderEvent, synced_at: datetime) -> dict:
        """SProviderEvent → строка для EventRepository.upsert_many."""
        return {
            "id": event.id,
            "name": event.name,
            "status": event.status,
            "place_id": event.place.id,
            "place_name": event.place.name,
            "place_city": event.place.city,
            "place_address": event.place.address,
            "seats_pattern": event.place.seats_pattern,
            "event_time": event.event_time,
            "registration_deadline": event.registration_deadline,
            "number_of_visitors": event.number_of_visitors,
            "changed_at": event.changed_at,
            "synced_at": synced_at,
        }
