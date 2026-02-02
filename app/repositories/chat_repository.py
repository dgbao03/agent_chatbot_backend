"""
Chat history repository - Data access layer for messages.
"""
from typing import Optional, List
from app.database.client import get_supabase_client
from app.config.constants import (
    TABLE_MESSAGES,
    FIELD_CONVERSATION_ID,
    FIELD_IS_IN_WORKING_MEMORY,
    FIELD_CREATED_AT,
    FIELD_ID,
    FIELD_ROLE,
    FIELD_CONTENT,
    FIELD_INTENT,
    FIELD_METADATA,
    DEFAULT_IS_IN_WORKING_MEMORY
)
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
        response = supabase.from_(TABLE_MESSAGES).select('*').eq(
            FIELD_CONVERSATION_ID, conversation_id
        ).eq(
            FIELD_IS_IN_WORKING_MEMORY, True
        ).order(FIELD_CREATED_AT, desc=False).execute()
        
        if not response.data:
            return []

        # Convert to simple format for LlamaIndex
        messages: List[MessageDict] = []
        for msg in response.data:
            messages.append({
                FIELD_ID: msg[FIELD_ID],
                FIELD_ROLE: msg[FIELD_ROLE],
                FIELD_CONTENT: msg[FIELD_CONTENT],
                FIELD_INTENT: msg.get(FIELD_INTENT),
                FIELD_CREATED_AT: msg[FIELD_CREATED_AT]
            })
        
        return messages
        
    except Exception as e:
        print(f"Error loading chat history from Supabase: {e}")
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
            FIELD_CONVERSATION_ID: conversation_id,
            FIELD_ROLE: role,
            FIELD_CONTENT: content,
            FIELD_INTENT: intent,
            FIELD_METADATA: metadata,
            FIELD_IS_IN_WORKING_MEMORY: DEFAULT_IS_IN_WORKING_MEMORY  # New messages start in working memory
        }
        
        print(f"💾 Inserting message: role={role}, intent={intent}, content_len={len(content)}")
        
        response = supabase.from_(TABLE_MESSAGES).insert(message_data).execute()
        
        if response.data and len(response.data) > 0:
            msg_id = response.data[0][FIELD_ID]
            print(f"✅ Message saved with ID: {msg_id}")
            return msg_id
        else:
            print(f"⚠️ Insert returned no data: {response}")
            return None
        
    except Exception as e:
        print(f"❌ Error saving message to Supabase: {e}")
        import traceback
        traceback.print_exc()
        return None

