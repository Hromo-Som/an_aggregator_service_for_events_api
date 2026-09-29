import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from events_aggregator.api.exception_handlers import register_exception_handlers
from events_aggregator.api.router import router as api_router
from events_aggregator.clients.capashino.client import CapashinoClient
from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.config import settings
from events_aggregator.monitoring import setup_sentry
from events_aggregator.scheduler import scheduler, setup_scheduler
from events_aggregator.services.outbox_publisher import OutboxPublisher
from events_aggregator.services.sync import SyncService

logger = logging.getLogger(__name__)

setup_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):

    provider = EventsProviderClient(
        base_url=settings.events_provider_base_url,
        api_key=settings.events_provider_api_key.get_secret_value(),
        timeout=settings.events_provider_timeout,
    )
    app.state.provider = provider

    capashino = CapashinoClient(
        base_url=settings.capashino_base_url,
        api_key=settings.capashino_api_key.get_secret_value(),
        timeout=settings.capashino_timeout,
    )
    app.state.capashino = capashino

    publisher = OutboxPublisher(capashino)
    publisher_task = asyncio.create_task(publisher.run())

    async def initial_sync() -> None:
        try:
            result = await SyncService(provider).sync(full=False)
            logger.info("initial_sync_done count=%s", result.synced_count)
        except Exception:
            logger.exception("initial_sync_failed")

    asyncio.create_task(initial_sync())

    setup_scheduler(provider)
    if settings.sync_enabled:
        scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)

    publisher.stop()

    try:
        await asyncio.wait_for(publisher_task, timeout=5.0)
    except TimeoutError:
        logger.warning("outbox_publisher_shutdown_timeout")
        publisher_task.cancel()

    await capashino.aclose()
    await provider.aclose()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)


app.include_router(api_router)
register_exception_handlers(app)
