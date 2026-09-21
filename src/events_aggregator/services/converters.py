from events_aggregator.db.models import EventORM
from events_aggregator.schemas.event import SEventPlaceRead, SEventRead


def event_orm_to_read(event: EventORM) -> SEventRead:
    """EventORM → SEventRead."""
    return SEventRead(
        id=event.id,
        name=event.name,
        place=SEventPlaceRead(
            id=event.place_id,
            name=event.place_name,
            city=event.place_city,
            address=event.place_address,
        ),
        event_time=event.event_time,
        registration_deadline=event.registration_deadline,
        status=event.status,
        number_of_visitors=event.number_of_visitors,
    )
