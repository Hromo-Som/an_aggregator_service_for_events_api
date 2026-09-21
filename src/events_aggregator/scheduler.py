import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.config import settings
from events_aggregator.services.sync import SyncAlreadyRunning, SyncService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler(provider: EventsProviderClient) -> None:
    """Настроить периодические задачи."""
    if not settings.sync_enabled:
        logger.info("scheduler_disabled")
        return

    sync_service = SyncService(provider)

    async def periodic_sync() -> None:
        try:
            result = await sync_service.sync(full=False)
            logger.info("periodic_sync_done count=%s", result.synced_count)
        except SyncAlreadyRunning:
            logger.warning("periodic_sync_skipped_already_running")
        except Exception:
            logger.exception("periodic_sync_failed")

    scheduler.add_job(
        periodic_sync,
        trigger=CronTrigger(hour=settings.sync_hour, minute=0),
        id="periodic_sync",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    logger.info("scheduler_configured hour=%s", settings.sync_hour)
