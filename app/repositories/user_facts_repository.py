"""
User facts repository - Data access layer for user facts.
"""
from typing import List
from app.database.client import get_supabase_client
from app.config.constants import (
    TABLE_USER_FACTS,
    FIELD_USER_ID,
    FIELD_KEY,
    FIELD_VALUE,
    FIELD_ID,
    FIELD_CREATED_AT,
    FIELD_UPDATED_AT
)
from app.config.types import UserFactDict


def load_user_facts(user_id: str) -> List[UserFactDict]:
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
        response = supabase.from_(TABLE_USER_FACTS).select('*').eq(
            FIELD_USER_ID, user_id
        ).order(FIELD_KEY, desc=False).execute()
        
        if not response.data:
            return []
        
        # Convert to simple format
        facts: List[UserFactDict] = []
        for fact in response.data:
            facts.append({
                FIELD_ID: fact[FIELD_ID],
                FIELD_KEY: fact[FIELD_KEY],
                FIELD_VALUE: fact[FIELD_VALUE],
                FIELD_CREATED_AT: fact.get(FIELD_CREATED_AT),
                FIELD_UPDATED_AT: fact.get(FIELD_UPDATED_AT)
            })
        
        return facts
        
    except Exception:
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
        response = supabase.from_(TABLE_USER_FACTS).upsert({
            FIELD_USER_ID: user_id,
            FIELD_KEY: key,
            FIELD_VALUE: value
        }, on_conflict=f'{FIELD_USER_ID},{FIELD_KEY}').execute()
        
        return response.data is not None
        
    except Exception:
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
        response = supabase.from_(TABLE_USER_FACTS).delete().eq(
            FIELD_USER_ID, user_id
        ).eq(FIELD_KEY, key).execute()
        
        return True
        
    except Exception:
        return False

