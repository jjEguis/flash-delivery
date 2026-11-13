"""Errores de dominio tipados; la capa HTTP los traduce a códigos estables."""


class DomainError(Exception):
    status = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class ValidationError(DomainError):
    status = 400
    code = "INVALID_INPUT"


class UnauthorizedError(DomainError):
    status = 401
    code = "UNAUTHORIZED"


class ForbiddenError(DomainError):
    status = 403
    code = "FORBIDDEN"


class NotFoundError(DomainError):
    status = 404
    code = "NOT_FOUND"


class ConflictError(DomainError):
    status = 409
    code = "CONFLICT"


class DependencyUnavailableError(DomainError):
    status = 503
    code = "DEPENDENCY_UNAVAILABLE"
