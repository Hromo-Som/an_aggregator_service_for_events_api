import logging
from collections.abc import AsyncIterator
from urllib.parse import urlparse

from .client import EventsProviderClient
from .exceptions import EventsProviderError
from .schemas import SProviderEvent

logger = logging.getLogger(__name__)


class EventsPaginator:
    """Обходит все страницы событий через next."""

    MAX_PAGES = 100

    def __init__(self, client: EventsProviderClient) -> None:
        self._client = client

    async def iter_all_events(
        self,
        changed_at: str | None = None,
    ) -> AsyncIterator[SProviderEvent]:
        """Итерировать все события, следуя по next."""
        page = await self._client.get_events_list(changed_at=changed_at)

        for event in page.results:
            yield event

        pages_seen = 1
        while page.next:
            if pages_seen >= self.MAX_PAGES:
                raise EventsProviderError(f"Pagination exceeded {self.MAX_PAGES} pages")

            self._ensure_same_host(page.next)
            page = await self._client.get_events_page(page.next)

            for event in page.results:
                yield event

            pages_seen += 1

    def _ensure_same_host(self, url: str) -> None:
        """Защита от SSRF: next должен вести на тот же хост."""
        base_host = urlparse(self._client.base_url).netloc
        target_host = urlparse(url).netloc
        if base_host != target_host:
            raise EventsProviderError(
                f"Pagination link points to a different host: "
                f"{target_host} (expected {base_host})"
            )
