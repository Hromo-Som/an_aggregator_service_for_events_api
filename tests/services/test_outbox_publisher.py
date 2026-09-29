from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import codes

from events_aggregator.clients.capashino.exceptions import CapashinoPermanentError
from events_aggregator.clients.exceptions import APIClientError
from events_aggregator.config import settings
from events_aggregator.db.models import OutboxEventORM
from events_aggregator.enums import OutboxEventType, OutboxStatus
from events_aggregator.services.outbox_publisher import OutboxPublisher


@pytest.fixture
def mock_capashino() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def publisher(mock_capashino: AsyncMock) -> OutboxPublisher:
    return OutboxPublisher(mock_capashino)


@pytest.fixture
def mock_outbox_repo() -> MagicMock:
    """OutboxRepository: fetch_pending/mark_* — async."""
    repo = MagicMock()
    repo.fetch_pending = AsyncMock()
    repo.mark_sent = AsyncMock()
    repo.mark_failed_attempt = AsyncMock()
    return repo


@pytest.fixture
def mock_outbox_repo_factory(mock_outbox_repo: MagicMock) -> MagicMock:
    """Мок OutboxRepository как класса — возвращает настроенный repo."""
    mock_cls = MagicMock(return_value=mock_outbox_repo)
    return mock_cls


def _make_event(**overrides) -> OutboxEventORM:
    """Создать OutboxEventORM с дефолтными полями для тестов."""
    base = {
        "id": uuid4(),
        "event_type": OutboxEventType.TICKET_PURCHASED,
        "payload": {
            "ticket_id": str(uuid4()),
            "event_id": str(uuid4()),
            "event_name": "Python Conf",
            "first_name": "Ivan",
            "last_name": "Ivanov",
            "email": "ivan@example.com",
            "seat": "A15",
        },
        "status": OutboxStatus.PENDING,
        "attempts": 0,
        "created_at": datetime.now(UTC),
    }
    base.update(overrides)
    return OutboxEventORM(**base)


def test_build_ticket_message_contains_fields() -> None:
    payload = {
        "event_name": "Python Conf",
        "seat": "A15",
        "ticket_id": "abc-123",
    }

    message = OutboxPublisher._build_ticket_message(payload)

    assert "Python Conf" in message
    assert "A15" in message
    assert "abc-123" in message


async def test_send_ticket_purchased_calls_capashino(
    publisher: OutboxPublisher,
    mock_capashino: AsyncMock,
) -> None:
    event = _make_event()

    await publisher._send_ticket_purchased(event)

    mock_capashino.send_notification.assert_awaited_once()
    kwargs = mock_capashino.send_notification.await_args.kwargs
    assert kwargs["reference_id"].__str__() == event.payload["ticket_id"]
    assert kwargs["idempotency_key"] == str(event.id)
    assert "Python Conf" in kwargs["message"]


async def test_dispatch_ticket_purchased(
    publisher: OutboxPublisher,
    mock_capashino: AsyncMock,
) -> None:
    event = _make_event(event_type=OutboxEventType.TICKET_PURCHASED)

    await publisher._dispatch(event)

    mock_capashino.send_notification.assert_awaited_once()


async def test_dispatch_unknown_type_raises(publisher: OutboxPublisher) -> None:
    event = _make_event(event_type="some.unknown.event")

    with pytest.raises(ValueError, match="unknown event type"):
        await publisher._dispatch(event)


async def test_publish_one_success_marks_sent(
    publisher: OutboxPublisher,
    mock_capashino: AsyncMock,
    mock_outbox_repo: MagicMock,
) -> None:
    event = _make_event()

    await publisher._publish_one(mock_outbox_repo, event)

    mock_outbox_repo.mark_sent.assert_awaited_once_with(event)
    mock_outbox_repo.mark_failed_attempt.assert_not_awaited()


async def test_publish_one_permanent_error_marks_failed(
    publisher: OutboxPublisher,
    mock_capashino: AsyncMock,
    mock_outbox_repo: MagicMock,
) -> None:
    """CapashinoPermanentError → mark_failed_attempt(max_attempts=1)."""
    mock_capashino.send_notification.side_effect = CapashinoPermanentError(
        "Bad request", status_code=codes.BAD_REQUEST
    )
    event = _make_event()

    await publisher._publish_one(mock_outbox_repo, event)

    mock_outbox_repo.mark_failed_attempt.assert_awaited_once()
    kwargs = mock_outbox_repo.mark_failed_attempt.await_args.kwargs
    assert kwargs["max_attempts"] == 1
    mock_outbox_repo.mark_sent.assert_not_awaited()


async def test_publish_one_conflict_treated_as_sent(
    publisher: OutboxPublisher,
    mock_capashino: AsyncMock,
    mock_outbox_repo: MagicMock,
) -> None:
    """409 → уведомление уже создано, помечаем как sent."""
    mock_capashino.send_notification.side_effect = APIClientError(
        "Conflict", status_code=codes.CONFLICT
    )
    event = _make_event()

    await publisher._publish_one(mock_outbox_repo, event)

    mock_outbox_repo.mark_sent.assert_awaited_once_with(event)
    mock_outbox_repo.mark_failed_attempt.assert_not_awaited()


async def test_publish_one_retryable_error_increments_attempts(
    publisher: OutboxPublisher,
    mock_capashino: AsyncMock,
    mock_outbox_repo: MagicMock,
) -> None:
    """5xx → mark_failed_attempt с max_attempts из настроек."""
    mock_capashino.send_notification.side_effect = APIClientError(
        "Server error", status_code=codes.INTERNAL_SERVER_ERROR
    )
    event = _make_event()

    await publisher._publish_one(mock_outbox_repo, event)

    mock_outbox_repo.mark_failed_attempt.assert_awaited_once()
    kwargs = mock_outbox_repo.mark_failed_attempt.await_args.kwargs
    assert kwargs["max_attempts"] == settings.outbox_max_attempts
    mock_outbox_repo.mark_sent.assert_not_awaited()


async def test_publish_one_unexpected_error_marks_failed(
    publisher: OutboxPublisher,
    mock_capashino: AsyncMock,
    mock_outbox_repo: MagicMock,
) -> None:
    """KeyError в payload → mark_failed_attempt, не падаем."""
    event = _make_event(payload={"ticket_id": "abc"})

    await publisher._publish_one(mock_outbox_repo, event)

    mock_outbox_repo.mark_failed_attempt.assert_awaited_once()
    mock_outbox_repo.mark_sent.assert_not_awaited()


async def test_publish_one_unknown_type_marks_failed(
    publisher: OutboxPublisher,
    mock_outbox_repo: MagicMock,
) -> None:
    """Неизвестный event_type → ValueError → mark_failed_attempt."""
    event = _make_event(event_type="unknown.type")

    await publisher._publish_one(mock_outbox_repo, event)

    mock_outbox_repo.mark_failed_attempt.assert_awaited_once()
    mock_outbox_repo.mark_sent.assert_not_awaited()


async def test_process_batch_empty(
    publisher: OutboxPublisher,
    mock_outbox_repo: MagicMock,
    mock_outbox_repo_factory: MagicMock,
) -> None:
    mock_outbox_repo.fetch_pending.return_value = []

    with patch(
        "events_aggregator.services.outbox_publisher.OutboxRepository",
        mock_outbox_repo_factory,
    ):
        await publisher._process_batch()

    mock_outbox_repo.fetch_pending.assert_awaited_once()
    mock_outbox_repo.mark_sent.assert_not_awaited()


async def test_process_batch_publishes_each_event(
    publisher: OutboxPublisher,
    mock_capashino: AsyncMock,
    mock_outbox_repo: MagicMock,
    mock_outbox_repo_factory: MagicMock,
) -> None:
    event_a = _make_event()
    event_b = _make_event()
    mock_outbox_repo.fetch_pending.return_value = [event_a, event_b]

    with patch(
        "events_aggregator.services.outbox_publisher.OutboxRepository",
        mock_outbox_repo_factory,
    ):
        await publisher._process_batch()

    assert mock_capashino.send_notification.await_count == 2
    assert mock_outbox_repo.mark_sent.await_count == 2


def test_stop_sets_event(publisher: OutboxPublisher) -> None:
    assert not publisher._stop.is_set()

    publisher.stop()

    assert publisher._stop.is_set()


async def test_run_exits_after_stop(publisher: OutboxPublisher) -> None:
    """run() завершается, когда вызван stop()."""
    import asyncio

    with (
        patch("events_aggregator.services.outbox_publisher.async_session"),
        patch(
            "events_aggregator.services.outbox_publisher.OutboxRepository"
        ) as MockRepo,
    ):
        repo = MockRepo.return_value
        repo.fetch_pending = AsyncMock(return_value=[])

        task = asyncio.create_task(publisher.run())
        await asyncio.sleep(0.05)
        publisher.stop()

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except TimeoutError:
            task.cancel()
            pytest.fail("run() did not exit after stop()")

        assert task.done()
