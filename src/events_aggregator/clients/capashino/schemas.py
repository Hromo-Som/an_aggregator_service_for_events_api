from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class SCapashinoNotificationCreate(BaseModel):
    """Тело запроса на создание уведомления в Capashino."""

    message: str = Field(
        min_length=1,
        description="Текст уведомления, не пустой после обрезки пробелов",
    )
    reference_id: UUID = Field(
        description="Идентификатор, с которым связывается уведомление (например, ticket_id)",
    )
    idempotency_key: str = Field(
        description="Уникальный ключ: повторный запрос вернёт то же уведомление",
    )


class SCapashinoNotificationResponse(BaseModel):
    """Ответ Capashino на создание уведомления."""

    id: UUID
    user_id: UUID | None = None
    message: str
    reference_id: UUID
    created_at: AwareDatetime
    idempotency_key: str | None = None
