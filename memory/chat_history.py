import json
from pathlib import Path
from config.settings import CHAT_HISTORY_FILE

def _load_chat_history() -> list:
    """Load recent chat history từ file JSON. Trả về list rỗng nếu file không tồn tại hoặc lỗi."""
    try:
        if not CHAT_HISTORY_FILE.exists():
            return []

        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            history = json.loads(content)
            if not isinstance(history, list):
                return []
            return history
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi khi đọc recent_chat_history.json: {e}")
        return []

def _save_chat_history(history: list) -> bool:
    """Lưu recent chat history vào file JSON. Trả về True nếu thành công."""
    try:
        CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = CHAT_HISTORY_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        temp_file.replace(CHAT_HISTORY_FILE)
        return True
    except (IOError, Exception) as e:
        print(f"Lỗi khi ghi recent_chat_history.json: {e}")
        return False

