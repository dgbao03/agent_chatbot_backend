"""
Memory Management Module
Quản lý việc load và save chat history từ file JSON
"""

import json
import os
from pathlib import Path
from typing import List
from llama_index.core.llms import ChatMessage, MessageRole
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """Quản lý chat history, load và save từ file JSON"""
    
    def __init__(self, data_dir: str = "data"):
        """
        Args:
            data_dir: Thư mục chứa file chat history
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "chat_history.json"
    
    def get_history_path(self) -> Path:
        """
        Trả về đường dẫn đến file chat history
        
        Returns:
            Path: Đường dẫn đến file chat_history.json
        """
        return self.history_file
    
    def load_history(self) -> List[ChatMessage]:
        """
        Load chat history từ file JSON
        
        Returns:
            List[ChatMessage]: Danh sách các ChatMessage objects
            Trả về empty list nếu file không tồn tại hoặc có lỗi
        """
        if not self.history_file.exists():
            logger.info(f"Chat history file không tồn tại: {self.history_file}")
            return []
        
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    logger.info(f"Chat history file rỗng: {self.history_file}")
                    return []
                data = json.loads(content)
            
            # Convert từ dict sang ChatMessage objects
            chat_history = []
            for msg_dict in data:
                role = MessageRole(msg_dict["role"])
                content = msg_dict["content"]
                chat_history.append(ChatMessage(role=role, content=content))
            
            logger.info(f"Đã load {len(chat_history)} messages từ {self.history_file}")
            return chat_history
            
        except json.JSONDecodeError as e:
            logger.warning(f"Lỗi parse JSON từ {self.history_file}: {e}. Trả về empty list.")
            return []
        except Exception as e:
            logger.error(f"Lỗi khi load chat history từ {self.history_file}: {e}")
            return []
    
    def save_history(self, chat_history: List[ChatMessage]) -> bool:
        """
        Lưu chat history vào file JSON
        
        Args:
            chat_history: Danh sách các ChatMessage objects cần lưu
            
        Returns:
            bool: True nếu lưu thành công, False nếu có lỗi
        """
        try:
            # Convert từ ChatMessage objects sang dict
            data = []
            for msg in chat_history:
                msg_dict = {
                    "role": msg.role.value,  # MessageRole enum -> string value
                    "content": msg.content
                }
                data.append(msg_dict)
            
            # Lưu vào file với format đẹp
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Đã lưu {len(chat_history)} messages vào {self.history_file}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi lưu chat history vào {self.history_file}: {e}")
            return False

