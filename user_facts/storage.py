import json
from typing import Optional
from pathlib import Path
from config.settings import USER_FACTS_FILE

def _load_user_facts() -> list:
    """Load user facts từ file JSON. Trả về list rỗng nếu file không tồn tại hoặc lỗi."""
    try:
        if not USER_FACTS_FILE.exists():
            return []
        
        with open(USER_FACTS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            facts = json.loads(content)
            if not isinstance(facts, list):
                return []
            return facts
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi khi đọc user_facts.json: {e}")
        return []

def _save_user_facts(facts: list) -> bool:
    """Lưu user facts vào file JSON. Trả về True nếu thành công."""
    try:
        # Đảm bảo thư mục tồn tại
        USER_FACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic write: ghi vào file tạm rồi rename
        temp_file = USER_FACTS_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(facts, f, ensure_ascii=False, indent=2)
        
        # Rename file tạm thành file chính
        temp_file.replace(USER_FACTS_FILE)
        return True
    except (IOError, Exception) as e:
        print(f"Lỗi khi ghi user_facts.json: {e}")
        return False

def _find_fact_by_key(facts: list, key: str) -> Optional[dict]:
    """Tìm fact theo key (không phân biệt hoa thường). Trả về dict hoặc None."""
    key_lower = key.lower().strip()
    for fact in facts:
        if isinstance(fact, dict) and fact.get("key", "").lower().strip() == key_lower:
            return fact
    return None

