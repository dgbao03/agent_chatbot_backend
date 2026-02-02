"""
Chat history management using Supabase.
Replaces JSON file storage with database operations.
"""
from typing import Optional
from config.supabase_client import get_supabase_client


def _load_chat_history(conversation_id: str) -> list:
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
        response = supabase.from_('messages').select('*').eq(
            'conversation_id', conversation_id
        ).eq(
            'is_in_working_memory', True
        ).order('created_at', desc=False).execute()
        
        if not response.data:
            return []

        # Convert to simple format for LlamaIndex
        messages = []
        for msg in response.data:
            messages.append({
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["content"],
                "intent": msg.get("intent"),
                "created_at": msg["created_at"]
            })
        
        return messages
        
    except Exception as e:
        print(f"Error loading chat history from Supabase: {e}")
        return []


def _save_message(
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
            'conversation_id': conversation_id,
            'role': role,
            'content': content,
            'intent': intent,
            'metadata': metadata,
            'is_in_working_memory': True  # New messages start in working memory
        }
        
        print(f"💾 Inserting message: role={role}, intent={intent}, content_len={len(content)}")
        
        response = supabase.from_('messages').insert(message_data).execute()
        
        if response.data and len(response.data) > 0:
            msg_id = response.data[0]['id']
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
