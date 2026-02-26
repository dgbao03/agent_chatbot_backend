"""
Pure utility functions (no domain dependencies).
"""
from typing import Optional, List
from app.config.types import UserFact


def find_fact_by_key(facts: List[UserFact], key: str) -> Optional[UserFact]:
    """
    Find fact by key (case-insensitive).
    
    Args:
        facts: List of UserFact objects
        key: Key to find (case-insensitive)
        
    Returns:
        UserFact object if found, None otherwise
    """
    key_lower = key.lower().strip()
    for fact in facts:
        if isinstance(fact, dict) and fact.get("key", "").lower().strip() == key_lower:
            return fact
    return None
