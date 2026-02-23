"""
Chat service - Business logic for chat orchestration.
"""
from sqlalchemy.orm import Session
from app.models import Conversation
from app.exceptions import NotFoundError, AccessDeniedError


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

