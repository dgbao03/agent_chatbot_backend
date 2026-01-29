"""
Workflow context manager for sharing user_id across tools.
This allows tools to access user_id without passing it as parameter.
"""
from contextvars import ContextVar
from typing import Optional

# Context variable to store current user_id
_user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


def set_current_user_id(user_id: str) -> None:
    """Set the current user_id in context."""
    _user_id_var.set(user_id)


def get_current_user_id() -> Optional[str]:
    """Get the current user_id from context."""
    return _user_id_var.get()


def clear_current_user_id() -> None:
    """Clear the current user_id from context."""
    _user_id_var.set(None)

