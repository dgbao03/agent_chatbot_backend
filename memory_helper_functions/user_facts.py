"""
User facts management using Supabase.
Replaces JSON file storage with database operations.
"""
from typing import Optional
from config.supabase_client import get_supabase_client


def _format_user_facts_for_prompt(user_id: str) -> str:
    """
    Format user facts thành text để thêm vào System Prompt.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        Formatted string với user facts, hoặc empty string nếu không có facts
    """
    try:
        facts = _load_user_facts(user_id)
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
        
    except Exception as e:
        print(f"Error formatting user facts for prompt: {e}")
        return ""


def _load_user_facts(user_id: str) -> list:
    """
    Load user facts from Supabase.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        List of fact dicts: [{"key": "...", "value": "...", "id": "uuid"}, ...]
    """
    try:
        supabase = get_supabase_client()
        
        # Query user facts
        response = supabase.from_('user_facts').select('*').eq(
            'user_id', user_id
        ).order('key', desc=False).execute()
        
        if not response.data:
            return []
        
        # Convert to simple format
        facts = []
        for fact in response.data:
            facts.append({
                "id": fact["id"],
                "key": fact["key"],
                "value": fact["value"],
                "created_at": fact.get("created_at"),
                "updated_at": fact.get("updated_at")
            })
        
        return facts
        
    except Exception as e:
        print(f"Error loading user facts from Supabase: {e}")
        return []


def _save_user_facts(facts: list) -> bool:
    """
    Legacy function for backward compatibility.
    Now facts are managed with _upsert_user_fact().
    This function is kept to avoid breaking existing code but does nothing.
    
    Returns:
        True (always succeeds, does nothing)
    """
    print("Warning: _save_user_facts() is deprecated. Use _upsert_user_fact() instead.")
    return True


def _upsert_user_fact(user_id: str, key: str, value: str) -> bool:
    """
    Insert or update a user fact in Supabase.
    
    Args:
        user_id: UUID of the user
        key: Fact key (e.g., "company", "role")
        value: Fact value
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase_client()
        
        # Upsert fact (insert or update based on user_id + key unique constraint)
        response = supabase.from_('user_facts').upsert({
            'user_id': user_id,
            'key': key,
            'value': value
        }, on_conflict='user_id,key').execute()
        
        return response.data is not None
        
    except Exception as e:
        print(f"Error upserting user fact to Supabase: {e}")
        return False


def _delete_user_fact(user_id: str, key: str) -> bool:
    """
    Delete a user fact from Supabase.
    
    Args:
        user_id: UUID of the user
        key: Fact key to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase_client()
        
        # Delete fact
        response = supabase.from_('user_facts').delete().eq(
            'user_id', user_id
        ).eq('key', key).execute()
        
        return True
        
    except Exception as e:
        print(f"Error deleting user fact from Supabase: {e}")
        return False


def _find_fact_by_key(facts: list, key: str) -> Optional[dict]:
    """
    Tìm fact theo key (không phân biệt hoa thường).
    
    Args:
        facts: List of fact dicts
        key: Key to find
        
    Returns:
        Fact dict hoặc None
    """
    key_lower = key.lower().strip()
    for fact in facts:
        if isinstance(fact, dict) and fact.get("key", "").lower().strip() == key_lower:
            return fact
    return None
