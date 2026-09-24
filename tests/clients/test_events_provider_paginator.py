import httpx
import pytest
import respx

from events_aggregator.clients.events_provider.exceptions import EventsProviderError
from events_aggregator.clients.events_provider.paginator import EventsPaginator
from tests.clients.helpers import build_event_json, build_page_json


async def test_iter_all_events_single_page(
    respx_router: respx.MockRouter,
    paginator: EventsPaginator,
) -> None:
    respx_router.get("/events/").mock(
        return_value=httpx.Response(
            httpx.codes.OK,
            json=build_page_json(
                [
                    build_event_json(name="A"),
                    build_event_json(name="B"),
                ]
            ),
        )
    )

    events = [e async for e in paginator.iter_all_events()]

    assert len(events) == 2
    assert events[0].name == "A"
    assert events[1].name == "B"


async def test_iter_all_events_follows_next(
    respx_router: respx.MockRouter,
    paginator: EventsPaginator,
) -> None:
    """Пагинация: next ведёт на вторую страницу."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                httpx.codes.OK,
                json=build_page_json(
                    [build_event_json(name="A")],
                    next_url="https://provider.test/api/events/?page=2",
                ),
            )
        return httpx.Response(
            httpx.codes.OK,
            json=build_page_json([build_event_json(name="B")]),
        )

    respx_router.get("/events/").mock(side_effect=handler)

    events = [e async for e in paginator.iter_all_events()]

    assert len(events) == 2
    assert [e.name for e in events] == ["A", "B"]


async def test_iter_all_events_max_pages_raises(
    respx_router: respx.MockRouter,
    paginator: EventsPaginator,
) -> None:
    """Если next зациклится — MAX_PAGES остановит."""
    paginator.MAX_PAGES = 2

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            httpx.codes.OK,
            json=build_page_json(
                [],
                next_url="https://provider.test/api/events/?page=2",
            ),
        )

    respx_router.get("/events/").mock(side_effect=handler)

    with pytest.raises(EventsProviderError, match="Pagination exceeded"):
        _ = [e async for e in paginator.iter_all_events()]


async def test_iter_all_events_rejects_foreign_host(
    respx_router: respx.MockRouter,
    paginator: EventsPaginator,
) -> None:
    """SSRF-защита: next на другом хосте → ошибка."""
    respx_router.get("/events/").mock(
        return_value=httpx.Response(
            httpx.codes.OK,
            json=build_page_json(
                [],
                next_url="https://evil.example.com/events/?page=2",
            ),
        )
    )

    with pytest.raises(EventsProviderError, match="different host"):
        _ = [e async for e in paginator.iter_all_events()]
