from prometheus_client import Counter, Gauge, Histogram

EVENTS_PROVIDER_REQUESTS_TOTAL = Counter(
    "events_provider_requests_total",
    "Total requests to Events Provider API",
    ["endpoint", "status"],
)

EVENTS_PROVIDER_REQUEST_DURATION = Histogram(
    "events_provider_request_duration_seconds",
    "Events Provider API request duration in seconds",
    ["endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

EVENTS_TOTAL = Gauge(
    "events_total",
    "Current number of events in database",
)

TICKETS_CREATED_TOTAL = Gauge(
    "tickets_created_total",
    "Current number of tickets in database",
)

TICKETS_CANCELLED_TOTAL = Gauge(
    "tickets_cancelled_total",
    "Total number of cancelled tickets (counted from outbox audit events)",
)

CACHE_HITS_TOTAL = Counter(
    "cache_hits_total",
    "Seats cache hits",
)

CACHE_MISSES_TOTAL = Counter(
    "cache_misses_total",
    "Seats cache misses",
)
