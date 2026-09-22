from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.db.models import TicketORM


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        ticket_id: UUID,
        event_id: UUID,
        first_name: str,
        last_name: str,
        email: str,
        seat: str,
    ) -> TicketORM:
        ticket = TicketORM(
            ticket_id=ticket_id,
            event_id=event_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            seat=seat,
            created_at=datetime.now(UTC),
        )
        self._session.add(ticket)
        await self._session.commit()
        await self._session.refresh(ticket)
        return ticket

    async def get_by_id(self, ticket_id: UUID) -> TicketORM | None:
        return await self._session.get(TicketORM, ticket_id)

    async def delete(self, ticket: TicketORM) -> None:
        await self._session.delete(ticket)
        await self._session.commit()
