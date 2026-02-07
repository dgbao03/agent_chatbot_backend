"""
User facts repository - Data access layer for user facts.
"""
from typing import List, Optional
from app.database.client import get_supabase_client
from app.config.types import UserFact


def load_user_facts(user_id: str) -> List[UserFact]:
    """
    Load user facts from Supabase.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        List of UserFact objects with all fields populated (id, user_id, key, value, created_at, updated_at)
    """
    try:
        supabase = get_supabase_client()
        
        # Query user facts
        response = (
            supabase.from_("user_facts")
            .select("*")
            .eq("user_id", user_id)
            .order("key", desc=False)
            .execute()
        )
        
        if not response.data:
            return []
        
        # Convert to simple format
        facts: List[UserFact] = []
        for fact in response.data:
            facts.append(
                {
                    "id": fact["id"],
                    "user_id": fact["user_id"],
                    "key": fact["key"],
                    "value": fact["value"],
                    "created_at": fact.get("created_at"),
                    "updated_at": fact.get("updated_at"),
                }
            )
        
        return facts
        
    except Exception:
        return []


def upsert_user_fact(fact: UserFact) -> Optional[UserFact]:
    """
    Insert or update a user fact in Supabase.
    
    Args:
        fact: UserFact object with user_id, key, value
        
    Returns:
        UserFact object with id, created_at, updated_at set if successful, None otherwise
    """
    try:
        supabase = get_supabase_client()
        
        # Upsert fact (insert or update based on user_id + key unique constraint)
        response = (
            supabase.from_("user_facts")
            .upsert(
                {
                    "user_id": fact["user_id"],
                    "key": fact["key"],
                    "value": fact["value"],
                },
                on_conflict="user_id,key",
            )
            .execute()
        )
        
        if not response.data or len(response.data) == 0:
            return None
        
        saved_fact = response.data[0]
        return {
            "id": saved_fact["id"],
            "user_id": saved_fact["user_id"],
            "key": saved_fact["key"],
            "value": saved_fact["value"],
            "created_at": saved_fact.get("created_at"),
            "updated_at": saved_fact.get("updated_at"),
        }
        
    except Exception:
        return None


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
        supabase.from_("user_facts").delete().eq("user_id", user_id).eq(
            "key", key
        ).execute()
        
        return True
        
    except Exception:
        return False

