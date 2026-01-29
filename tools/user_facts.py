"""
User facts tools for LLM.
These tools allow LLM to add, update, and delete user facts.
"""
from memory_helper_functions.user_facts import _load_user_facts, _upsert_user_fact, _delete_user_fact, _find_fact_by_key
from config.workflow_context import get_current_user_id


def add_user_fact(key: str, value: str) -> str:
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
        if _upsert_user_fact(user_id, key_clean, value_clean):
            return f"Đã lưu: {key_clean} = {value_clean}"
        else:
            return "Lỗi: Không thể lưu thông tin."
                
    except Exception as e:
        return f"Lỗi khi thêm user fact: {str(e)}"


def update_user_fact(key: str, value: str) -> str:
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
        facts = _load_user_facts(user_id)
        fact = _find_fact_by_key(facts, key_clean)
        
        if not fact:
            return f"Không tìm thấy thông tin với key: {key_clean}. Sử dụng add_user_fact để thêm mới."
        
        # Update fact
        if _upsert_user_fact(user_id, key_clean, value_clean):
                return f"Đã cập nhật: {key_clean} = {value_clean}"
        else:
            return "Lỗi: Không thể lưu thông tin."
                
    except Exception as e:
        return f"Lỗi khi cập nhật user fact: {str(e)}"


def delete_user_fact(key: str) -> str:
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
        facts = _load_user_facts(user_id)
        fact = _find_fact_by_key(facts, key_clean)
        
        if not fact:
            return f"Không tìm thấy thông tin với key: {key_clean}"
        
        # Delete fact
        if _delete_user_fact(user_id, key_clean):
            return f"Đã xóa thông tin: {key_clean}"
        else:
            return "Lỗi: Không thể xóa thông tin."
                
    except Exception as e:
        return f"Lỗi khi xóa user fact: {str(e)}"
