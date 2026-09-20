import logging
from typing import Any, Self, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .exceptions import (
    APIClientError,
    APIConnectionError,
    APIInvalidResponseError,
)

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)


class BaseAPIClient:
    """Базовый асинхронный HTTP-клиент для внешних API."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Accept": "application/json",
                **(headers or {}),
            },
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        """Закрыть HTTP-клиент. Вызывается при остановке приложения."""
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Выполнить HTTP-запрос, вернуть распарсенный JSON."""
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as e:
            logger.warning("API timeout: %s %s", method, url)
            raise self._connection_error(f"Timeout: {method} {url}") from e
        except httpx.RequestError as e:
            logger.warning("API connection error: %s %s", method, url)
            raise self._connection_error(f"Connection error: {e}") from e

        if response.status_code >= 400:
            raise self._error_from_response(response)

        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except ValueError as e:
            raise self._invalid_response_error(response) from e

    @staticmethod
    def _parse(model: type[TModel], data: dict[str, Any]) -> TModel:
        """Распарсить ответ в Pydantic-модель."""
        try:
            return model.model_validate(data)
        except ValidationError as e:
            raise APIInvalidResponseError(
                message=f"Invalid response format: {e.error_count()} errors"
            ) from e

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Попытаться достать осмысленное сообщение из тела ошибки."""
        try:
            payload = response.json()
        except ValueError:
            return f"HTTP {response.status_code}: {response.text[:200]}"

        if isinstance(payload, dict):
            for key in ("message", "detail", "error"):
                value = payload.get(key)
                if isinstance(value, str):
                    return value

        return f"HTTP {response.status_code}: {payload}"

    def _error_from_response(
        self,
        response: httpx.Response,
    ) -> APIClientError:
        """Построить исключение из ответа с ошибкой."""
        return APIClientError(
            self._extract_error_message(response), status_code=response.status_code
        )

    def _connection_error(self, message: str) -> APIClientError:
        """Построить исключение для сетевой ошибки."""
        return APIConnectionError(message)

    def _invalid_response_error(self, response: httpx.Response) -> APIClientError:
        """Построить исключение для невалидного тела ответа."""
        return APIInvalidResponseError(
            f"Invalid JSON from {response.request.method} {response.request.url}"
        )
