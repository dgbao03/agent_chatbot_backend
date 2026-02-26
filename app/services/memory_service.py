"""
Memory service - Business logic for memory management.
"""
from typing import List, Tuple
from sqlalchemy.orm import Session
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer
from app.repositories.chat_repository import load_chat_history
from app.repositories.summary_repository import load_summary, save_summary
from app.utils.formatters import format_messages_for_summary
from app.config.prompts import SUMMARY_INITIAL_PROMPT, SUMMARY_UPDATE_PROMPT
from app.config.llm import get_summary_llm
from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)

llm = get_summary_llm()


def load_conversation_memory(conversation_id: str, user_id: str, db: Session) -> ChatMemoryBuffer:
    """
    Load conversation history from DB and initialise a ChatMemoryBuffer.

    Fetches messages that are still in working memory, populates them into
    a 2 000-token ChatMemoryBuffer, and returns it ready for use by the
    workflow steps.

    Args:
        conversation_id: UUID of the conversation
        user_id: UUID of the user (for ownership check)
        db: Database session

    Returns:
        ChatMemoryBuffer populated with the conversation's working-memory messages
    """
    chat_history = load_chat_history(conversation_id, user_id, db)
    memory = ChatMemoryBuffer.from_defaults(token_limit=settings.MEMORY_TOKEN_LIMIT)

    for chat in chat_history:
        memory.put(ChatMessage(
            role=chat["role"],
            content=chat["content"],
            additional_kwargs={"message_id": chat.get("id")},
        ))

    logger.debug(
        "chat_history_loaded",
        conversation_id=conversation_id,
        message_count=len(chat_history),
    )
    return memory


def split_messages_for_summary(
    messages: List[ChatMessage], 
    is_empty_truncated: bool = False
) -> Tuple[List[ChatMessage], List[ChatMessage]]:
    """
    Split messages into 80% (for summary) and 20% (to keep).
    Ensures:
    - 80% is always user-assistant pairs (from the start)
    - 20% always starts with a user message (from the end)

    If is_empty_truncated = True: summarize all messages, keep nothing.

    Args:
        messages: List of ChatMessage objects from LlamaIndex memory
        is_empty_truncated: Flag indicating truncated_messages_list is empty

    Returns:
        Tuple of (messages_to_summarize, messages_to_keep) - both are List[ChatMessage]
    """
    if not messages:
        return [], []
    
    # If truncated_messages_list is empty, summarize all messages
    if is_empty_truncated:
        return messages, []
    
    total_count = len(messages)
    
    # Find the last user message in all messages
    last_user_idx = -1
    for i in range(total_count - 1, -1, -1):
        if messages[i].role.value == "user":
            last_user_idx = i
            break
    
    if last_user_idx == -1:
        # If no user message found, keep nothing
        return messages, []
    
    # Calculate number of messages to keep (20%)
    target_keep_count = max(2, int(total_count * settings.MEMORY_KEEP_RATIO))  # Minimum 2 (1 user-assistant pair)
    
    # Start from the last user message, collect user-assistant pairs
    keep_start_idx = last_user_idx
    
    # Count user-assistant pairs from keep_start_idx to end
    valid_pairs = 0
    i = keep_start_idx
    while i < total_count - 1:
        if (
            messages[i].role.value == "user"
            and messages[i + 1].role.value == "assistant"
        ):
            valid_pairs += 1
            i += 2
        else:
            break
    
    # If valid pairs fewer than target, find more pairs from earlier
    if valid_pairs * 2 < target_keep_count:
        # Search backwards from keep_start_idx - 1
        for i in range(keep_start_idx - 1, -1, -1):
            if (
                i + 1 < total_count
                and messages[i].role.value == "user"
                and messages[i + 1].role.value == "assistant"
            ):
                keep_start_idx = i
                valid_pairs += 1
                if valid_pairs * 2 >= target_keep_count:
                    break
    
    # Ensure at least 1 user-assistant pair
    if valid_pairs == 0:
        # If no pairs found, keep only the last user message (not ideal but better than nothing)
        keep_start_idx = last_user_idx
        keep_count = 1
    else:
        keep_count = valid_pairs * 2
    
    messages_to_keep = messages[keep_start_idx:keep_start_idx + keep_count]
    messages_to_summarize = messages[:keep_start_idx]
    
    return messages_to_summarize, messages_to_keep


async def create_summary(conversation_id: str, user_id: str, messages: List[ChatMessage], db: Session) -> str:
    """
    Create summary from messages, combining with old summary if exists.

    Args:
        conversation_id: UUID of the conversation
        user_id: UUID of the user (for ownership check)
        messages: List of ChatMessage objects from LlamaIndex memory to summarize
        db: Database session
        
    Returns:
        str: Summary text
    """
    try:
        # Load old summary
        old_summary_data = load_summary(conversation_id, user_id, db)
        old_summary = old_summary_data.get("summary_content", "")
        
        # Format new messages
        formatted_messages = format_messages_for_summary(messages)
        
        # Build prompt for LLM
        if not old_summary:
            system_prompt = SUMMARY_INITIAL_PROMPT
            user_prompt = f"Please summarize the following conversation:\n\n{formatted_messages}"
        else:
            system_prompt = SUMMARY_UPDATE_PROMPT
            user_prompt = (
                f"Previous summary:\n{old_summary}\n\n"
                f"New conversation:\n{formatted_messages}\n\n"
                f"Please create a new summary combining both sections above."
            )
        
        # Call LLM to create summary
        llm_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt)
        ]
        
        response = await llm.achat(llm_messages)
        
        # Extract content from response
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            summary_text = str(response.message.content)
        elif hasattr(response, 'content'):
            summary_text = str(response.content)
        else:
            summary_text = str(response)
        
        # Save new summary (upsert overwrites)
        save_summary(conversation_id, summary_text, db)
        
        return summary_text
        
    except Exception:
        logger.exception("create_summary_failed")
        # Fallback: return simple summary
        user_count = sum(1 for msg in messages if msg.role.value == "user")
        assistant_count = sum(1 for msg in messages if msg.role.value == "assistant")
        return (
            f"[SUMMARY] Summarized {user_count} user messages and "
            f"{assistant_count} assistant responses from the previous conversation."
        )

