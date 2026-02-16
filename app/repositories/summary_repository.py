"""
Summary repository - Data access layer for conversation summaries.
"""
from datetime import datetime, timezone
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import ConversationSummary, Message, Conversation
from app.config.types import SummaryDict
from app.auth.context import get_current_user_id


def load_summary(conversation_id: str, db: Session) -> SummaryDict:
    """
    Load chat summary from database for a conversation.
    Gets the latest version summary.
    
    Args:
        conversation_id: UUID of the conversation
        db: Database session
    
    Returns:
        dict: {"summary_content": str} or {"summary_content": ""} if none
    """
    try:
        # Get current user for authorization check
        user_id = get_current_user_id()
        
        # Verify conversation belongs to user
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not conversation:
            return {"summary_content": ""}
        
        # Query latest summary (highest version)
        summary = db.query(ConversationSummary).filter(
            ConversationSummary.conversation_id == conversation_id
        ).order_by(ConversationSummary.version.desc()).first()
        
        if not summary:
            return {"summary_content": ""}
        
        return {
            "summary_content": summary.summary_content or "",
        }
        
    except Exception:
        return {"summary_content": ""}


def save_summary(conversation_id: str, summary_content: str, db: Session) -> bool:
    """
    Save chat summary to database.
    Creates a new version of the summary.
    
    Args:
        conversation_id: UUID of the conversation
        summary_content: Summary content
        db: Database session
        
    Returns:
        bool: True if successful
    """
    try:
        # Get current max version
        max_version = db.query(func.max(ConversationSummary.version)).filter(
            ConversationSummary.conversation_id == conversation_id
        ).scalar()
        
        new_version = (max_version or 0) + 1
        
        # Create new summary version
        summary = ConversationSummary(
            conversation_id=conversation_id,
            version=new_version,
            summary_content=summary_content
        )
        
        db.add(summary)
        db.commit()
        
        return True
        
    except Exception:
        db.rollback()
        return False


def mark_messages_as_summarized(message_ids: List[str], db: Session) -> bool:
    """
    Mark messages as summarized (is_in_working_memory = False).
    
    Args:
        message_ids: List of message UUIDs to mark
        db: Database session
        
    Returns:
        bool: True if successful
    """
    try:
        # Update messages with current UTC timestamp
        db.query(Message).filter(
            Message.id.in_(message_ids)
        ).update(
            {
                "is_in_working_memory": False,
                "summarized_at": datetime.now(timezone.utc)
            },
            synchronize_session=False
        )
        
        db.commit()
        return True
        
    except Exception:
        db.rollback()
        return False

