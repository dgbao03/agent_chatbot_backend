"""
Workflow context manager for sharing user_id and JWT token across tools.
This allows tools to access user_id and JWT without passing them as parameters.
"""
from contextvars import ContextVar
from typing import Optional

# Context variable to store current user_id
_user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)

# Context variable to store current JWT token
_jwt_token_var: ContextVar[Optional[str]] = ContextVar('jwt_token', default=None)


def set_current_user_id(user_id: str) -> None:
    """Set the current user_id in context."""
    _user_id_var.set(user_id)


def get_current_user_id() -> Optional[str]:
    """Get the current user_id from context."""
    return _user_id_var.get()


def clear_current_user_id() -> None:
    """Clear the current user_id from context."""
    _user_id_var.set(None)


def set_current_jwt_token(jwt_token: str) -> None:
    """Set the current JWT token in context."""
    _jwt_token_var.set(jwt_token)


def get_current_jwt_token() -> Optional[str]:
    """Get the current JWT token from context."""
    return _jwt_token_var.get()


def clear_current_jwt_token() -> None:
    """Clear the current JWT token from context."""
    _jwt_token_var.set(None)

