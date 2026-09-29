from uuid import UUID

from httpx import Response, codes

from events_aggregator.clients.base import BaseAPIClient
from events_aggregator.clients.capashino.exceptions import CapashinoPermanentError
from events_aggregator.clients.capashino.schemas import (
    SCapashinoNotificationCreate,
    SCapashinoNotificationResponse,
)
from events_aggregator.clients.exceptions import APIClientError


class CapashinoClient(BaseAPIClient):
    """Клиент Notification-сервиса Capashino."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
    ) -> None:
        super().__init__(
            base_url,
            headers={"X-API-Key": api_key},
            timeout=timeout,
        )

    async def send_notification(
        self,
        *,
        message: str,
        reference_id: UUID,
        idempotency_key: str,
    ) -> SCapashinoNotificationResponse:
        """Создать уведомление в Capashino."""
        payload = SCapashinoNotificationCreate(
            message=message,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )
        data = await self._request(
            "POST",
            "/api/notifications",
            json=payload.model_dump(mode="json"),
        )
        return self._parse(SCapashinoNotificationResponse, data)

    def _error_from_response(self, response: Response) -> APIClientError:
        status = response.status_code
        message = self._extract_error_message(response)

        if status in (
            codes.BAD_REQUEST,
            codes.UNAUTHORIZED,
            codes.FORBIDDEN,
            codes.UNPROCESSABLE_ENTITY,
        ):
            return CapashinoPermanentError(
                f"Capashino rejected request: {message}",
                status_code=status,
            )

        if status == codes.CONFLICT:
            return APIClientError(
                f"Capashino idempotency conflict: {message}",
                status_code=status,
            )

        return APIClientError(
            f"Capashino temporary error: {message}",
            status_code=status,
        )
