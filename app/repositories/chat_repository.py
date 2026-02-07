"""
Chat history repository - Data access layer for messages.
"""
from typing import Optional, List
from app.database.client import get_supabase_client
from app.config.types import Message


def load_chat_history(conversation_id: str) -> List[Message]:
    """
    Load working memory messages from Supabase for a conversation.
    Returns list of messages in working memory, ordered by created_at.
    
    Args:
        conversation_id: UUID of the conversation
        
    Returns:
        List of Message objects with all fields populated (id, conversation_id, role, content, etc.)
    """
    try:
        supabase = get_supabase_client()
        
        # Query messages in working memory for this conversation
        response = (
            supabase.from_("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .eq("is_in_working_memory", True)
            .order("created_at", desc=False)
            .execute()
        )
        
        if not response.data:
            return []

        # Convert to simple format for LlamaIndex
        messages: List[Message] = []
        for msg in response.data:
            messages.append(
                {
                    "id": msg["id"],
                    "conversation_id": msg["conversation_id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "intent": msg.get("intent"),
                    "is_in_working_memory": msg.get("is_in_working_memory", True),
                    "summarized_at": msg.get("summarized_at"),
                    "metadata": msg.get("metadata"),
                    "created_at": msg["created_at"],
                }
            )
        
        return messages
        
    except Exception:
        return []


def save_message(message: Message) -> Optional[Message]:
    """
    Save a new message to Supabase.
    
    Args:
        message: Message object with conversation_id, role, content, intent (optional), metadata (optional)
        
    Returns:
        Message object with id and created_at set if successful, None if failed
    """
    try:
        supabase = get_supabase_client()
        
        # Extract fields from message object
        message_data = {
            "conversation_id": message["conversation_id"],
            "role": message["role"],
            "content": message["content"],
            "intent": message.get("intent"),
            "metadata": message.get("metadata"),
            "is_in_working_memory": message.get("is_in_working_memory", True),  # Default to True for new messages
        }
        
        response = supabase.from_("messages").insert(message_data).execute()
        
        if response.data and len(response.data) > 0:
            saved_msg = response.data[0]
            return {
                "id": saved_msg["id"],
                "conversation_id": saved_msg["conversation_id"],
                "role": saved_msg["role"],
                "content": saved_msg["content"],
                "intent": saved_msg.get("intent"),
                "is_in_working_memory": saved_msg.get("is_in_working_memory", True),
                "summarized_at": saved_msg.get("summarized_at"),
                "metadata": saved_msg.get("metadata"),
                "created_at": saved_msg.get("created_at"),
            }
        else:
            return None
        
    except Exception:
        return None

