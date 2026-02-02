"""
Pure utility functions (no domain dependencies).
"""
from typing import Optional


def find_fact_by_key(facts: list, key: str) -> Optional[dict]:
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

