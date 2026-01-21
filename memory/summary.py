import json
from pathlib import Path
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import ChatMessage, MessageRole
from config.settings import CHAT_SUMMARY_FILE

llm = OpenAI(model="gpt-4o-mini")

def _load_chat_summary() -> dict:
    """
    Load chat summary từ file JSON.
    
    Returns:
        dict: {"version": int, "summary_content": str} hoặc {"version": 0, "summary_content": ""} nếu không có
    """
    try:
        if not CHAT_SUMMARY_FILE.exists():
            return {"version": 0, "summary_content": ""}
        
        with open(CHAT_SUMMARY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {"version": 0, "summary_content": ""}
            data = json.loads(content)
            if not isinstance(data, dict):
                return {"version": 0, "summary_content": ""}
            return {
                "version": data.get("version", 0),
                "summary_content": data.get("summary_content", "")
            }
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi khi đọc chat_summary.json: {e}")
        return {"version": 0, "summary_content": ""}

def _save_chat_summary(version: int, summary_content: str) -> bool:
    """
    Lưu chat summary vào file JSON.
    
    Args:
        version: Version number
        summary_content: Nội dung summary
        
    Returns:
        bool: True nếu thành công
    """
    try:
        CHAT_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = CHAT_SUMMARY_FILE.with_suffix(".tmp")
        data = {
            "version": version,
            "summary_content": summary_content
        }
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_file.replace(CHAT_SUMMARY_FILE)
        return True
    except (IOError, Exception) as e:
        print(f"Lỗi khi ghi chat_summary.json: {e}")
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

async def _create_summary(messages: list) -> str:
    """
    Tạo summary từ messages, kết hợp với summary cũ nếu có.
    
    Args:
        messages: List các ChatMessage cần summary
        
    Returns:
        str: Summary text
    """
    try:
        # Load summary cũ
        old_summary_data = _load_chat_summary()
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
        _save_chat_summary(new_version, summary_text)
        
        print(f"Summary created: version {new_version} (previous: {old_version})")
        
        return summary_text
        
    except Exception as e:
        print(f"Lỗi khi tạo summary: {e}")
        # Fallback: trả về summary đơn giản
        user_count = sum(1 for msg in messages if msg.role.value == "user")
        assistant_count = sum(1 for msg in messages if msg.role.value == "assistant")
        return f"[SUMMARY] Đã tóm tắt {user_count} lượt hỏi và {assistant_count} lượt trả lời từ cuộc hội thoại trước đó."

