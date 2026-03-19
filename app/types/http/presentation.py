"""
Presentation Schemas - Pydantic models for presentation endpoints
"""
from pydantic import BaseModel
from typing import Optional, List


class PageContentResponse(BaseModel):
    page_number: int
    html_content: str
    page_title: Optional[str] = None


class VersionInfoResponse(BaseModel):
    version: int
    total_pages: int
    is_current: bool
    timestamp: Optional[str] = None  # alias for created_at for FE compatibility
    created_at: Optional[str] = None
    user_request: Optional[str] = None


class VersionContentResponse(BaseModel):
    pages: List[PageContentResponse]
    total_pages: int


class ActivePresentationResponse(BaseModel):
    presentation_id: Optional[str] = None
