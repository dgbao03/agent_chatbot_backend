"""
Conversation repository - Data access layer for conversations.
"""
from typing import Optional
from app.database.client import get_supabase_client
from app.config.constants import (
    TABLE_CONVERSATIONS,
    FIELD_ID,
    FIELD_USER_ID,
    FIELD_TITLE
)


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
        
        response = supabase.from_(TABLE_CONVERSATIONS).insert({
            FIELD_USER_ID: user_id,
            FIELD_TITLE: None  # Sẽ update sau
        }).execute()
        
        if response.data and len(response.data) > 0:
            conversation_id = response.data[0][FIELD_ID]
            print(f"✅ Created new conversation: {conversation_id}")
            return conversation_id
        else:
            raise ValueError("Failed to create conversation: No data returned")
            
    except Exception as e:
        print(f"❌ Error creating conversation: {e}")
        import traceback
        traceback.print_exc()
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
        
        response = supabase.from_(TABLE_CONVERSATIONS).update({
            FIELD_TITLE: title
        }).eq(FIELD_ID, conversation_id).execute()
        
        if response.data:
            print(f"✅ Updated conversation title: {conversation_id} -> {title}")
            return True
        else:
            print(f"⚠️ Update conversation title returned no data: {conversation_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating conversation title: {e}")
        import traceback
        traceback.print_exc()
        return False

