"""
Chat history repository - Data access layer for messages.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import Message, Conversation
from app.config.types import Message as MessageDict
from app.auth.context import get_current_user_id


def load_chat_history(conversation_id: str, db: Session) -> List[MessageDict]:
    """
    Load working memory messages from database for a conversation.
    Returns list of messages in working memory, ordered by created_at.
    
    Args:
        conversation_id: UUID of the conversation
        db: Database session
        
    Returns:
        List of Message dicts with all fields populated (id, conversation_id, role, content, etc.)
    """
    try:
        # Get current user for authorization check
        user_id = get_current_user_id()
        
        # Verify conversation belongs to user (security check)
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not conversation:
            return []
        
        # Query messages in working memory for this conversation
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.is_in_working_memory == True
        ).order_by(Message.created_at.asc()).all()
        
        if not messages:
            return []

        # Convert to dict format
        result: List[MessageDict] = []
        for msg in messages:
            result.append(
                {
                    "id": str(msg.id),
                    "conversation_id": str(msg.conversation_id),
                    "role": msg.role,
                    "content": msg.content,
                    "intent": msg.intent,
                    "is_in_working_memory": msg.is_in_working_memory,
                    "summarized_at": msg.summarized_at.isoformat() if msg.summarized_at else None,
                    "metadata": msg.metadata,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
            )
        
        return result
        
    except Exception:
        return []


def save_message(message: MessageDict, db: Session) -> Optional[MessageDict]:
    """
    Save a new message to database.
    
    Args:
        message: Message dict with conversation_id, role, content, intent (optional), metadata (optional)
        db: Database session
        
    Returns:
        Message dict with id and created_at set if successful, None if failed
    """
    try:
        # Create new message
        new_message = Message(
            conversation_id=message["conversation_id"],
            role=message["role"],
            content=message["content"],
            intent=message.get("intent"),
            metadata=message.get("metadata"),
            is_in_working_memory=message.get("is_in_working_memory", True)
        )
        
        db.add(new_message)
        db.commit()
        db.refresh(new_message)
        
        return {
            "id": str(new_message.id),
            "conversation_id": str(new_message.conversation_id),
            "role": new_message.role,
            "content": new_message.content,
            "intent": new_message.intent,
            "is_in_working_memory": new_message.is_in_working_memory,
            "summarized_at": new_message.summarized_at.isoformat() if new_message.summarized_at else None,
            "metadata": new_message.metadata,
            "created_at": new_message.created_at.isoformat() if new_message.created_at else None,
        }
        
    except Exception:
        db.rollback()
        return None

