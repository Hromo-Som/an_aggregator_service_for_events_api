from fastapi import APIRouter, HTTPException, status

from events_aggregator.dependencies import SyncServiceDep
from events_aggregator.schemas.sync import SSyncResultRead
from events_aggregator.services.sync import (
    SyncAlreadyRunning,
    SyncResult,
)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post(
    "/trigger",
    response_model=SSyncResultRead,
    status_code=status.HTTP_200_OK,
    summary="Запустить синхронизацию вручную",
)
async def trigger_sync(
    service: SyncServiceDep,
    full: bool = False,
) -> SSyncResultRead:
    """Ручной запуск синхронизации."""
    try:
        result: SyncResult = await service.sync(full=full)
    except SyncAlreadyRunning as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sync is already running",
        ) from e

    return SSyncResultRead(
        synced_count=result.synced_count,
        started_at=result.started_at,
        finished_at=result.finished_at,
        last_changed_at=result.last_changed_at,
        full=result.full,
    )
