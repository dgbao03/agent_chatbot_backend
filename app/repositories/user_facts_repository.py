"""
User facts repository - Data access layer for user facts.
"""
from app.config.supabase_client import get_supabase_client


def load_user_facts(user_id: str) -> list:
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


def upsert_user_fact(user_id: str, key: str, value: str) -> bool:
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


def delete_user_fact(user_id: str, key: str) -> bool:
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

