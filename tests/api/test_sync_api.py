from datetime import UTC, datetime
from unittest.mock import AsyncMock

from httpx import AsyncClient, codes

from events_aggregator.services.sync import (
    SyncAlreadyRunning,
    SyncResult,
)


def _make_result(*, full: bool) -> SyncResult:
    now = datetime.now(UTC)
    return SyncResult(
        synced_count=10,
        started_at=now,
        finished_at=now,
        last_changed_at=now,
        full=full,
    )


async def test_trigger_sync_incremental(
    api_client: AsyncClient,
    mock_sync_service: AsyncMock,
) -> None:
    mock_sync_service.sync.return_value = _make_result(full=False)

    response = await api_client.post("/api/sync/trigger")

    assert response.status_code == codes.OK
    body = response.json()
    assert body["synced_count"] == 10
    assert body["full"] is False
    mock_sync_service.sync.assert_awaited_once_with(full=False)


async def test_trigger_sync_full(
    api_client: AsyncClient,
    mock_sync_service: AsyncMock,
) -> None:
    mock_sync_service.sync.return_value = _make_result(full=True)

    response = await api_client.post("/api/sync/trigger?full=true")

    assert response.status_code == codes.OK
    assert response.json()["full"] is True
    mock_sync_service.sync.assert_awaited_once_with(full=True)


async def test_trigger_sync_already_running(
    api_client: AsyncClient,
    mock_sync_service: AsyncMock,
) -> None:
    mock_sync_service.sync.side_effect = SyncAlreadyRunning()

    response = await api_client.post("/api/sync/trigger")

    assert response.status_code == codes.CONFLICT
    assert "already running" in response.json()["detail"].lower()
