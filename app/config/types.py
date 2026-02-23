"""
Type definitions - Shared data structures using TypedDict.
These types represent the structure of data returned from repositories and used across the application.
"""
from typing import TypedDict, Optional, List, Literal


# ============================================
# MESSAGE TYPES
# ============================================
class Message(TypedDict, total=False):
    """Message entity - maps to messages table."""
    id: Optional[str]
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    intent: Optional[Literal["PPTX", "GENERAL"]]
    is_in_working_memory: bool
    summarized_at: Optional[str]
    metadata: Optional[dict]
    created_at: Optional[str]


# ============================================
# SUMMARY TYPES
# ============================================
class SummaryDict(TypedDict):
    """Summary dictionary structure returned from database."""
    summary_content: str


# ============================================
# CONVERSATION TYPES
# ============================================
class Conversation(TypedDict, total=False):
    """Conversation entity - maps to conversations table."""
    id: Optional[str]
    user_id: str
    title: Optional[str]
    active_presentation_id: Optional[str]
    next_presentation_id_counter: int
    created_at: Optional[str]
    updated_at: Optional[str]


# ============================================
# USER FACT TYPES
# ============================================
class UserFact(TypedDict, total=False):
    """User fact entity - maps to user_facts table."""
    id: Optional[str]
    user_id: str
    key: str
    value: str
    created_at: Optional[str]
    updated_at: Optional[str]


# ============================================
# PRESENTATION TYPES
# ============================================
class PresentationMetadataDict(TypedDict, total=False):
    """Presentation metadata structure stored in JSONB."""
    user_request: str


class Presentation(TypedDict, total=False):
    """Presentation entity - maps to presentations table."""
    id: Optional[str]
    conversation_id: str
    topic: str
    total_pages: int
    version: int
    metadata: Optional[dict]
    created_at: Optional[str]
    updated_at: Optional[str]


class PresentationWithPages(TypedDict, total=False):
    """Presentation with pages - maps to presentations + presentation_pages (JOIN)."""
    id: str
    conversation_id: str
    topic: str
    total_pages: int
    version: int
    pages: List[dict]  # List[PageContent] from pydantic_outputs
    metadata: Optional[dict]
    created_at: Optional[str]
    updated_at: Optional[str]


class PresentationVersion(TypedDict, total=False):
    """Presentation version entity - maps to presentation_versions table + computed field."""
    version: int
    total_pages: int
    user_request: Optional[str]
    created_at: str
    is_current: bool


class VersionContent(TypedDict, total=False):
    """Version content - aggregated from presentation_version_pages or presentation_pages."""
    pages: List[dict]  # List[PageContent] from pydantic_outputs
    total_pages: int

