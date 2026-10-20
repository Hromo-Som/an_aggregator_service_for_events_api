from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.clients.events_provider.exceptions import ProviderNotFound
from events_aggregator.db.models import EventORM
from events_aggregator.enums import EventStatus
from events_aggregator.monitoring.metrics import CACHE_HITS_TOTAL, CACHE_MISSES_TOTAL
from events_aggregator.services.cache import seats_cache
from events_aggregator.services.exceptions import EventNotPublished, NoAvailableSeats


async def resolve_available_seats(
    *,
    event: EventORM,
    provider: EventsProviderClient,
) -> list[str]:
    """Получить список свободных мест для события."""
    if event.status != EventStatus.PUBLISHED:
        raise EventNotPublished(
            f"Event {event.id} is not available for registration "
            f"(status: {event.status})"
        )

    cache_key = str(event.id)
    cached = seats_cache.get(cache_key)
    if cached is not None:
        CACHE_HITS_TOTAL.inc()
        return cached

    CACHE_MISSES_TOTAL.inc()

    try:
        result = await provider.get_available_seats(event.id)
    except ProviderNotFound as e:
        raise NoAvailableSeats(f"Event {event.id} not found") from e

    seats_cache.set(cache_key, result.seats)
    return result.seats
