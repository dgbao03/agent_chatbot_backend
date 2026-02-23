"""
Conversation repository - Data access layer for conversations.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import Conversation
from app.config.types import Conversation as ConversationDict
from app.exceptions import DatabaseError
from app.auth.context import get_current_user_id
from app.logging import get_logger

logger = get_logger(__name__)


def list_conversations(user_id: str, db: Session) -> List[ConversationDict]:
    """
    List all conversations for a user, ordered by updated_at desc.

    Args:
        user_id: UUID of the user
        db: Database session

    Returns:
        List of conversation dicts
    """
    try:
        conversations = (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .all()
        )
        return [
            {
                "id": str(c.id),
                "user_id": str(c.user_id),
                "title": c.title,
                "active_presentation_id": str(c.active_presentation_id) if c.active_presentation_id else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in conversations
        ]
    except Exception:
        logger.exception("list_conversations_failed")
        return []


def get_conversation_by_id(conversation_id: str, user_id: str, db: Session) -> Optional[ConversationDict]:
    """
    Get conversation by ID if it belongs to the user.

    Args:
        conversation_id: UUID of the conversation
        user_id: UUID of the user
        db: Database session

    Returns:
        Conversation dict or None if not found / not owned
    """
    try:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )
        if not conv:
            return None
        return {
            "id": str(conv.id),
            "user_id": str(conv.user_id),
            "title": conv.title,
            "active_presentation_id": str(conv.active_presentation_id) if conv.active_presentation_id else None,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        }
    except Exception:
        logger.exception("get_conversation_by_id_failed")
        return None


def update_conversation(
    conversation_id: str, user_id: str, data: Dict[str, Any], db: Session
) -> Optional[ConversationDict]:
    """
    Update conversation (e.g. title) if it belongs to the user.

    Args:
        conversation_id: UUID of the conversation
        user_id: UUID of the user
        data: Dict with fields to update (title, etc.)
        db: Database session

    Returns:
        Updated conversation dict or None
    """
    try:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )
        if not conv:
            return None
        if "title" in data and data["title"] is not None:
            conv.title = data["title"]
        db.commit()
        db.refresh(conv)
        return {
            "id": str(conv.id),
            "user_id": str(conv.user_id),
            "title": conv.title,
            "active_presentation_id": str(conv.active_presentation_id) if conv.active_presentation_id else None,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        }
    except Exception:
        logger.exception("update_conversation_failed")
        db.rollback()
        return None


def delete_conversation(conversation_id: str, user_id: str, db: Session) -> bool:
    """
    Delete conversation if it belongs to the user. Cascade deletes messages, summaries, presentations.

    Args:
        conversation_id: UUID of the conversation
        user_id: UUID of the user
        db: Database session

    Returns:
        True if deleted, False if not found / not owned
    """
    try:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )
        if not conv:
            return False
        db.delete(conv)
        db.commit()
        return True
    except Exception:
        logger.exception("delete_conversation_failed")
        db.rollback()
        return False


def create_new_conversation(user_id: str, db: Session) -> str:
    """
    Create a new conversation with title = null initially.
    Title will be updated after generation.
    
    Args:
        user_id: UUID of the user
        db: Database session
        
    Returns:
        Conversation ID (UUID string)
        
    Raises:
        DatabaseError: If conversation creation fails
    """
    try:
        conversation = Conversation(
            user_id=user_id,
            title=None
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        return str(conversation.id)
            
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to create conversation: {e}") from e


def update_conversation_title(conversation_id: str, title: str, db: Session) -> bool:
    """
    Update conversation title.
    
    Args:
        conversation_id: UUID of the conversation
        title: Title string to set
        db: Database session
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current user for authorization check
        user_id = get_current_user_id()
        
        # Find conversation with user_id filter (replaces RLS)
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not conversation:
            return False
        
        # Update title
        conversation.title = title
        db.commit()
        
        return True
            
    except Exception:
        logger.exception("update_conversation_title_failed")
        db.rollback()
        return False

