from events_aggregator.clients.exceptions import APIClientError


class CapashinoPermanentError(APIClientError):
    """Ошибка, которую бессмысленно ретраить (4xx, кроме 409)."""
