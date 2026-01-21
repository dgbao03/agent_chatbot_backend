from user_facts.storage import _load_user_facts, _save_user_facts, _find_fact_by_key

def add_user_fact(key: str, value: str) -> str:
    try:
        if not key or not key.strip():
            return "Lỗi: Key không được để trống."
        
        if not value or not value.strip():
            return "Lỗi: Value không được để trống."
        
        facts = _load_user_facts()
        key_clean = key.strip()
        value_clean = value.strip()
        
        # Kiểm tra key đã tồn tại chưa
        existing_fact = _find_fact_by_key(facts, key_clean)
        
        if existing_fact:
            # Cập nhật fact hiện có
            existing_fact["value"] = value_clean
            if _save_user_facts(facts):
                return f"Đã cập nhật: {key_clean} = {value_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
        else:
            # Thêm fact mới
            new_fact = {"key": key_clean, "value": value_clean}
            facts.append(new_fact)
            if _save_user_facts(facts):
                return f"Đã lưu: {key_clean} = {value_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
                
    except Exception as e:
        return f"Lỗi khi thêm user fact: {str(e)}"

def update_user_fact(key: str, value: str) -> str:
    try:
        if not key or not key.strip():
            return "Lỗi: Key không được để trống."
        
        if not value or not value.strip():
            return "Lỗi: Value không được để trống."
        
        facts = _load_user_facts()
        key_clean = key.strip()
        value_clean = value.strip()
        
        # Tìm fact theo key
        fact = _find_fact_by_key(facts, key_clean)
        
        if fact:
            fact["value"] = value_clean
            if _save_user_facts(facts):
                return f"Đã cập nhật: {key_clean} = {value_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
        else:
            return f"Không tìm thấy thông tin với key: {key_clean}. Sử dụng add_user_fact để thêm mới."
                
    except Exception as e:
        return f"Lỗi khi cập nhật user fact: {str(e)}"

def delete_user_fact(key: str) -> str:
    try:
        if not key or not key.strip():
            return "Lỗi: Key không được để trống."
        
        facts = _load_user_facts()
        key_clean = key.strip()
        
        # Tìm và xóa fact
        fact = _find_fact_by_key(facts, key_clean)
        
        if fact:
            facts.remove(fact)
            if _save_user_facts(facts):
                return f"Đã xóa thông tin: {key_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
        else:
            return f"Không tìm thấy thông tin với key: {key_clean}"
                
    except Exception as e:
        return f"Lỗi khi xóa user fact: {str(e)}"

