import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar
from uuid import UUID

import httpx

from events_aggregator.clients.base import BaseAPIClient
from events_aggregator.monitoring.metrics import (
    EVENTS_PROVIDER_REQUEST_DURATION,
    EVENTS_PROVIDER_REQUESTS_TOTAL,
)

from .exceptions import (
    EventsProviderError,
    ProviderAuthError,
    ProviderBadRequest,
    ProviderNotFound,
    ProviderRateLimited,
    ProviderServerError,
)
from .schemas import (
    EventsPage,
    SProviderAvailableSeats,
    SProviderCancellationResponse,
    SProviderRegistration,
    SProviderRegistrationCreate,
)

T = TypeVar("T")


def _track(
    endpoint: str,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Обернуть метод клиента: записать запрос и длительность в метрики."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            started = time.monotonic()
            status = "error"
            try:
                result = await func(*args, **kwargs)
                status = "200"
                return result
            except EventsProviderError as exc:
                if exc.status_code is not None:
                    status = str(exc.status_code)
                raise
            finally:
                EVENTS_PROVIDER_REQUESTS_TOTAL.labels(
                    endpoint=endpoint, status=status
                ).inc()
                EVENTS_PROVIDER_REQUEST_DURATION.labels(endpoint=endpoint).observe(
                    time.monotonic() - started
                )

        return wrapper

    return decorator


class EventsProviderClient(BaseAPIClient):
    """Асинхронный клиент для Events Provider API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            headers={"x-api-key": f"{api_key}"},
            timeout=timeout,
        )

    @property
    def base_url(self) -> str:
        """Публичный доступ к base_url (для пагинатора)."""
        return self._base_url

    @_track("/events")
    async def get_events_page(self, url: str) -> EventsPage:
        """Получить конкретную страницу по URL (для пагинатора)."""
        data = await self._request("GET", url)
        return self._parse(EventsPage, data)

    @_track("/events")
    async def get_events_list(
        self,
        changed_at: str | None = None,
    ) -> EventsPage:
        """Получить страницу событий с пагинацией."""
        params: dict[str, str] = {}
        if changed_at is not None:
            params["changed_at"] = changed_at

        data = await self._request("GET", "/events/", params=params)

        return self._parse(EventsPage, data)

    @_track("/seats")
    async def get_available_seats(
        self,
        event_id: UUID,
    ) -> SProviderAvailableSeats:
        """Получить список свободных мест на событие."""
        data = await self._request("GET", f"/events/{event_id}/seats/")
        return self._parse(SProviderAvailableSeats, data)

    @_track("/registration")
    async def register(
        self,
        event_id: UUID,
        payload: SProviderRegistrationCreate,
    ) -> SProviderRegistration:
        """Зарегистрировать участника на событие."""
        data = await self._request(
            "POST",
            f"/events/{event_id}/register/",
            json=payload.model_dump(mode="json"),
        )
        return self._parse(SProviderRegistration, data)

    @_track("/registration")
    async def unregister(
        self,
        event_id: UUID,
        ticket_id: UUID,
    ) -> SProviderCancellationResponse:
        """Отменить регистрацию участника на событие."""
        data = await self._request(
            "DELETE",
            f"/events/{event_id}/unregister/",
            json={"ticket_id": str(ticket_id)},
        )
        return self._parse(SProviderCancellationResponse, data)

    def _error_from_response(self, response: httpx.Response) -> EventsProviderError:
        status = response.status_code
        message = self._extract_error_message(response)

        if status == httpx.codes.BAD_REQUEST:
            return ProviderBadRequest(message=message, status_code=status)
        if status == httpx.codes.UNAUTHORIZED:
            return ProviderAuthError(message=message, status_code=status)
        if status == httpx.codes.NOT_FOUND:
            return ProviderNotFound(message=message, status_code=status)
        if status == httpx.codes.TOO_MANY_REQUESTS:
            retry_after = response.headers.get("Retry-After")
            return ProviderRateLimited(
                message=message,
                retry_after=float(retry_after) if retry_after else None,
            )
        if status == httpx.codes.INTERNAL_SERVER_ERROR:
            return ProviderServerError(message=message, status_code=status)

        return EventsProviderError(message=message, status_code=status)
