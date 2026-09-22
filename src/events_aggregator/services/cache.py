from cachetools import TTLCache


class SeatsCache:
    """In-memory кэш свободных мест. TTL 30 секунд."""

    def __init__(self, ttl: int = 30, maxsize: int = 1000) -> None:
        self._cache: TTLCache[str, list[str]] = TTLCache(
            maxsize=maxsize,
            ttl=ttl,
        )

    def get(self, event_id: str) -> list[str] | None:
        return self._cache.get(event_id)

    def set(self, event_id: str, seats: list[str]) -> None:
        self._cache[event_id] = list(seats)

    def invalidate(self, event_id: str) -> None:
        """Удалить запись из кэша."""
        self._cache.pop(event_id, None)

    def clear(self) -> None:
        self._cache.clear()


seats_cache = SeatsCache(ttl=30, maxsize=1000)
