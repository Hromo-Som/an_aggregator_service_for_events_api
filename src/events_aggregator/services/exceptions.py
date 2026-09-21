class DomainError(Exception):
    """Базовая доменная ошибка."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EventNotFound(DomainError):
    """Событие не найдено."""


class RegistrationNotFound(DomainError):
    """Регистрация не найдена."""


class NoAvailableSeats(DomainError):
    """Свободных мест нет."""


class SeatAlreadyTaken(DomainError):
    """Место уже занято."""


class RegistrationDeadlinePassed(DomainError):
    """Дедлайн регистрации прошёл."""


class EventNotPublished(DomainError):
    """Событие ещё не опубликовано."""
