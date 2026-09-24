from enum import Enum


class EventStatus(str, Enum):
    """Статус события от провайдера."""

    NEW = "new"
    PUBLISHED = "published"
    FINISHED = "finished"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> EventStatus:
        """Неизвестные значения маппим в UNKNOWN, чтобы не падать на новых."""
        return cls.UNKNOWN


class SyncStatus(str, Enum):
    """Статус синхронизации в sync_metadata."""

    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
