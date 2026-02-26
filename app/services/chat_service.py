"""
Chat service - Business logic for chat orchestration.
"""
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models import Conversation
from app.repositories.conversation_repository import (
    create_new_conversation,
    update_conversation_title,
)
from app.utils.title_generator import generate_conversation_title
from app.exceptions import NotFoundError, AccessDeniedError
from app.logging import get_logger

logger = get_logger(__name__)


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
