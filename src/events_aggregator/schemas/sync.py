from datetime import datetime

from pydantic import BaseModel


class SSyncResultRead(BaseModel):
    """Результат ручной синхронизации."""

    synced_count: int
    started_at: datetime
    finished_at: datetime
    last_changed_at: datetime
    full: bool


class SSyncStatusRead(BaseModel):
    """Текущий статус синхронизации."""

    last_sync_time: datetime | None
    last_changed_at: datetime | None
    sync_status: str
    last_error: str | None
