import httpx
import pytest
import respx
from pydantic import BaseModel

from events_aggregator.clients.base import BaseAPIClient
from events_aggregator.clients.events_provider.client import EventsProviderClient
from events_aggregator.clients.exceptions import (
    APIClientError,
    APIConnectionError,
    APIInvalidResponseError,
)
from tests.constants import BASE_URL


async def test_request_get_returns_json(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.get("/events/").mock(
        return_value=httpx.Response(httpx.codes.OK, json={"results": []})
    )

    data = await provider_client._request("GET", "/events/")

    assert data == {"results": []}


async def test_request_post_sends_json(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    route = respx_router.post("/tickets").mock(
        return_value=httpx.Response(httpx.codes.CREATED, json={"ticket_id": "abc"})
    )

    data = await provider_client._request("POST", "/tickets", json={"seat": "A15"})

    assert data == {"ticket_id": "abc"}
    assert route.called
    request = route.calls.last.request
    assert b'"seat":"A15"' in request.content


async def test_request_204_returns_empty_dict(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.delete("/tickets/123").mock(
        return_value=httpx.Response(httpx.codes.NO_CONTENT)
    )

    data = await provider_client._request("DELETE", "/tickets/123")

    assert data == {}


async def test_request_empty_body_returns_empty_dict(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.get("/empty").mock(
        return_value=httpx.Response(httpx.codes.OK, content=b"")
    )

    data = await provider_client._request("GET", "/empty")

    assert data == {}


async def test_request_timeout_raises_connection_error(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.get("/slow").mock(side_effect=httpx.TimeoutException("Timeout"))

    with pytest.raises(APIConnectionError) as exc_info:
        await provider_client._request("GET", "/slow")

    assert "Timeout" in str(exc_info.value)


async def test_request_network_error_raises_connection_error(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.get("/broken").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with pytest.raises(APIConnectionError) as exc_info:
        await provider_client._request("GET", "/broken")

    assert "Connection error" in str(exc_info.value)


async def test_request_4xx_raises_error_from_response(
    respx_router: respx.MockRouter,
) -> None:
    """Базовый клиент на 4xx возвращает APIClientError."""
    base_client = BaseAPIClient(base_url=BASE_URL)

    respx_router.get("/protected").mock(
        return_value=httpx.Response(httpx.codes.FORBIDDEN, json={"detail": "Forbidden"})
    )

    with pytest.raises(APIClientError) as exc_info:
        await base_client._request("GET", "/protected")

    assert exc_info.value.status_code == httpx.codes.FORBIDDEN
    assert "Forbidden" in str(exc_info.value)

    await base_client.aclose()


async def test_request_5xx_raises_error_from_response(
    respx_router: respx.MockRouter,
) -> None:
    base_client = BaseAPIClient(base_url=BASE_URL)

    respx_router.get("/boom").mock(
        return_value=httpx.Response(
            httpx.codes.INTERNAL_SERVER_ERROR,
            text="Internal Error",
        )
    )

    with pytest.raises(APIClientError) as exc_info:
        await base_client._request("GET", "/boom")

    assert exc_info.value.status_code == httpx.codes.INTERNAL_SERVER_ERROR

    await base_client.aclose()


async def test_request_invalid_json_raises_invalid_response(
    respx_router: respx.MockRouter,
    provider_client: EventsProviderClient,
) -> None:
    respx_router.get("/html").mock(
        return_value=httpx.Response(
            httpx.codes.OK,
            content=b"<html>not json</html>",
            headers={"Content-Type": "text/html"},
        )
    )

    with pytest.raises(APIInvalidResponseError):
        await provider_client._request("GET", "/html")


async def test_parse_valid_data() -> None:

    class Model(BaseModel):
        name: str
        count: int

    result = BaseAPIClient._parse(Model, {"name": "x", "count": 5})

    assert result.name == "x"
    assert result.count == 5


async def test_parse_invalid_data_raises() -> None:

    class Model(BaseModel):
        name: str
        count: int

    with pytest.raises(APIInvalidResponseError):
        BaseAPIClient._parse(Model, {"name": "x"})


def test_extract_message_from_detail_field() -> None:
    response = httpx.Response(httpx.codes.BAD_REQUEST, json={"detail": "Bad input"})
    assert BaseAPIClient._extract_error_message(response) == "Bad input"


def test_extract_message_from_message_field() -> None:
    response = httpx.Response(httpx.codes.BAD_REQUEST, json={"message": "Oops"})
    assert BaseAPIClient._extract_error_message(response) == "Oops"


def test_extract_message_fallback_to_raw_json() -> None:
    response = httpx.Response(httpx.codes.BAD_REQUEST, json={"unexpected": "shape"})
    result = BaseAPIClient._extract_error_message(response)
    assert "unexpected" in result


def test_extract_message_non_json() -> None:
    response = httpx.Response(
        httpx.codes.INTERNAL_SERVER_ERROR, text="plain text error"
    )
    result = BaseAPIClient._extract_error_message(response)
    assert "plain text error" in result


async def test_aclose_closes_client() -> None:
    client = BaseAPIClient(base_url=BASE_URL)
    await client.aclose()
    await client.aclose()


async def test_async_context_manager() -> None:
    async with BaseAPIClient(base_url=BASE_URL) as client:
        assert isinstance(client, BaseAPIClient)
