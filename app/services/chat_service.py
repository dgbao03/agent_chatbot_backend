"""
Chat service - Business logic for chat orchestration.
"""
from sqlalchemy.orm import Session
from app.models import Conversation


def validate_conversation_access(user_id: str, conversation_id: str, db: Session) -> None:
    """
    Validate that user has access to the conversation.
    Raises ValueError if access is denied.
    
    Args:
        user_id: UUID of the user
        conversation_id: UUID of the conversation
        db: Database session
        
    Raises:
        ValueError: If conversation not found or user doesn't have access
    """
    try:
        # Query conversation with user_id filter
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found or access denied.")
            
    except ValueError:
        raise
    except Exception:
        raise ValueError("Access denied: Unable to verify conversation ownership.")

