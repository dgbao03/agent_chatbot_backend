"""
Chat service - Business logic for chat orchestration.
"""
from app.database.client import get_supabase_client


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
        conversation_response = (
            supabase.from_("conversations")
            .select("user_id")
            .eq("id", conversation_id)
            .maybe_single()
            .execute()
        )
        
        if not conversation_response.data:
            raise ValueError(f"Conversation {conversation_id} not found.")
        
        conversation_owner_id = conversation_response.data.get("user_id")
        if conversation_owner_id != user_id:
            raise ValueError(
                "Access denied: You can only access your own conversations."
            )
    except ValueError:
        raise
    except Exception:
        raise ValueError("Access denied: Unable to verify conversation ownership.")

