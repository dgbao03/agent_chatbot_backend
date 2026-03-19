"""
Internal types for user facts domain.
Used by: user_facts_repository, helpers, tools/user_facts.
"""
from typing import TypedDict, Optional


class UserFact(TypedDict, total=False):
    """User fact entity - maps to user_facts table."""
    id: Optional[str]
    user_id: str
    key: str
    value: str
    created_at: Optional[str]
    updated_at: Optional[str]
