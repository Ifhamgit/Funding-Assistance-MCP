"""Domain errors. Each maps 1:1 to an error code in SPEC §5.3."""

from typing import Any


class DomainError(Exception):
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_envelope(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class Unauthenticated(DomainError):
    code = "UNAUTHENTICATED"


class InvalidInput(DomainError):
    code = "VALIDATION_ERROR"

    def __init__(self, message: str, fields: list[str]):
        super().__init__(message, {"fields": sorted(fields)})


class Forbidden(DomainError):
    code = "FORBIDDEN"


class NotFound(DomainError):
    code = "NOT_FOUND"


class InvalidTransition(DomainError):
    code = "INVALID_TRANSITION"


class InsufficientFunds(DomainError):
    code = "INSUFFICIENT_FUNDS"


class IdempotencyConflict(DomainError):
    code = "IDEMPOTENCY_CONFLICT"
