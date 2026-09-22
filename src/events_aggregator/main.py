import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from events_aggregator.scheduler import scheduler, setup_scheduler
from events_aggregator.services.sync import SyncService

from .api.exception_handlers import register_exception_handlers
from .api.router import router as api_router
from .clients.events_provider.client import EventsProviderClient
from .config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

    provider = EventsProviderClient(
        base_url=settings.events_provider_base_url,
        api_key=settings.events_provider_api_key.get_secret_value(),
        timeout=settings.events_provider_timeout,
    )
    app.state.provider = provider

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
    await provider.aclose()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)


register_exception_handlers(app)
app.include_router(api_router)
