from uuid import uuid4

import httpx
import pytest
import respx

from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.clients.events_provider.exceptions import (
    ProviderAuthError,
    ProviderBadRequest,
    ProviderNotFound,
    ProviderRateLimited,
    ProviderServerError,
)
from events_aggregator.clients.events_provider.schemas import (
    SProviderRegistrationCreate,
)
from tests.clients.helpers import build_event_json, build_page_json
from tests.constants import EVENT_ID, TICKET_ID


async def test_get_events_list_success(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.get("/events/").mock(
        return_value=httpx.Response(
            httpx.codes.OK,
            json=build_page_json([build_event_json()]),
        )
    )

    page = await provider_client.get_events_list()

    assert len(page.results) == 1
    assert page.results[0].name == "Python Conf"


async def test_get_events_list_passes_changed_at(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    route = respx_router.get("/events/").mock(
        return_value=httpx.Response(httpx.codes.OK, json=build_page_json([]))
    )

    await provider_client.get_events_list(changed_at="2026-01-01")

    request = route.calls.last.request
    assert request.url.params["changed_at"] == "2026-01-01"


async def test_get_available_seats_success(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.get(f"/events/{EVENT_ID}/seats/").mock(
        return_value=httpx.Response(httpx.codes.OK, json={"seats": ["A1", "A2"]})
    )

    result = await provider_client.get_available_seats(EVENT_ID)

    assert result.seats == ["A1", "A2"]


async def test_register_success(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    ticket_id = uuid4()
    route = respx_router.post(f"/events/{EVENT_ID}/register/").mock(
        return_value=httpx.Response(httpx.codes.OK, json={"ticket_id": str(ticket_id)})
    )

    payload = SProviderRegistrationCreate(
        first_name="Ivan",
        last_name="Ivanov",
        email="ivan@example.com",
        seat="A15",
    )

    result = await provider_client.register(EVENT_ID, payload)

    assert result.ticket_id == ticket_id
    request = route.calls.last.request
    assert b'"first_name":"Ivan"' in request.content
    assert b'"seat":"A15"' in request.content


async def test_unregister_success(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    route = respx_router.delete(f"/events/{EVENT_ID}/unregister/").mock(
        return_value=httpx.Response(httpx.codes.OK, json={"success": True})
    )

    result = await provider_client.unregister(EVENT_ID, TICKET_ID)

    assert result.success is True
    request = route.calls.last.request
    assert str(TICKET_ID).encode() in request.content


@pytest.mark.parametrize(
    "status,expected_exception",
    [
        (httpx.codes.BAD_REQUEST, ProviderBadRequest),
        (httpx.codes.UNAUTHORIZED, ProviderAuthError),
        (httpx.codes.NOT_FOUND, ProviderNotFound),
        (httpx.codes.TOO_MANY_REQUESTS, ProviderRateLimited),
        (httpx.codes.INTERNAL_SERVER_ERROR, ProviderServerError),
    ],
)
async def test_error_mapping(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
    status: int,
    expected_exception: type,
) -> None:
    respx_router.get("/probe").mock(
        return_value=httpx.Response(status, json={"detail": "err"})
    )

    with pytest.raises(expected_exception):
        await provider_client._request("GET", "/probe")


async def test_error_429_retry_after(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.get("/limited").mock(
        return_value=httpx.Response(
            httpx.codes.TOO_MANY_REQUESTS,
            json={"detail": "Rate limited"},
            headers={"Retry-After": "30"},
        )
    )

    with pytest.raises(ProviderRateLimited) as exc_info:
        await provider_client._request("GET", "/limited")

    assert exc_info.value.retry_after == 30.0
