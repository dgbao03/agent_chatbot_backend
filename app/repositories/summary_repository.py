"""
Summary repository - Data access layer for conversation summaries.
"""
from datetime import datetime, timezone
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.models import ConversationSummary, Message, Conversation
from app.types.internal.conversation import SummaryDict
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


def load_summary(conversation_id: str, user_id: str, db: Session) -> SummaryDict:
    """
    Load chat summary from database for a conversation.
    
    Args:
        conversation_id: UUID of the conversation
        user_id: UUID of the user (for ownership check)
        db: Database session
    
    Returns:
        dict: {"summary_content": str} or {"summary_content": ""} if none
    """
    try:
        # Verify conversation belongs to user
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not conversation:
            return {"summary_content": ""}
        
        # Query summary (1 row per conversation)
        summary = db.query(ConversationSummary).filter(
            ConversationSummary.conversation_id == conversation_id
        ).first()
        
        if not summary:
            return {"summary_content": ""}
        
        return {
            "summary_content": summary.summary_content or "",
        }
        
    except Exception as e:
        logger.exception("load_summary_failed")
        raise DatabaseError(f"Failed to load summary: {e}") from e


def save_summary(conversation_id: str, summary_content: str, db: Session) -> bool:
    """
    Save chat summary to database.
    Upsert: overwrites existing summary for the conversation.
    
    Args:
        conversation_id: UUID of the conversation
        summary_content: Summary content
        db: Database session
        
    Returns:
        bool: True if successful
    """
    try:
        uid = UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
        stmt = insert(ConversationSummary).values(
            conversation_id=uid,
            summary_content=summary_content
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['conversation_id'],
            set_={'summary_content': stmt.excluded.summary_content}
        )
        db.execute(stmt)
        db.commit()
        return True
    except Exception as e:
        logger.exception("save_summary_failed")
        db.rollback()
        raise DatabaseError(f"Failed to save summary: {e}") from e


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
        
    except Exception as e:
        logger.exception("mark_messages_as_summarized_failed")
        db.rollback()
        raise DatabaseError(f"Failed to mark messages as summarized: {e}") from e

