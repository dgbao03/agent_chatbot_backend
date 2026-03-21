"""
Authentication context - User ID and DB session context management.
"""
from contextvars import ContextVar
from typing import Optional
from sqlalchemy.orm import Session
from app.exceptions import AuthenticationError, DatabaseError

# Context variable for user_id (replaces RLS in self-hosted DB)
_current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)

# Context variable for database session
_current_db_session: ContextVar[Optional[Session]] = ContextVar("current_db_session", default=None)


def set_current_user_id(user_id: str) -> None:
    """
    Set current user ID in context.
    Called by the workflow router before running ChatWorkflow, so that
    LLM-invoked tools (e.g. user_facts tools) can access it via ContextVar.

    Args:
        user_id: UUID of authenticated user
    """
    _current_user_id.set(user_id)


def get_current_user_id() -> Optional[str]:
    """
    Get current user ID from context.
    Used exclusively by LLM-invoked tools (e.g. user_facts tools) that cannot
    receive user_id via dependency injection.

    Returns:
        user_id or None if not authenticated

    Raises:
        AuthenticationError: If no user_id in context (unauthenticated request)
    """
    user_id = _current_user_id.get()
    if not user_id:
        raise AuthenticationError("No authenticated user in context")
    return user_id


def clear_current_user_id() -> None:
    """
    Clear current user ID from context.
    Called after request completes.
    """
    _current_user_id.set(None)


def set_current_db_session(db: Session) -> None:
    """
    Set current database session in context.
    Called by the workflow router before running ChatWorkflow, so that
    LLM-invoked tools (e.g. user_facts tools) can access it via ContextVar.

    Args:
        db: SQLAlchemy database session
    """
    _current_db_session.set(db)


def get_current_db_session() -> Session:
    """
    Get current database session from context.
    Used exclusively by LLM-invoked tools (e.g. user_facts tools) that cannot
    receive db via dependency injection.

    Returns:
        SQLAlchemy Session

    Raises:
        DatabaseError: If no db session in context
    """
    db = _current_db_session.get()
    if not db:
        raise DatabaseError("No database session in context")
    return db


def clear_current_db_session() -> None:
    """
    Clear current database session from context.
    Called after request completes.
    """
    _current_db_session.set(None)
