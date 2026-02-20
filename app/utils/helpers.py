"""
Pure utility functions (no domain dependencies).
"""
from typing import Optional, List, Any
from app.config.types import UserFact, Message
from app.repositories.chat_repository import save_message


def find_fact_by_key(facts: List[UserFact], key: str) -> Optional[UserFact]:
    """
    Tìm fact theo key (không phân biệt hoa thường).
    
    Args:
        facts: List of UserFact objects
        key: Key to find (case-insensitive)
        
    Returns:
        UserFact object if found, None otherwise
    """
    key_lower = key.lower().strip()
    for fact in facts:
        if isinstance(fact, dict) and fact.get("key", "").lower().strip() == key_lower:
            return fact
    return None


async def save_error_response(
    conversation_id: str,
    db: Any,
    content: str,
    result_dict: dict,
    memory: Optional[Any] = None,
    ctx: Optional[Any] = None,
) -> dict:
    """
    Save assistant error message to DB. Optionally add to memory and update ctx.store.
    Returns result_dict for workflow to wrap in StopEvent.
    """
    assistant_message: Message = {
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": content,
        "intent": "GENERAL",
        "metadata": {"error_fallback": True},
    }
    saved = save_message(assistant_message, db)
    msg_id = saved["id"] if saved else None

    if memory is not None and ctx is not None:
        from llama_index.core.llms import ChatMessage, MessageRole

        memory.put(
            ChatMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                additional_kwargs={"message_id": msg_id},
            )
        )
        await ctx.store.set("chat_history", memory)

    return result_dict
