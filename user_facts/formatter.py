from user_facts.storage import _load_user_facts

def _format_user_facts_for_prompt() -> str:
    """Format user facts thành text để thêm vào System Prompt. Trả về chuỗi rỗng nếu không có facts."""
    try:
        facts = _load_user_facts()
        if not facts:
            return ""
        
        formatted_lines = ["USER FACTS (Thông tin về người dùng):"]
        for fact in facts:
            if isinstance(fact, dict) and "key" in fact and "value" in fact:
                formatted_lines.append(f"- {fact['key']}: {fact['value']}")
        
        if len(formatted_lines) == 1:  # Chỉ có header, không có facts
            return ""
        
        return "\n".join(formatted_lines)
    except Exception as e:
        print(f"Lỗi khi format user facts cho prompt: {e}")
        return ""

