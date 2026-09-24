from events_aggregator.db.models import EventORM
from events_aggregator.enums import EventStatus
from events_aggregator.schemas.event import SEventDetailRead, SEventRead
from events_aggregator.services.converters import Converter


def test_event_orm_to_read(event_orm: EventORM) -> None:
    result = Converter.event_orm_to_read(event_orm)

    assert isinstance(result, SEventRead)
    assert result.id == event_orm.id
    assert result.name == event_orm.name
    assert result.place.id == event_orm.place_id
    assert result.place.city == event_orm.place_city
    assert result.event_time == event_orm.event_time
    assert result.status == EventStatus.PUBLISHED
    assert result.number_of_visitors == 5


def test_event_orm_to_detail_read(event_orm: EventORM) -> None:
    result = Converter.event_orm_to_detail_read(event_orm)

    assert isinstance(result, SEventDetailRead)
    assert result.place.seats_pattern == "A1-100,B1-50"
    assert result.id == event_orm.id
