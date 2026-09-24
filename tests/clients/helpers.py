from uuid import uuid4


def build_event_json(**overrides) -> dict:
    base = {
        "id": str(uuid4()),
        "name": "Python Conf",
        "place": {
            "id": str(uuid4()),
            "name": "Технопарк",
            "city": "Москва",
            "address": "ул. Ленина, 1",
            "seats_pattern": "A1-100",
            "changed_at": "2026-01-01T00:00:00+00:00",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        "event_time": "2026-09-01T10:00:00+00:00",
        "registration_deadline": "2026-08-31T10:00:00+00:00",
        "status": "published",
        "number_of_visitors": 5,
        "changed_at": "2026-01-01T00:00:00+00:00",
        "created_at": "2026-01-01T00:00:00+00:00",
        "status_changed_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def build_page_json(results: list[dict], next_url: str | None = None) -> dict:
    return {
        "count": len(results),
        "next": next_url,
        "previous": None,
        "results": results,
    }
