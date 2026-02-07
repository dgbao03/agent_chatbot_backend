"""
Format functions for converting data to text formats.
"""
from app.repositories.user_facts_repository import load_user_facts


def format_user_facts_for_prompt(user_id: str) -> str:
    """
    Format user facts thành text để thêm vào System Prompt.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        Formatted string với user facts, hoặc empty string nếu không có facts
    """
    try:
        facts = load_user_facts(user_id)
        if not facts:
            return ""
        
        formatted_lines = ["USER FACTS (Thông tin về người dùng):"]
        for fact in facts:
            key = fact.get("key", "")
            value = fact.get("value", "")
            if key and value:
                formatted_lines.append(f"- {key}: {value}")
        
        if len(formatted_lines) == 1:  # Chỉ có header, không có facts
            return ""
        
        return "\n".join(formatted_lines)
        
    except Exception:
        return ""


def format_messages_for_summary(messages: list) -> str:
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

