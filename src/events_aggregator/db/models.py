from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from events_aggregator.db.base import Base


class EventORM(Base):
    """Модель события."""

    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), index=True)

    place_id: Mapped[UUID] = mapped_column(index=True)
    place_name: Mapped[str] = mapped_column(String(255))
    place_city: Mapped[str] = mapped_column(String(100), index=True)
    place_address: Mapped[str] = mapped_column(String(500))
    seats_pattern: Mapped[str] = mapped_column(Text)

    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    registration_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    number_of_visitors: Mapped[int] = mapped_column(default=0)

    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    tickets: Mapped[list[TicketORM]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_events_city_event_time", "place_city", "event_time"),)

    def __repr__(self) -> str:
        return f"<EventORM id={self.id} name={self.name!r}>"


class TicketORM(Base):
    """Регистрация (билет) участника."""

    __tablename__ = "tickets"

    ticket_id: Mapped[UUID] = mapped_column(primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255))
    seat: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event: Mapped[EventORM] = relationship(
        back_populates="tickets",
    )

    def __repr__(self) -> str:
        return f"<TicketORM id={self.ticket_id} event={self.event_id}>"


class SyncMetadataORM(Base):
    """Метаданные синхронизации. Всегда одна строка с id=1."""

    __tablename__ = "sync_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    last_sync_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str] = mapped_column(String(20))
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("id = 1", name="ck_sync_metadata_single_row"),)
