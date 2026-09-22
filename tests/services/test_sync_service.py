from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from events_aggregator.clients.events_provider.schemas import (
    SProviderEvent,
    SProviderPlace,
)
from events_aggregator.services.sync import (
    SyncAlreadyRunning,
    SyncService,
)


@pytest.fixture
def mock_provider() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_provider: AsyncMock) -> SyncService:
    return SyncService(mock_provider)


@pytest.fixture
def mock_meta_repo() -> Iterator[AsyncMock]:
    with patch("events_aggregator.services.sync.SyncMetadataRepository") as MockRepo:
        repo = AsyncMock()
        MockRepo.return_value = repo
        yield repo


@pytest.fixture
def mock_event_repo() -> Iterator[AsyncMock]:
    with patch("events_aggregator.services.sync.EventRepository") as MockRepo:
        repo = AsyncMock()
        MockRepo.return_value = repo
        yield repo


@pytest.fixture
def sample_event() -> SProviderEvent:
    """Готовое событие от провайдера."""
    now = datetime.now(UTC)
    return _make_event(changed_at=now)


def _make_event(
    *,
    changed_at: datetime | None = None,
    name: str = "Test Event",
) -> SProviderEvent:
    """Создать SProviderEvent со всеми обязательными полями."""
    now = datetime.now(UTC)
    return SProviderEvent(
        id=uuid4(),
        name=name,
        place=SProviderPlace(
            id=uuid4(),
            name="Place",
            city="Moscow",
            address="Lenina 1",
            seats_pattern="A1-10",
            changed_at=now,
            created_at=now,
        ),
        event_time=now + timedelta(days=1),
        registration_deadline=now + timedelta(hours=12),
        status="published",
        number_of_visitors=0,
        changed_at=changed_at or now,
        created_at=now,
        status_changed_at=now,
    )


def _make_async_gen(*events: SProviderEvent):
    """Создать функцию, возвращающую async-генератор по событиям."""

    async def _iter(*args, **kwargs):
        for event in events:
            yield event

    return _iter


def _make_meta(*, last_changed_at: datetime | None) -> AsyncMock:
    """Мок SyncMetadataORM с нужным last_changed_at."""
    meta = AsyncMock()
    meta.last_changed_at = last_changed_at
    meta.sync_status = "idle"
    return meta


async def test_sync_raises_when_already_running(
    service: SyncService,
) -> None:
    async with service._lock:
        with pytest.raises(SyncAlreadyRunning):
            await service.sync(full=False)


async def test_sync_no_events(
    service: SyncService,
    mock_provider: AsyncMock,
    mock_meta_repo: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_session_factory: AsyncMock,
) -> None:
    mock_meta_repo.get.return_value = _make_meta(last_changed_at=None)
    mock_provider.iter_all_events = _make_async_gen()

    result = await service.sync(full=False)

    assert result.synced_count == 0
    mock_event_repo.upsert_many.assert_not_awaited()
    mock_meta_repo.mark_running.assert_awaited_once()
    mock_meta_repo.mark_success.assert_awaited_once()


async def test_sync_one_event(
    service: SyncService,
    mock_provider: AsyncMock,
    mock_meta_repo: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_session_factory: AsyncMock,
    sample_event: SProviderEvent,
) -> None:
    mock_meta_repo.get.return_value = _make_meta(last_changed_at=None)
    mock_provider.iter_all_events = _make_async_gen(sample_event)

    result = await service.sync(full=False)

    assert result.synced_count == 1
    mock_event_repo.upsert_many.assert_awaited_once()
    rows = mock_event_repo.upsert_many.await_args.args[0]
    assert len(rows) == 1
    assert rows[0]["id"] == sample_event.id
    assert rows[0]["name"] == sample_event.name


async def test_sync_uses_max_changed_at(
    service: SyncService,
    mock_provider: AsyncMock,
    mock_meta_repo: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_session_factory: AsyncMock,
) -> None:
    now = datetime.now(UTC)
    older = now - timedelta(hours=2)
    newer = now - timedelta(hours=1)

    event_older = _make_event(changed_at=older, name="Older")
    event_newer = _make_event(changed_at=newer, name="Newer")

    mock_meta_repo.get.return_value = _make_meta(last_changed_at=None)
    mock_provider.iter_all_events = _make_async_gen(event_older, event_newer)

    result = await service.sync(full=False)

    assert result.synced_count == 2
    assert result.last_changed_at == newer


async def test_sync_incremental_uses_last_changed_at(
    service: SyncService,
    mock_provider: AsyncMock,
    mock_meta_repo: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_session_factory: AsyncMock,
) -> None:
    last_changed = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
    captured: list[str | None] = []

    async def capture_iter(*args, **kwargs):
        captured.append(kwargs.get("changed_at"))
        return
        yield

    mock_provider.iter_all_events = capture_iter
    mock_meta_repo.get.return_value = _make_meta(last_changed_at=last_changed)

    await service.sync(full=False)

    assert captured == ["2026-01-01"]


async def test_sync_full_uses_first_date(
    service: SyncService,
    mock_provider: AsyncMock,
    mock_meta_repo: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_session_factory: AsyncMock,
) -> None:
    captured: list[str | None] = []

    async def capture_iter(*args, **kwargs):
        captured.append(kwargs.get("changed_at"))
        return
        yield

    mock_provider.iter_all_events = capture_iter
    mock_meta_repo.get.return_value = _make_meta(
        last_changed_at=datetime(2026, 1, 1, tzinfo=UTC)
    )

    await service.sync(full=True)

    assert captured == ["2000-01-01"]


async def test_sync_marks_failure_on_error(
    service: SyncService,
    mock_provider: AsyncMock,
    mock_meta_repo: AsyncMock,
    mock_event_repo: AsyncMock,
    mock_session_factory: AsyncMock,
) -> None:
    mock_meta_repo.get.return_value = _make_meta(last_changed_at=None)

    async def failing_iter(*args, **kwargs):
        raise RuntimeError("Provider is down")
        yield

    mock_provider.iter_all_events = failing_iter

    with pytest.raises(RuntimeError):
        await service.sync(full=False)

    mock_meta_repo.mark_failure.assert_awaited_once()
    error_arg = mock_meta_repo.mark_failure.await_args.args[0]
    assert "Provider is down" in error_arg
