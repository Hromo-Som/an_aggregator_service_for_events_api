from uuid import UUID

from pydantic import AwareDatetime, BaseModel


class SEventPlaceRead(BaseModel):
    """Площадка в списке событий."""

    id: UUID
    name: str
    city: str
    address: str


class SEventRead(BaseModel):
    """Событие в формате нашего API."""

    id: UUID
    name: str
    place: SEventPlaceRead
    event_time: AwareDatetime
    registration_deadline: AwareDatetime
    status: str
    number_of_visitors: int


class SEventPageRead(BaseModel):
    """Страница событий с пагинацией."""

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[SEventRead]
