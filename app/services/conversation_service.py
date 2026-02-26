"""
Conversation service - Business logic for conversation management.

Centralizes all conversation-related business logic:
- CRUD operations (wrapping repository calls)
- Ownership validation
- Conversation creation with title generation
"""
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session

from app.models import Conversation
from app.repositories.conversation_repository import (
    create_new_conversation,
    update_conversation_title,
    list_conversations as repo_list_conversations,
    get_conversation_by_id,
    update_conversation as repo_update_conversation,
    delete_conversation as repo_delete_conversation,
)
from app.repositories.chat_repository import load_all_messages_for_conversation
from app.repositories.presentation_repository import get_active_presentation as repo_get_active_presentation
from app.utils.title_generator import generate_conversation_title
from app.exceptions import NotFoundError, AccessDeniedError
from app.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Ownership / access helpers
# ---------------------------------------------------------------------------

def validate_conversation_access(user_id: str, conversation_id: str, db: Session) -> None:
    """
    Validate that user has access to the conversation.

    Args:
        user_id: UUID of the user
        conversation_id: UUID of the conversation
        db: Database session

    Raises:
        NotFoundError: If conversation not found or user doesn't own it
        AccessDeniedError: If ownership check fails due to unexpected error
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()

        if not conversation:
            raise NotFoundError("Conversation", conversation_id)

    except NotFoundError:
        raise
    except Exception as e:
        raise AccessDeniedError("Unable to verify conversation ownership") from e


def get_or_create_conversation(
    user_id: str,
    conversation_id: Optional[str],
    user_input: str,
    db: Session,
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Get an existing conversation (validating ownership) or create a new one.

    If conversation_id is absent/null/"null", a new conversation is created and
    its title is generated from the user's input. Otherwise, ownership is
    verified via validate_conversation_access.

    Args:
        user_id: UUID of the authenticated user
        conversation_id: Existing conversation UUID, or None / "" / "null"
        user_input: User's message text (used for title generation on new convs)
        db: Database session

    Returns:
        Tuple of (conversation_id, new_conv_id_if_created, title_if_created)
        - new_conv_id_if_created is None when the conversation already existed
        - title_if_created is None when the conversation already existed

    Raises:
        DatabaseError: If creating a new conversation fails
        NotFoundError: If existing conversation is not found or not owned
        AccessDeniedError: If ownership check fails unexpectedly
    """
    is_new = not conversation_id or conversation_id == "null" or conversation_id == ""

    if is_new:
        conversation_id = create_new_conversation(user_id, db)

        try:
            title = generate_conversation_title(user_input)
            update_conversation_title(conversation_id, title, db)
        except Exception:
            title = user_input[:60].strip()
            if len(user_input) > 60:
                title += "..."
            update_conversation_title(conversation_id, title, db)

        logger.info("conversation_created", conversation_id=conversation_id, title=title)
        return conversation_id, conversation_id, title

    else:
        validate_conversation_access(user_id, conversation_id, db)
        return conversation_id, None, None


# ---------------------------------------------------------------------------
# CRUD — used by routers/conversations.py
# ---------------------------------------------------------------------------

def list_conversations(user_id: str, db: Session) -> list:
    """
    List all conversations for a user, ordered by updated_at desc.

    Raises:
        DatabaseError: On DB failure (propagated from repository)
    """
    return repo_list_conversations(user_id, db)


def check_conversation_exists(conversation_id: str, user_id: str, db: Session) -> bool:
    """Return True if the conversation exists and belongs to the user."""
    conv = get_conversation_by_id(conversation_id, user_id, db)
    return conv is not None


def get_conversation(conversation_id: str, user_id: str, db: Session) -> dict:
    """
    Get conversation by ID.

    Raises:
        NotFoundError: If conversation not found or not owned by user
        DatabaseError: On DB failure (propagated from repository)
    """
    conv = get_conversation_by_id(conversation_id, user_id, db)
    if conv is None:
        raise NotFoundError("Conversation", conversation_id)
    return conv


def update_conversation(
    conversation_id: str, user_id: str, data: Dict[str, Any], db: Session
) -> dict:
    """
    Update conversation fields (e.g. title).

    Raises:
        NotFoundError: If conversation not found or not owned by user
        DatabaseError: On DB failure (propagated from repository)
    """
    conv = repo_update_conversation(conversation_id, user_id, data, db)
    if conv is None:
        raise NotFoundError("Conversation", conversation_id)
    return conv


def delete_conversation(conversation_id: str, user_id: str, db: Session) -> None:
    """
    Delete conversation if it belongs to the user.

    Raises:
        NotFoundError: If conversation not found or not owned by user
        DatabaseError: On DB failure (propagated from repository)
    """
    deleted = repo_delete_conversation(conversation_id, user_id, db)
    if not deleted:
        raise NotFoundError("Conversation", conversation_id)


def get_messages(conversation_id: str, user_id: str, db: Session) -> list:
    """
    Get all messages in a conversation (including summarized).

    Raises:
        DatabaseError: On DB failure (propagated from repository)
    """
    return load_all_messages_for_conversation(conversation_id, user_id, db)


def get_active_presentation(conversation_id: str, user_id: str, db: Session) -> Optional[str]:
    """
    Get active presentation ID for a conversation.

    Returns None if no active presentation exists.
    """
    return repo_get_active_presentation(conversation_id, db, user_id=user_id)
