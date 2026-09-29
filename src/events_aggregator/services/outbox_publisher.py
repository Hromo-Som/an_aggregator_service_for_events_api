import asyncio
import logging
from uuid import UUID

from fastapi import status

from events_aggregator.clients.capashino.client import CapashinoClient
from events_aggregator.clients.capashino.exceptions import CapashinoPermanentError
from events_aggregator.clients.exceptions import APIClientError
from events_aggregator.config import settings
from events_aggregator.db.models import OutboxEventORM
from events_aggregator.db.repositories.outbox import OutboxRepository
from events_aggregator.db.session import async_session
from events_aggregator.enums import OutboxEventType

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Фоновый воркер: читает pending-записи из outbox и публикует их."""

    def __init__(self, capashino_client: CapashinoClient) -> None:
        self._capashino = capashino_client
        self._stop = asyncio.Event()

    async def run(self) -> None:
        """Основной цикл. Запускается как asyncio.Task в lifespan."""
        logger.info(
            "outbox_publisher_started interval=%.1fs batch=%d",
            settings.outbox_poll_interval,
            settings.outbox_batch_size,
        )

        try:
            while not self._stop.is_set():
                try:
                    await self._process_batch()
                except Exception:
                    logger.exception("outbox_publisher_iteration_failed")

                try:
                    await asyncio.wait_for(
                        self._stop.wait(),
                        timeout=settings.outbox_poll_interval,
                    )
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("outbox_publisher_cancelled")
            raise
        finally:
            logger.info("outbox_publisher_stopped")

    def stop(self) -> None:
        """Попросить воркер завершиться (для graceful shutdown)."""
        self._stop.set()

    async def _process_batch(self) -> None:
        """Обработать одну порцию pending-записей."""
        async with async_session() as session:
            repo = OutboxRepository(session)
            events = await repo.fetch_pending(limit=settings.outbox_batch_size)

            if not events:
                return

            logger.info("outbox_batch_picked count=%d", len(events))

            for event in events:
                await self._publish_one(repo, event)

    async def _publish_one(
        self,
        repo: OutboxRepository,
        event: OutboxEventORM,
    ) -> None:
        """Отправить одно событие."""
        try:
            await self._dispatch(event)
        except CapashinoPermanentError as e:
            logger.error(
                "outbox_publish_permanent_failure id=%s type=%s error=%s",
                event.id,
                event.event_type,
                e,
            )
            await repo.mark_failed_attempt(event, error=str(e), max_attempts=1)
        except APIClientError as e:
            if e.status_code == status.HTTP_409_CONFLICT:
                logger.warning(
                    "outbox_idempotent_conflict id=%s -> treat as sent",
                    event.id,
                )
                await repo.mark_sent(event)
            else:
                logger.warning(
                    "outbox_publish_failed id=%s attempts=%d error=%s",
                    event.id,
                    event.attempts + 1,
                    e,
                )
                await repo.mark_failed_attempt(
                    event, error=str(e), max_attempts=settings.outbox_max_attempts
                )
        except Exception:
            logger.exception("outbox_publish_unexpected_error id=%s", event.id)
            await repo.mark_failed_attempt(
                event,
                error="unexpected error",
                max_attempts=settings.outbox_max_attempts,
            )
        else:
            logger.info(
                "outbox_publish_succeeded id=%s type=%s",
                event.id,
                event.event_type,
            )
            await repo.mark_sent(event)

    async def _dispatch(self, event: OutboxEventORM) -> None:
        """Роутинг события по типу."""
        if event.event_type == OutboxEventType.TICKET_PURCHASED:
            await self._send_ticket_purchased(event)
        else:
            raise ValueError("unknown event type")

    async def _send_ticket_purchased(self, event: OutboxEventORM) -> None:
        """Отправить уведомление о покупке билета в Capashino."""
        payload = event.payload
        message = self._build_ticket_message(payload)

        await self._capashino.send_notification(
            message=message,
            reference_id=UUID(payload["ticket_id"]),
            idempotency_key=str(event.id),
        )

    @staticmethod
    def _build_ticket_message(payload: dict) -> str:
        return (
            f"Вы успешно зарегистрированы на мероприятие - "
            f"{payload['event_name']}. "
            f"Место: {payload['seat']}. "
            f"Номер билета: {payload['ticket_id']}."
        )
