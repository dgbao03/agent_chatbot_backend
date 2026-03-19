"""
Internal types for presentation domain.
Used by: presentation_repository, presentation_service, workflow.
"""
from typing import TypedDict, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.types.llm.outputs import PageContent


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
    pages: List["PageContent"]
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
    pages: List["PageContent"]
    total_pages: int
