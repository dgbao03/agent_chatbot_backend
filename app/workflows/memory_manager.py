"""
Memory manager - Handles memory truncation and summarization.
"""
import hashlib
from llama_index.core.workflow import Context
from llama_index.core.memory import ChatMemoryBuffer
from app.services.memory_service import split_messages_for_summary, create_summary
from app.repositories.summary_repository import mark_messages_as_summarized


async def process_memory_truncation(ctx: Context, memory: ChatMemoryBuffer) -> None:
    """
    Xử lý memory truncation và summary.
    
    Args:
        ctx: Workflow context
        memory: ChatMemoryBuffer cần xử lý
    """
    # Get conversation_id and db from context
    conversation_id = await ctx.store.get("conversation_id")
    db = await ctx.store.get("db")
    
    all_messages = memory.get_all()
    truncated_messages_list = memory.get()
    
    # Kiểm tra truncate bằng hash của message đầu tiên
    is_truncated = False
    is_empty_truncated = False  # Flag: truncated_messages_list rỗng
    
    # Kiểm tra trường hợp đặc biệt: all_messages có nhưng truncated_messages_list rỗng
    if all_messages and not truncated_messages_list:
        is_truncated = True
        is_empty_truncated = True
    elif all_messages and truncated_messages_list:
        # Lấy message đầu tiên từ get_all()
        first_msg_all = all_messages[0]
        first_content_all = first_msg_all.content if hasattr(first_msg_all, 'content') else str(first_msg_all)
        
        # Lấy message đầu tiên từ get()
        first_msg_truncated = truncated_messages_list[0]
        first_content_truncated = first_msg_truncated.content if hasattr(first_msg_truncated, 'content') else str(first_msg_truncated)
        
        # Tạo hash từ 20 ký tự đầu + 20 ký tự cuối
        def create_hash(content: str) -> str:
            if len(content) < 40:
                # Nếu content ngắn hơn 40 ký tự, dùng toàn bộ
                combined = content
            else:
                combined = content[:20] + content[-20:]
            return hashlib.md5(combined.encode('utf-8')).hexdigest()
        
        hash_all = create_hash(first_content_all)
        hash_truncated = create_hash(first_content_truncated)
        
        # So sánh hash
        is_truncated = (hash_all != hash_truncated)
    
    if is_truncated:
        # Xử lý truncate: lấy 80% để summary, giữ lại 20% (hoặc summary toàn bộ nếu is_empty_truncated)
        messages_to_summarize, messages_to_keep = split_messages_for_summary(all_messages, is_empty_truncated)
        
        # Tạo summary
        summary_text = await create_summary(conversation_id, messages_to_summarize, db)
        
        # Mark messages as summarized in DB (set is_in_working_memory = FALSE)
        message_ids_to_summarize = []
        for msg in messages_to_summarize:
            msg_id = msg.additional_kwargs.get("message_id")
            if msg_id:
                message_ids_to_summarize.append(msg_id)
        
        if message_ids_to_summarize:
            mark_messages_as_summarized(message_ids_to_summarize, db)
        
        # Tạo memory mới
        if messages_to_keep:
            # Có messages để giữ lại: tạo memory với 20% messages
            new_memory = ChatMemoryBuffer.from_defaults(token_limit=memory.token_limit)
            for msg in messages_to_keep:
                new_memory.put(msg)
            
            # Cập nhật memory trong context
            await ctx.store.set("chat_history", new_memory)
            memory = new_memory
        else:
            # Không có messages để giữ lại (is_empty_truncated): tạo memory rỗng
            new_memory = ChatMemoryBuffer.from_defaults(token_limit=memory.token_limit)
            await ctx.store.set("chat_history", new_memory)
            memory = new_memory

