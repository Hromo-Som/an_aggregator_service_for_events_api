from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.db.models import TicketORM


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(
        self,
        ticket: TicketORM,
    ) -> TicketORM:
        self._session.add(ticket)
        return ticket

    async def get_by_id(self, ticket_id: UUID) -> TicketORM | None:
        return await self._session.get(TicketORM, ticket_id)

    async def delete(self, ticket: TicketORM) -> None:
        await self._session.delete(ticket)
        await self._session.commit()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(TicketORM)
        result = await self._session.execute(stmt)
        return result.scalar_one()
