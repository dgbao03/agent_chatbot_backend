"""
Message Service - Business logic for saving chat messages.

Provides thin wrappers around the chat repository so that workflow steps
call a named, intentional operation rather than constructing raw dicts.
"""
from typing import Optional

from app.config.types import Message
from app.repositories.chat_repository import save_message


def save_user_message(conversation_id: str, content: str, db) -> Optional[str]:
    """
    Persist a user message and return its database ID.

    Args:
        conversation_id: UUID of the conversation
        content: User's message text
        db: Database session

    Returns:
        Message UUID string if saved successfully, None otherwise
    """
    message: Message = {
        "conversation_id": conversation_id,
        "role": "user",
        "content": content,
        "intent": None,
        "metadata": {},
    }
    saved = save_message(message, db)
    return saved["id"] if saved else None


def save_assistant_message(
    conversation_id: str,
    content: str,
    intent: str,
    metadata: dict,
    db,
) -> Optional[str]:
    """
    Persist an assistant message and return its database ID.

    Args:
        conversation_id: UUID of the conversation
        content: Assistant's response text
        intent: Detected intent label (e.g. "GENERAL", "PPTX")
        metadata: Arbitrary metadata dict (pages, slide_id, security flags, etc.)
        db: Database session

    Returns:
        Message UUID string if saved successfully, None otherwise
    """
    message: Message = {
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": content,
        "intent": intent,
        "metadata": metadata,
    }
    saved = save_message(message, db)
    return saved["id"] if saved else None
