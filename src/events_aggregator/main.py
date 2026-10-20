import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from starlette.responses import Response

from events_aggregator.api.exception_handlers import register_exception_handlers
from events_aggregator.api.router import router as api_router
from events_aggregator.clients.capashino.client import CapashinoClient
from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.config import settings
from events_aggregator.db.repositories.events import EventRepository
from events_aggregator.db.repositories.outbox import OutboxRepository
from events_aggregator.db.repositories.tickets import TicketRepository
from events_aggregator.db.session import SessionDep
from events_aggregator.enums import OutboxEventType
from events_aggregator.monitoring.http_metrics import MetricsMiddleware
from events_aggregator.monitoring.metrics import (
    EVENTS_TOTAL,
    TICKETS_CANCELLED_TOTAL,
    TICKETS_CREATED_TOTAL,
)
from events_aggregator.scheduler import scheduler, setup_scheduler
from events_aggregator.services.outbox_publisher import OutboxPublisher
from events_aggregator.services.sync import SyncService

logger = logging.getLogger(__name__)


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
        except asyncio.CancelledError:
            logger.info("initial_sync_cancelled")
            raise
        except Exception:
            logger.exception("initial_sync_failed")

    initial_sync_task = asyncio.create_task(initial_sync())

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
        with suppress(asyncio.CancelledError):
            await publisher_task

    if not initial_sync_task.done():
        logger.info("initial_sync_cancel_on_shutdown")
        initial_sync_task.cancel()
        with suppress(asyncio.CancelledError):
            await initial_sync_task

    await capashino.aclose()
    await provider.aclose()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(MetricsMiddleware)


@app.get("/metrics", include_in_schema=False)
async def metrics(session: SessionDep) -> Response:
    """Prometheus text exposition format. Без авторизации."""
    events_repo = EventRepository(session)
    tickets_repo = TicketRepository(session)
    outbox_repo = OutboxRepository(session)

    events_count, tickets_count, cancelled_count = await asyncio.gather(
        events_repo.count(),
        tickets_repo.count(),
        outbox_repo.count_by_type(OutboxEventType.TICKET_CANCELLED),
    )

    EVENTS_TOTAL.set(events_count)
    TICKETS_CREATED_TOTAL.set(tickets_count)
    TICKETS_CANCELLED_TOTAL.set(cancelled_count)

    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


app.include_router(api_router)
register_exception_handlers(app)
