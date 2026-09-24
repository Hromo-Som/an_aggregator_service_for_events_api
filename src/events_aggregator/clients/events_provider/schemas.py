from uuid import UUID

from pydantic import AwareDatetime, BaseModel, EmailStr, Field

from events_aggregator.enums import EventStatus


class SProviderPlace(BaseModel):
    """Площадка проведения события."""

    id: UUID
    name: str
    city: str
    address: str
    seats_pattern: str = Field(
        ...,
        description='паттерн мест в формате "A1-1000,B1-2000"',
    )
    changed_at: AwareDatetime
    created_at: AwareDatetime


class SProviderEvent(BaseModel):
    """Событие в формате провайдера."""

    id: UUID
    name: str
    place: SProviderPlace
    event_time: AwareDatetime
    registration_deadline: AwareDatetime
    status: EventStatus = Field(
        ...,
        description=(
            '"new" - новое событие, еще не опубликовано, '
            '"published" - опубликовано, доступно для регистрации'
        ),
    )
    number_of_visitors: int
    changed_at: AwareDatetime
    created_at: AwareDatetime
    status_changed_at: AwareDatetime


class SProviderAvailableSeats(BaseModel):
    """Информация о свободных местах."""

    seats: list[str]


class SProviderRegistrationCreate(BaseModel):
    """Тело запроса на регистрацию."""

    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    seat: str = Field(
        ...,
        min_length=1,
        max_length=10,
    )
    email: EmailStr


class SProviderRegistration(BaseModel):
    """Ответ на успешную регистрацию."""

    ticket_id: UUID


class SProviderCancellationResponse(BaseModel):
    """Ответ на отмену регистрации."""

    success: bool


class PaginatedResponse[T: BaseModel](BaseModel):
    """Обёртка пагинации: next / previous / results."""

    next: str | None = None
    previous: str | None = None
    results: list[T]


EventsPage = PaginatedResponse[SProviderEvent]
