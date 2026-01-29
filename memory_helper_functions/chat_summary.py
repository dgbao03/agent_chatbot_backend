"""
Chat summary management using Supabase.
Replaces JSON file storage with database operations.
"""
from typing import Optional
from datetime import datetime, timezone
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import ChatMessage, MessageRole
from config.supabase_client import get_supabase_client

llm = OpenAI(model="gpt-4o-mini", request_timeout=120.0)  # 2 minutes timeout


def _split_messages_for_summary(messages: list, is_empty_truncated: bool = False) -> tuple:
    """
    Chia messages thành 80% (để summary) và 20% (giữ lại).
    Đảm bảo:
    - 80% luôn là cặp user-assistant (từ đầu)
    - 20% luôn bắt đầu với user message (từ cuối)
    
    Nếu is_empty_truncated = True: summary toàn bộ messages, không giữ lại gì.
    
    Args:
        messages: List các ChatMessage
        is_empty_truncated: Flag cho biết truncated_messages_list rỗng
        
    Returns:
        tuple: (messages_to_summarize, messages_to_keep)
    """
    if not messages:
        return [], []
    
    # Nếu truncated_messages_list rỗng, summary toàn bộ messages
    if is_empty_truncated:
        return messages, []
    
    total_count = len(messages)
    keep_count = max(1, int(total_count * 0.2))  # 20%, tối thiểu 1 message
    
    # Tìm user message cuối cùng trong toàn bộ messages
    last_user_idx = -1
    for i in range(total_count - 1, -1, -1):
        if messages[i].role.value == "user":
            last_user_idx = i
            break
    
    if last_user_idx == -1:
        # Nếu không có user message nào, không giữ lại gì
        return messages, []
    
    # Tính số lượng messages muốn giữ (20%)
    target_keep_count = max(2, int(total_count * 0.2))  # Tối thiểu 2 (1 cặp user-assistant)
    
    # Bắt đầu từ user message cuối cùng, lấy các cặp user-assistant
    keep_start_idx = last_user_idx
    
    # Đếm số cặp user-assistant từ keep_start_idx đến cuối
    valid_pairs = 0
    i = keep_start_idx
    while i < total_count - 1:
        if messages[i].role.value == "user" and messages[i+1].role.value == "assistant":
            valid_pairs += 1
            i += 2
        else:
            break
    
    # Nếu số cặp hợp lệ ít hơn target, tìm thêm cặp từ trước đó
    if valid_pairs * 2 < target_keep_count:
        # Tìm ngược lại từ keep_start_idx - 1
        for i in range(keep_start_idx - 1, -1, -1):
            if i + 1 < total_count and messages[i].role.value == "user" and messages[i+1].role.value == "assistant":
                keep_start_idx = i
                valid_pairs += 1
                if valid_pairs * 2 >= target_keep_count:
                    break
    
    # Đảm bảo có ít nhất 1 cặp user-assistant
    if valid_pairs == 0:
        # Nếu không có cặp nào, chỉ giữ user message cuối cùng (không hợp lệ nhưng tốt hơn không có gì)
        keep_start_idx = last_user_idx
        keep_count = 1
    else:
        keep_count = valid_pairs * 2
    
    messages_to_keep = messages[keep_start_idx:keep_start_idx + keep_count]
    messages_to_summarize = messages[:keep_start_idx]
    
    return messages_to_summarize, messages_to_keep


def _load_chat_summary(conversation_id: str) -> dict:
    """
    Load latest chat summary from Supabase for a conversation.
    
    Args:
        conversation_id: UUID of the conversation
    
    Returns:
        dict: {"version": int, "summary_content": str} or {"version": 0, "summary_content": ""} if none
    """
    try:
        supabase = get_supabase_client()
        
        # Query latest summary for this conversation
        response = supabase.from_('conversation_summaries').select('*').eq(
            'conversation_id', conversation_id
        ).order('version', desc=True).limit(1).execute()
        
        if not response.data or len(response.data) == 0:
            return {"version": 0, "summary_content": ""}
        
        summary = response.data[0]
            return {
            "version": summary["version"],
            "summary_content": summary["summary_content"]
            }
        
    except Exception as e:
        print(f"Error loading chat summary from Supabase: {e}")
        return {"version": 0, "summary_content": ""}


def _save_chat_summary(conversation_id: str, version: int, summary_content: str) -> bool:
    """
    Save chat summary to Supabase.
    
    Args:
        conversation_id: UUID of the conversation
        version: Version number
        summary_content: Summary content
        
    Returns:
        bool: True if successful
    """
    try:
        supabase = get_supabase_client()
        
        # Insert new summary
        response = supabase.from_('conversation_summaries').insert({
            'conversation_id': conversation_id,
            'version': version,
            'summary_content': summary_content
        }).execute()
        
        return response.data is not None
        
    except Exception as e:
        print(f"Error saving chat summary to Supabase: {e}")
        return False


def _format_messages_for_summary(messages: list) -> str:
    """
    Format messages thành text để gửi cho LLM summary.
    
    Args:
        messages: List các ChatMessage
        
    Returns:
        str: Formatted text
    """
    formatted_lines = []
    for i, msg in enumerate(messages, 1):
        role = msg.role.value
        content = msg.content if hasattr(msg, 'content') else str(msg)
        formatted_lines.append(f"{role.capitalize()}: {content}")
    
    return "\n".join(formatted_lines)


async def _create_summary(conversation_id: str, messages: list) -> str:
    """
    Tạo summary từ messages, kết hợp với summary cũ nếu có.
    
    Args:
        conversation_id: UUID of the conversation
        messages: List các ChatMessage cần summary
        
    Returns:
        str: Summary text
    """
    try:
        # Load summary cũ
        old_summary_data = _load_chat_summary(conversation_id)
        old_version = old_summary_data["version"]
        old_summary = old_summary_data["summary_content"]
        
        # Format messages mới
        formatted_messages = _format_messages_for_summary(messages)
        
        # Tạo prompt cho LLM
        if old_version == 0:
            # Lần đầu tiên, không có summary cũ
            system_prompt = (
                "Bạn là một AI chuyên tạo tóm tắt cuộc hội thoại.\n"
                "Nhiệm vụ: Tóm tắt ngắn gọn các điểm chính của cuộc hội thoại.\n"
                "Tập trung vào:\n"
                "- Các chủ đề chính được thảo luận\n"
                "- Thông tin quan trọng được chia sẻ\n"
                "- Kết luận hoặc kết quả (nếu có)"
            )
            user_prompt = f"Hãy tóm tắt cuộc hội thoại sau đây:\n\n{formatted_messages}"
        else:
            # Có summary cũ, kết hợp với messages mới
            system_prompt = (
                "Bạn là một AI chuyên tạo tóm tắt tích lũy cuộc hội thoại.\n"
                "Nhiệm vụ: Tạo tóm tắt mới bằng cách kết hợp tóm tắt cũ với cuộc hội thoại mới.\n"
                "Yêu cầu:\n"
                "- Giữ lại thông tin quan trọng từ tóm tắt cũ\n"
                "- Bổ sung thông tin mới từ cuộc hội thoại\n"
                "- Tạo tóm tắt ngắn gọn, không lặp lại"
            )
            user_prompt = (
                f"Tóm tắt cũ (version {old_version}):\n{old_summary}\n\n"
                f"Cuộc hội thoại mới:\n{formatted_messages}\n\n"
                f"Hãy tạo tóm tắt mới kết hợp cả hai phần trên."
            )
        
        # Gọi LLM để tạo summary
        llm_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt)
        ]
        
        response = await llm.achat(llm_messages)
        
        # Lấy content từ response
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            summary_text = str(response.message.content)
        elif hasattr(response, 'content'):
            summary_text = str(response.content)
        else:
            summary_text = str(response)
        
        # Lưu summary mới với version tăng lên
        new_version = old_version + 1
        _save_chat_summary(conversation_id, new_version, summary_text)
        
        print(f"Summary created: version {new_version} (previous: {old_version})")
        
        return summary_text
        
    except Exception as e:
        print(f"Lỗi khi tạo summary: {e}")
        # Fallback: trả về summary đơn giản
        user_count = sum(1 for msg in messages if msg.role.value == "user")
        assistant_count = sum(1 for msg in messages if msg.role.value == "assistant")
        return f"[SUMMARY] Đã tóm tắt {user_count} lượt hỏi và {assistant_count} lượt trả lời từ cuộc hội thoại trước đó."


def _mark_messages_as_summarized(message_ids: list[str]) -> bool:
    """
    Mark messages as summarized (is_in_working_memory = False).
    
    Args:
        message_ids: List of message UUIDs to mark
        
    Returns:
        bool: True if successful
    """
    try:
        supabase = get_supabase_client()
        
        # Update messages with current UTC timestamp
        response = supabase.from_('messages').update({
            'is_in_working_memory': False,
            'summarized_at': datetime.now(timezone.utc).isoformat()
        }).in_('id', message_ids).execute()
        
        print(f"✅ DB Update: Marked {len(message_ids)} messages as is_in_working_memory=FALSE")
        
        return True
        
    except Exception as e:
        print(f"❌ Error marking messages as summarized: {e}")
        return False
