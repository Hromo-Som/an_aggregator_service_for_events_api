import time

from events_aggregator.services.cache import SeatsCache


def test_cache_set_and_get() -> None:
    cache = SeatsCache(ttl=30)
    cache.set("event-1", ["A1", "A2"])
    assert cache.get("event-1") == ["A1", "A2"]


def test_cache_returns_none_for_missing_key() -> None:
    cache = SeatsCache(ttl=30)
    assert cache.get("unknown") is None


def test_cache_returns_copy() -> None:
    """Мутация исходного списка не должна менять кэш."""
    cache = SeatsCache(ttl=30)
    seats = ["A1", "A2"]
    cache.set("event-1", seats)

    seats.append("A3")

    assert cache.get("event-1") == ["A1", "A2"]


def test_cache_invalidate() -> None:
    cache = SeatsCache(ttl=30)
    cache.set("event-1", ["A1"])
    cache.invalidate("event-1")
    assert cache.get("event-1") is None


def test_cache_invalidate_missing_key_is_noop() -> None:
    cache = SeatsCache(ttl=30)
    cache.invalidate("unknown")


def test_cache_clear() -> None:
    cache = SeatsCache(ttl=30)
    cache.set("event-1", ["A1"])
    cache.set("event-2", ["B1"])
    cache.clear()
    assert cache.get("event-1") is None
    assert cache.get("event-2") is None


def test_cache_ttl_expires() -> None:
    """TTL работает: после истечения get возвращает None."""
    cache = SeatsCache(ttl=1)
    cache.set("event-1", ["A1"])
    assert cache.get("event-1") == ["A1"]

    time.sleep(1.1)

    assert cache.get("event-1") is None
