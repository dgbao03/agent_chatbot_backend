"""
Internal types for conversation domain.
Used by: chat_repository, conversation_repository, summary_repository, message_service.
"""
from typing import TypedDict, Optional, Literal


class Message(TypedDict, total=False):
    """Message entity - maps to messages table."""
    id: Optional[str]
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    intent: Optional[Literal["PPTX", "GENERAL"]]
    is_in_working_memory: bool
    summarized_at: Optional[str]
    metadata: Optional[dict]
    created_at: Optional[str]


class Conversation(TypedDict, total=False):
    """Conversation entity - maps to conversations table."""
    id: Optional[str]
    user_id: str
    title: Optional[str]
    active_presentation_id: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class SummaryDict(TypedDict):
    """Summary dictionary structure returned from database."""
    summary_content: str
