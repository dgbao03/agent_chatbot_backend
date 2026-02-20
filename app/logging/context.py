"""
Logging context - ContextVar management for request-scoped logging data.
Follows the same pattern as app/auth/context.py.
"""
from contextvars import ContextVar
from typing import Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> Optional[str]:
    return _request_id.get()


def clear_request_id() -> None:
    _request_id.set(None)


def set_user_id(user_id: str) -> None:
    _user_id.set(user_id)


def get_user_id() -> Optional[str]:
    return _user_id.get()


def clear_user_id() -> None:
    _user_id.set(None)
