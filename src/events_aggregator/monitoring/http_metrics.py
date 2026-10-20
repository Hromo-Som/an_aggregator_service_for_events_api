import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Собирает http_requests_total и http_request_duration_seconds."""

    EXCLUDED_PATHS = frozenset(
        {
            "/metrics",
            "/api/health",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        }
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in self.EXCLUDED_PATHS:
            return await call_next(request)

        method = request.method
        started = time.monotonic()

        try:
            response = await call_next(request)
        except Exception:
            self._observe(method, request, 500, started)
            raise

        self._observe(method, request, response.status_code, started)
        return response

    @staticmethod
    def _observe(
        method: str,
        request: Request,
        status_code: int,
        started: float,
    ) -> None:
        endpoint = _resolve_endpoint(request)
        HTTP_REQUESTS_TOTAL.labels(
            method=method, endpoint=endpoint, status=str(status_code)
        ).inc()
        HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(
            time.monotonic() - started
        )


def _resolve_endpoint(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path
