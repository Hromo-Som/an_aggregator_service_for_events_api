class EventsProviderError(Exception):
    """Базовая ошибка при работе с Events Provider API."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProviderNotFound(EventsProviderError):
    """Ресурс не найден (404)."""


class ProviderAuthError(EventsProviderError):
    """Проблема с аутентификацией (401)."""


class ProviderBadRequest(EventsProviderError):
    """Невалидный запрос (400)."""


class ProviderRateLimited(EventsProviderError):
    """Превышен лимит запросов (429)."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ProviderServerError(EventsProviderError):
    """Внутренняя ошибка сервера (500)."""
