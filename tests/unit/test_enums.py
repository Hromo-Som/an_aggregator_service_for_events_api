from events_aggregator.enums import EventStatus


def test_event_status_known_values() -> None:
    assert EventStatus("published") is EventStatus.PUBLISHED
    assert EventStatus("new") is EventStatus.NEW
    assert EventStatus("finished") is EventStatus.FINISHED


def test_event_status_unknown_becomes_unknown() -> None:
    assert EventStatus("cancelled") is EventStatus.UNKNOWN
    assert EventStatus("totally-new-status") is EventStatus.UNKNOWN


def test_event_status_str_comparison() -> None:
    assert EventStatus.PUBLISHED == "published"
    assert "published" == EventStatus.PUBLISHED
