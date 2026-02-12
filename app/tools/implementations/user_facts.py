"""
User Facts Tools - Add, update, and delete user facts.
"""
from app.tools.base import BaseTool
from app.repositories.user_facts_repository import load_user_facts, upsert_user_fact, delete_user_fact as delete_user_fact_repo
from app.utils.helpers import find_fact_by_key
from app.auth.context import get_current_user_id
from app.config.types import UserFact


class AddUserFactTool(BaseTool):
    """
    Tool for adding or updating a user fact.
    """
    
    name = "add_user_fact"
    category = "user_data"
    description = """
Định nghĩa User Fact: Các thông tin quan trọng/cá nhân về User cần ghi nhớ.
Sử dụng hàm khi thêm User Fact. 
Lưu ý: Chỉ sử dụng khi người dùng yêu cầu nhớ thông tin của họ. Không tự ý dùng hàm này.
Khi người dùng yêu cầu thêm thông tin, ví dụ: 'Lưu lại rằng tôi tên là Bao Do', 'Nhớ rằng tôi sống ở Hà Nội'. 
Các thông tin sẽ được lưu dưới dạng key-value (ví dụ: 'name': 'Bao Do', 'location': 'Hà Nội')."""
    
    def execute(self, key: str, value: str) -> str:
        """
        Add or update a user fact.
        
        Args:
            key: Fact key (e.g., "name", "company")
            value: Fact value
            
        Returns:
            Success or error message
        """
        try:
            # Get user_id from context
            user_id = get_current_user_id()
            if not user_id:
                return "Lỗi: Không thể xác định user_id. Vui lòng đăng nhập lại."
            
            if not key or not key.strip():
                return "Lỗi: Key không được để trống."
            
            if not value or not value.strip():
                return "Lỗi: Value không được để trống."
            
            key_clean = key.strip()
            value_clean = value.strip()
            
            # Upsert fact in Supabase
            fact: UserFact = {
                "user_id": user_id,
                "key": key_clean,
                "value": value_clean,
            }
            saved_fact = upsert_user_fact(fact)
            if saved_fact:
                return f"Đã lưu: {key_clean} = {value_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
                    
        except Exception as e:
            return f"Lỗi khi thêm user fact: {str(e)}"


class UpdateUserFactTool(BaseTool):
    """
    Tool for updating an existing user fact.
    """
    
    name = "update_user_fact"
    category = "user_data"
    description = """
Sử dụng hàm khi cập nhật User Fact theo key.
Lưu ý: Chỉ sử dụng khi người dùng yêu cầu cập nhật thông tin của họ. Không tự ý dùng hàm này.
Nếu key không tồn tại, công cụ sẽ báo lỗi. 
Ví dụ: khi người dùng yêu cầu sửa đổi 'tuổi tôi là 30' hoặc 'tên tôi là Bao Do', công cụ sẽ cập nhật thông tin tương ứng. 
Nếu key không có, sẽ trả về lỗi như 'Key không tồn tại'."""
    
    def execute(self, key: str, value: str) -> str:
        """
        Update an existing user fact.
        
        Args:
            key: Fact key to update
            value: New value
            
        Returns:
            Success or error message
        """
        try:
            # Get user_id from context
            user_id = get_current_user_id()
            if not user_id:
                return "Lỗi: Không thể xác định user_id. Vui lòng đăng nhập lại."
            
            if not key or not key.strip():
                return "Lỗi: Key không được để trống."
            
            if not value or not value.strip():
                return "Lỗi: Value không được để trống."
            
            key_clean = key.strip()
            value_clean = value.strip()
            
            # Check if fact exists
            facts = load_user_facts(user_id)
            fact = find_fact_by_key(facts, key_clean)
            
            if not fact:
                return f"Không tìm thấy thông tin với key: {key_clean}. Sử dụng add_user_fact để thêm mới."
            
            # Update fact
            fact_to_update: UserFact = {
                "user_id": user_id,
                "key": key_clean,
                "value": value_clean,
            }
            saved_fact = upsert_user_fact(fact_to_update)
            if saved_fact:
                return f"Đã cập nhật: {key_clean} = {value_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
                    
        except Exception as e:
            return f"Lỗi khi cập nhật user fact: {str(e)}"


class DeleteUserFactTool(BaseTool):
    """
    Tool for deleting a user fact.
    """
    
    name = "delete_user_fact"
    category = "user_data"
    description = """
Sử dụng hàm khi xóa User Fact theo key.
Lưu ý: Chỉ sử dụng khi người dùng yêu cầu xóa thông tin của họ. Không tự ý dùng hàm này.
Ví dụ: nếu người dùng yêu cầu 'Xóa tên tôi' hoặc 'Xóa tuổi tôi', công cụ sẽ xóa key tương ứng. 
Nếu không tìm thấy key, trả về lỗi như 'Không tìm thấy thông tin'."""
    
    def execute(self, key: str) -> str:
        """
        Delete a user fact.
        
        Args:
            key: Fact key to delete
            
        Returns:
            Success or error message
        """
        try:
            # Get user_id from context
            user_id = get_current_user_id()
            if not user_id:
                return "Lỗi: Không thể xác định user_id. Vui lòng đăng nhập lại."
            
            if not key or not key.strip():
                return "Lỗi: Key không được để trống."
            
            key_clean = key.strip()
            
            # Check if fact exists
            facts = load_user_facts(user_id)
            fact = find_fact_by_key(facts, key_clean)
            
            if not fact:
                return f"Không tìm thấy thông tin với key: {key_clean}"
            
            # Delete fact
            if delete_user_fact_repo(user_id, key_clean):
                return f"Đã xóa thông tin: {key_clean}"
            else:
                return "Lỗi: Không thể xóa thông tin."
                    
        except Exception as e:
            return f"Lỗi khi xóa user fact: {str(e)}"
