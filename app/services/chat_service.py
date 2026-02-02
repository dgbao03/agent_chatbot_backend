"""
Chat service - Business logic for chat orchestration.
"""
from app.database.client import get_supabase_client
from app.config.constants import (
    TABLE_CONVERSATIONS,
    FIELD_ID,
    FIELD_USER_ID
)


def validate_conversation_access(user_id: str, conversation_id: str) -> None:
    """
    Validate that user has access to the conversation.
    Raises ValueError if access is denied.
    
    Args:
        user_id: UUID of the user
        conversation_id: UUID of the conversation
        
    Raises:
        ValueError: If conversation not found or user doesn't have access
    """
    try:
        supabase = get_supabase_client()
        conversation_response = supabase.from_(TABLE_CONVERSATIONS).select(FIELD_USER_ID).eq(FIELD_ID, conversation_id).maybe_single().execute()
        
        if not conversation_response.data:
            raise ValueError(f"Conversation {conversation_id} not found.")
        
        conversation_owner_id = conversation_response.data.get(FIELD_USER_ID)
        if conversation_owner_id != user_id:
            raise ValueError(f"Access denied: You can only access your own conversations. This conversation belongs to user {conversation_owner_id}.")
        
        print(f"✅ Conversation ownership validated: user_id={user_id}, conversation_id={conversation_id}")
    except ValueError as e:
        print(f"❌ Conversation ownership validation failed: {e}")
        raise
    except Exception as e:
        print(f"❌ Conversation ownership validation failed: {e}")
        raise ValueError(f"Access denied: Unable to verify conversation ownership.")

