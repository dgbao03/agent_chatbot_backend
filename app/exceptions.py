"""
Custom Exception Hierarchy for Agent Chat Backend.

All application-specific exceptions inherit from AppException.
This enables:
  - Distinguishing "safe to show client" errors (AppException) from unexpected system errors (Exception)
  - Granular error handling at the router/workflow level
  - Consistent logging with proper error context

Usage:
    from app.exceptions import NotFoundError, AccessDeniedError

    raise NotFoundError("Conversation", conversation_id)
    raise AccessDeniedError("Unable to verify ownership") from original_error
"""


class AppException(Exception):
    """
    Base exception for all application-level errors.
    
    The `message` attribute is safe to return to the client.
    Unexpected/internal errors should remain as plain Exception
    and be caught separately at the router layer.
    """

    def __init__(self, message: str = "An unexpected error occurred"):
        self.message = message
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found (conversation, presentation, user, etc.)."""

    def __init__(self, resource: str, resource_id: str = ""):
        detail = f"{resource} not found" + (f": {resource_id}" if resource_id else "")
        super().__init__(detail)


class AccessDeniedError(AppException):
    """User does not have permission to access the requested resource."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message)


class ValidationError(AppException):
    """Input data failed validation (bad format, missing fields, etc.)."""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message)


class LLMError(AppException):
    """LLM-related failure (timeout, output parsing, quota exceeded, etc.)."""

    def __init__(self, message: str = "LLM processing failed"):
        super().__init__(message)


class DatabaseError(AppException):
    """Database operation failure (connection, query, transaction, etc.)."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message)


class ExternalServiceError(AppException):
    """Failure from an external service (third-party API, SMTP, etc.)."""

    def __init__(self, service: str, message: str = ""):
        detail = f"{service} error" + (f": {message}" if message else "")
        super().__init__(detail)
