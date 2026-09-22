from uuid import UUID

from fastapi import APIRouter, status

from events_aggregator.dependencies import TicketServiceDep
from events_aggregator.schemas.event import (
    SEventCancellationRead,
    SEventRegistrationCreate,
    SEventRegistrationRead,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post(
    "",
    response_model=SEventRegistrationRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: SEventRegistrationCreate,
    service: TicketServiceDep,
) -> SEventRegistrationRead:
    return await service.register(payload)


@router.delete(
    "/{ticket_id}",
    response_model=SEventCancellationRead,
)
async def unregister(
    ticket_id: UUID,
    service: TicketServiceDep,
) -> SEventCancellationRead:
    return await service.unregister(ticket_id)
