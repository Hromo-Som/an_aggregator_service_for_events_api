from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from events_aggregator.clients.events_provider.exceptions import (
    ProviderBadRequest,
    ProviderNotFound,
    ProviderRateLimited,
)
from events_aggregator.clients.exceptions import APIClientError
from events_aggregator.services.exceptions import (
    DomainError,
    EventNotFound,
    NoAvailableSeats,
    RegistrationDeadlinePassed,
    RegistrationNotFound,
    SeatAlreadyTaken,
)

_STATUS_MAP: dict[type[DomainError], int] = {
    EventNotFound: status.HTTP_404_NOT_FOUND,
    RegistrationNotFound: status.HTTP_404_NOT_FOUND,
    NoAvailableSeats: status.HTTP_400_BAD_REQUEST,
    SeatAlreadyTaken: status.HTTP_400_BAD_REQUEST,
    RegistrationDeadlinePassed: status.HTTP_400_BAD_REQUEST,
}


async def provider_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, ProviderBadRequest):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message},
        )
    if isinstance(exc, ProviderNotFound):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message},
        )
    if isinstance(exc, ProviderRateLimited):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": exc.message},
            headers={"Retry-After": str(exc.retry_after or 60)},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Превратить доменную ошибку в HTTP-ответ."""
    http_status = _STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return JSONResponse(
        status_code=http_status,
        content={"detail": exc.message},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Зарегистрировать все обработчики."""
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(APIClientError, provider_error_handler)
