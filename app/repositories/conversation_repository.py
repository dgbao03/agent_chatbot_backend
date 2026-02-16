"""
Conversation repository - Data access layer for conversations.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Conversation
from app.auth.context import get_current_user_id


def create_new_conversation(user_id: str, db: Session) -> str:
    """
    Tạo conversation mới với title = null ban đầu.
    Title sẽ được update sau khi generate.
    
    Args:
        user_id: UUID of the user
        db: Database session
        
    Returns:
        Conversation ID (UUID string)
        
    Raises:
        ValueError: If conversation creation fails
    """
    try:
        # Create new conversation
        conversation = Conversation(
            user_id=user_id,
            title=None  # Sẽ update sau
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        return str(conversation.id)
            
    except Exception as e:
        db.rollback()
        raise ValueError(f"Failed to create conversation: {e}")


def update_conversation_title(conversation_id: str, title: str, db: Session) -> bool:
    """
    Update title của conversation.
    
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
        db.rollback()
        return False

