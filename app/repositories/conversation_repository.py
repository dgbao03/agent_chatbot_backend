"""
Conversation repository - Data access layer for conversations.
"""
from typing import Optional
from app.database.client import get_supabase_client


def create_new_conversation(user_id: str) -> str:
    """
    Tạo conversation mới với title = null ban đầu.
    Title sẽ được update sau khi generate.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        Conversation ID (UUID string)
        
    Raises:
        ValueError: If conversation creation fails
    """
    try:
        supabase = get_supabase_client()
        
        response = supabase.from_("conversations").insert(
            {
                "user_id": user_id,
                "title": None,  # Sẽ update sau
            }
        ).execute()
        
        if response.data and len(response.data) > 0:
            conversation_id = response.data[0]["id"]
            return conversation_id
        else:
            raise ValueError("Failed to create conversation: No data returned")
            
    except Exception as e:
        raise ValueError(f"Failed to create conversation: {e}")


def update_conversation_title(conversation_id: str, title: str) -> bool:
    """
    Update title của conversation.
    
    Args:
        conversation_id: UUID of the conversation
        title: Title string to set
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase_client()
        
        response = (
            supabase.from_("conversations")
            .update({"title": title})
            .eq("id", conversation_id)
            .execute()
        )
        
        if response.data:
            return True
        else:
            return False
            
    except Exception:
        return False

