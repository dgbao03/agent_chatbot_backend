"""
Memory manager - Handles memory truncation and summarization.
"""
import hashlib
from llama_index.core.workflow import Context
from llama_index.core.memory import ChatMemoryBuffer
from app.services.memory_service import split_messages_for_summary, create_summary
from app.repositories.summary_repository import mark_messages_as_summarized
from app.logging import get_logger

logger = get_logger(__name__)


async def process_memory_truncation(ctx: Context, memory: ChatMemoryBuffer) -> None:
    """
    Handle memory truncation and summarization.
    
    Args:
        ctx: Workflow context
        memory: ChatMemoryBuffer to process
    """
    # Get conversation_id, user_id and db from context
    conversation_id = await ctx.store.get("conversation_id")
    user_id = await ctx.store.get("user_id")
    db = await ctx.store.get("db")
    
    all_messages = memory.get_all()
    truncated_messages_list = memory.get()
    
    # Detect truncation by comparing hash of first message
    is_truncated = False
    is_empty_truncated = False
    
    if all_messages and not truncated_messages_list:
        is_truncated = True
        is_empty_truncated = True
    elif all_messages and truncated_messages_list:
        first_msg_all = all_messages[0]
        first_content_all = first_msg_all.content if hasattr(first_msg_all, 'content') else str(first_msg_all)
        
        first_msg_truncated = truncated_messages_list[0]
        first_content_truncated = first_msg_truncated.content if hasattr(first_msg_truncated, 'content') else str(first_msg_truncated)
        
        def create_hash(content: str) -> str:
            if len(content) < 40:
                combined = content
            else:
                combined = content[:20] + content[-20:]
            return hashlib.md5(combined.encode('utf-8')).hexdigest()
        
        hash_all = create_hash(first_content_all)
        hash_truncated = create_hash(first_content_truncated)
        
        is_truncated = (hash_all != hash_truncated)
    
    if not is_truncated:
        return

    logger.info(
        "memory_truncation_detected",
        conversation_id=conversation_id,
        total_messages=len(all_messages),
        truncated_to=len(truncated_messages_list),
    )

    messages_to_summarize, messages_to_keep = split_messages_for_summary(all_messages, is_empty_truncated)

    try:
        summary_text = await create_summary(conversation_id, user_id, messages_to_summarize, db)
        logger.info(
            "summary_created",
            conversation_id=conversation_id,
            messages_summarized=len(messages_to_summarize),
        )
    except Exception as e:
        logger.error(
            "summary_creation_failed",
            conversation_id=conversation_id,
            error_type=type(e).__name__,
            error_message=str(e),
        )
        return
    
    # Mark messages as summarized in DB (set is_in_working_memory = FALSE)
    message_ids_to_summarize = []
    for msg in messages_to_summarize:
        msg_id = msg.additional_kwargs.get("message_id")
        if msg_id:
            message_ids_to_summarize.append(msg_id)
    
    if message_ids_to_summarize:
        mark_messages_as_summarized(message_ids_to_summarize, db)
    
    new_memory = ChatMemoryBuffer.from_defaults(token_limit=memory.token_limit)
    if messages_to_keep:
        for msg in messages_to_keep:
            new_memory.put(msg)
    
    await ctx.store.set("chat_history", new_memory)

