"""
Summary repository - Data access layer for conversation summaries.
"""
from datetime import datetime, timezone
from app.database.client import get_supabase_client
from app.config.types import SummaryDict


def load_summary(conversation_id: str) -> SummaryDict:
    """
    Load chat summary from Supabase for a conversation.
    Since conversation_id is PRIMARY KEY, there's only 1 row per conversation.
    
    Args:
        conversation_id: UUID of the conversation
    
    Returns:
        dict: {"summary_content": str} or {"summary_content": ""} if none
    """
    try:
        supabase = get_supabase_client()
        
        # Query summary for this conversation (conversation_id is PRIMARY KEY, only 1 row)
        # Use limit(1) instead of maybe_single() to avoid HTTP 406 Not Acceptable
        response = (
            supabase.from_("conversation_summaries")
            .select("summary_content")
            .eq("conversation_id", conversation_id)
            .limit(1)
            .execute()
        )
        
        # Check if response has data
        if not response.data or len(response.data) == 0:
            return {"summary_content": ""}
        
        return {
            "summary_content": response.data[0].get("summary_content", ""),
        }
        
    except Exception:
        return {FIELD_SUMMARY_CONTENT: ""}


def save_summary(conversation_id: str, summary_content: str) -> bool:
    """
    Save chat summary to Supabase using UPSERT.
    Since conversation_id is PRIMARY KEY, this will insert or update the existing row.
    
    Args:
        conversation_id: UUID of the conversation
        summary_content: Summary content
        
    Returns:
        bool: True if successful
    """
    try:
        supabase = get_supabase_client()
        
        # UPSERT: Insert if not exists, update if exists (conversation_id is PRIMARY KEY)
        response = (
            supabase.from_("conversation_summaries")
            .upsert(
                {
                    "conversation_id": conversation_id,
                    "summary_content": summary_content,
                },
                on_conflict="conversation_id",
            )
            .execute()
        )
        
        return response.data is not None
        
    except Exception:
        return False


def mark_messages_as_summarized(message_ids: list[str]) -> bool:
    """
    Mark messages as summarized (is_in_working_memory = False).
    
    Args:
        message_ids: List of message UUIDs to mark
        
    Returns:
        bool: True if successful
    """
    try:
        supabase = get_supabase_client()
        
        # Update messages with current UTC timestamp
        response = (
            supabase.from_("messages")
            .update(
                {
                    "is_in_working_memory": False,
                    "summarized_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .in_("id", message_ids)
            .execute()
        )
        
        return True
        
    except Exception:
        return False

