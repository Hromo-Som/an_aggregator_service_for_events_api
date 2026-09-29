from collections.abc import Iterator
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from events_aggregator.clients.capashino.client import CapashinoClient
from events_aggregator.clients.capashino.exceptions import CapashinoPermanentError
from events_aggregator.clients.exceptions import APIClientError

CAPASHINO_BASE_URL = "https://capashino.test"
CAPASHINO_API_KEY = "test-capashino-key"


@pytest.fixture
def capashino_client() -> CapashinoClient:
    """Клиент Capashino на тестовом base_url."""
    return CapashinoClient(
        base_url=CAPASHINO_BASE_URL,
        api_key=CAPASHINO_API_KEY,
        timeout=1.0,
    )


@pytest.fixture
def capashino_router() -> Iterator[respx.MockRouter]:
    """Отдельный respx-мок для Capashino (не пересекается с провайдером)."""
    with respx.mock(
        base_url=CAPASHINO_BASE_URL,
        assert_all_called=False,
    ) as router:
        yield router


def _response_body(notification_id: UUID | None = None) -> dict:
    return {
        "id": str(notification_id or uuid4()),
        "user_id": str(uuid4()),
        "message": "Вы успешно зарегистрированы",
        "reference_id": str(uuid4()),
        "created_at": "2026-09-29T10:00:00+00:00",
        "idempotency_key": "test-key",
    }


async def test_send_notification_success(
    capashino_router: respx.MockRouter,
    capashino_client: CapashinoClient,
) -> None:
    """201 → парсит ответ, возвращает SCapashinoNotificationResponse."""
    notification_id = uuid4()
    capashino_router.post("/api/notifications").mock(
        return_value=httpx.Response(
            httpx.codes.CREATED,
            json=_response_body(notification_id),
        )
    )

    result = await capashino_client.send_notification(
        message="Вы успешно зарегистрированы на Python Conf",
        reference_id=uuid4(),
        idempotency_key="test-key-abc",
    )

    assert result.id == notification_id
    assert result.idempotency_key == "test-key"


async def test_send_notification_sends_correct_body(
    capashino_router: respx.MockRouter,
    capashino_client: CapashinoClient,
) -> None:
    """В теле — message, reference_id, idempotency_key."""
    route = capashino_router.post("/api/notifications").mock(
        return_value=httpx.Response(
            httpx.codes.CREATED,
            json=_response_body(),
        )
    )

    reference_id = uuid4()
    await capashino_client.send_notification(
        message="Test message",
        reference_id=reference_id,
        idempotency_key="key-abc",
    )

    request = route.calls.last.request
    body = request.read().decode()

    assert '"message":"Test message"' in body
    assert f'"reference_id":"{reference_id}"' in body
    assert '"idempotency_key":"key-abc"' in body


async def test_send_notification_sends_api_key_header(
    capashino_router: respx.MockRouter,
    capashino_client: CapashinoClient,
) -> None:
    """Заголовок X-API-Key передаётся."""
    route = capashino_router.post("/api/notifications").mock(
        return_value=httpx.Response(
            httpx.codes.CREATED,
            json=_response_body(),
        )
    )

    await capashino_client.send_notification(
        message="Test",
        reference_id=uuid4(),
        idempotency_key="k",
    )

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == CAPASHINO_API_KEY


@pytest.mark.parametrize(
    "status",
    [
        httpx.codes.BAD_REQUEST,
        httpx.codes.UNAUTHORIZED,
        httpx.codes.FORBIDDEN,
        httpx.codes.UNPROCESSABLE_ENTITY,
    ],
)
async def test_send_notification_permanent_error(
    capashino_router: respx.MockRouter,
    capashino_client: CapashinoClient,
    status: int,
) -> None:
    """4xx (кроме 409) → CapashinoPermanentError."""
    capashino_router.post("/api/notifications").mock(
        return_value=httpx.Response(status, json={"detail": "error"})
    )

    with pytest.raises(CapashinoPermanentError) as exc_info:
        await capashino_client.send_notification(
            message="Test",
            reference_id=uuid4(),
            idempotency_key="k",
        )

    assert exc_info.value.status_code == status


async def test_send_notification_conflict_is_not_permanent(
    capashino_router: respx.MockRouter,
    capashino_client: CapashinoClient,
) -> None:
    """409 → обычный APIClientError, не CapashinoPermanentError."""
    capashino_router.post("/api/notifications").mock(
        return_value=httpx.Response(
            httpx.codes.CONFLICT,
            json={"detail": "idempotency conflict"},
        )
    )

    with pytest.raises(APIClientError) as exc_info:
        await capashino_client.send_notification(
            message="Test",
            reference_id=uuid4(),
            idempotency_key="k",
        )

    assert exc_info.value.status_code == httpx.codes.CONFLICT
    assert not isinstance(exc_info.value, CapashinoPermanentError)


@pytest.mark.parametrize(
    "status",
    [
        httpx.codes.INTERNAL_SERVER_ERROR,
        httpx.codes.BAD_GATEWAY,
        httpx.codes.SERVICE_UNAVAILABLE,
    ],
)
async def test_send_notification_server_error(
    capashino_router: respx.MockRouter,
    capashino_client: CapashinoClient,
    status: int,
) -> None:
    """5xx → APIClientError (не permanent), воркер будет ретраить."""
    capashino_router.post("/api/notifications").mock(
        return_value=httpx.Response(status, text="Server error")
    )

    with pytest.raises(APIClientError) as exc_info:
        await capashino_client.send_notification(
            message="Test",
            reference_id=uuid4(),
            idempotency_key="k",
        )

    assert exc_info.value.status_code == status
    assert not isinstance(exc_info.value, CapashinoPermanentError)
