from uuid import UUID

from pydantic import AwareDatetime, BaseModel, EmailStr, Field


class SEventPlaceRead(BaseModel):
    """Площадка в списке событий."""

    id: UUID
    name: str
    city: str
    address: str


class SEventPlaceDetailRead(SEventPlaceRead):
    """Площадка в деталях события (с seats_pattern)."""

    seats_pattern: str


class SEventRead(BaseModel):
    """Событие в формате нашего API."""

    id: UUID
    name: str
    place: SEventPlaceRead
    event_time: AwareDatetime
    registration_deadline: AwareDatetime
    status: str
    number_of_visitors: int


class SEventDetailRead(SEventRead):
    """Событие в деталях — с расширенной площадкой."""

    place: SEventPlaceDetailRead


class SEventPageRead(BaseModel):
    """Страница событий с пагинацией."""

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[SEventRead]


class SEventSeatsRead(BaseModel):
    """Свободные места."""

    event_id: UUID
    available_seats: list[str]


class SEventRegistrationCreate(BaseModel):
    """Тело запроса на регистрацию."""

    event_id: UUID
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    seat: str = Field(..., min_length=1, max_length=10)


class SEventRegistrationRead(BaseModel):
    """Ответ на регистрацию."""

    ticket_id: UUID


class SEventCancellationRead(BaseModel):
    """Ответ на отмену."""

    success: bool
