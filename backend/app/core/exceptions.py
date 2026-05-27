"""Domain exceptions — replace raw ValueError with semantically meaningful errors.

Each exception maps to a specific HTTP status code. The global handler in
main.py catches these and returns clean JSON. Service-layer code raises
these instead of ValueError so the API layer doesn't need try/except blocks.
"""


class ChangebookError(Exception):
    """Base for all domain exceptions."""

    status_code: int = 500
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class NotFoundError(ChangebookError):
    """Resource does not exist."""

    status_code = 404
    detail = "Resource not found."


class ForbiddenError(ChangebookError):
    """User is not allowed to perform this action."""

    status_code = 403
    detail = "You do not have permission to perform this action."


class InvalidTransitionError(ChangebookError):
    """State machine transition is not allowed."""

    status_code = 422
    detail = "Invalid state transition."


class GateError(ChangebookError):
    """A transition gate blocked the operation (missing reviews, incomplete profile, etc.)."""

    status_code = 422
    detail = "Transition blocked by a gate condition."


class ConflictError(ChangebookError):
    """Operation conflicts with current state (duplicate reviewer, already completed, etc.)."""

    status_code = 409
    detail = "Operation conflicts with current state."


class ValidationError(ChangebookError):
    """Input validation failed at the domain level."""

    status_code = 422
    detail = "Validation failed."
