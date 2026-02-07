"""
Chat history repository - Data access layer for messages.
"""
from typing import Optional, List
from app.database.client import get_supabase_client
from app.config.types import MessageDict


def load_chat_history(conversation_id: str) -> List[MessageDict]:
    """
    Load working memory messages from Supabase for a conversation.
    Returns list of messages in working memory, ordered by created_at.
    
    Args:
        conversation_id: UUID of the conversation
        
    Returns:
        List of message dicts with format:
        [
            {"role": "user", "content": "...", "id": "uuid"},
            {"role": "assistant", "content": "...", "id": "uuid"},
            ...
        ]
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
        messages: List[MessageDict] = []
        for msg in response.data:
            messages.append(
                {
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "intent": msg.get("intent"),
                    "created_at": msg["created_at"],
                }
            )
        
        return messages
        
    except Exception:
        return []


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    intent: Optional[str] = None,
    metadata: Optional[dict] = None
) -> Optional[str]:
    """
    Save a new message to Supabase.
    
    Args:
        conversation_id: UUID of the conversation
        role: 'user' or 'assistant' or 'system'
        content: Message content
        intent: Optional intent ('PPTX', 'GENERAL', etc.)
        metadata: Optional metadata dict
        
    Returns:
        Message ID if successful, None if failed
    """
    try:
        supabase = get_supabase_client()
        
        # Insert message
        message_data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "intent": intent,
            "metadata": metadata,
            "is_in_working_memory": True,  # New messages start in working memory
        }
        
        response = supabase.from_("messages").insert(message_data).execute()
        
        if response.data and len(response.data) > 0:
            msg_id = response.data[0]["id"]
            return msg_id
        else:
            return None
        
    except Exception:
        return None

