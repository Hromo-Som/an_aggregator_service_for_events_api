class APIClientError(Exception):
    """Базовая ошибка HTTP-клиента."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class APIConnectionError(APIClientError):
    """Сетевая ошибка: таймаут, DNS, соединение разорвано."""


class APIInvalidResponseError(APIClientError):
    """Ответ не является валидным JSON или не соответствует схеме."""
