from collections.abc import Iterator

import pytest
import respx

from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.clients.events_provider.paginator import EventsPaginator
from tests.constants import API_KEY, BASE_URL


@pytest.fixture
def respx_router() -> Iterator[respx.MockRouter]:
    """Активный respx-мок. Все httpx-запросы перехватываются."""
    with respx.mock(
        base_url=BASE_URL,
        assert_all_called=False,
    ) as router:
        yield router


@pytest.fixture
async def provider_client() -> EventsProviderClient:
    """Клиент провайдера, привязанный к тестовому base_url."""
    return EventsProviderClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        timeout=1.0,
    )


@pytest.fixture
def paginator(provider_client: EventsProviderClient) -> EventsPaginator:
    return EventsPaginator(provider_client)
