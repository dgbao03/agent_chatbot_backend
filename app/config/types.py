"""
Type definitions - Shared data structures using TypedDict.
These types represent the structure of data returned from repositories and used across the application.
"""
from typing import TypedDict, Optional, List, Literal


# ============================================
# MESSAGE TYPES
# ============================================
class MessageDict(TypedDict, total=False):
    """Message dictionary structure returned from database."""
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    intent: Optional[Literal["PPTX", "GENERAL"]]
    created_at: str
    conversation_id: str
    is_in_working_memory: bool
    summarized_at: Optional[str]
    metadata: Optional[dict]


# ============================================
# SUMMARY TYPES
# ============================================
class SummaryDict(TypedDict):
    """Summary dictionary structure returned from database."""
    summary_content: str


# ============================================
# USER FACT TYPES
# ============================================
class UserFactDict(TypedDict, total=False):
    """User fact dictionary structure returned from database."""
    id: str
    key: str
    value: str
    created_at: Optional[str]
    updated_at: Optional[str]
    user_id: str


# ============================================
# PRESENTATION TYPES
# ============================================
class PresentationMetadataDict(TypedDict, total=False):
    """Presentation metadata structure stored in JSONB."""
    user_request: str


class PresentationDict(TypedDict, total=False):
    """Presentation dictionary structure returned from database."""
    id: str
    topic: str
    pages: List[dict]  # List of PageContent-like dicts
    total_pages: int
    version: int
    metadata: Optional[PresentationMetadataDict]
    conversation_id: str
    created_at: Optional[str]
    updated_at: Optional[str]


class PresentationVersionDict(TypedDict, total=False):
    """Presentation version metadata structure."""
    version: int
    total_pages: int
    user_request: Optional[str]
    created_at: str
    is_current: bool


# ============================================
# PAGE CONTENT TYPES
# ============================================
class PageContentDict(TypedDict, total=False):
    """Page content dictionary structure."""
    page_number: int
    html_content: str
    page_title: Optional[str]

