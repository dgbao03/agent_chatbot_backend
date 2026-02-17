"""
Presentations Router - Presentation read endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas.presentation import (
    VersionInfoResponse,
    VersionContentResponse,
    PageContentResponse,
)
from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.repositories.presentation_repository import (
    get_presentation_versions,
    get_version_content,
)

router = APIRouter(prefix="/presentations", tags=["presentations"])


@router.get("/{presentation_id}/versions", response_model=List[VersionInfoResponse])
async def list_presentation_versions(
    presentation_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all versions of a presentation"""
    versions = get_presentation_versions(presentation_id, db, user_id=user_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Presentation not found")
    # Map created_at to timestamp for FE compatibility
    return [
        VersionInfoResponse(
            version=v["version"],
            total_pages=v["total_pages"],
            is_current=v["is_current"],
            timestamp=v.get("created_at"),
            created_at=v.get("created_at"),
            user_request=v.get("user_request"),
        )
        for v in versions
    ]


@router.get("/{presentation_id}/versions/{version}", response_model=VersionContentResponse)
async def get_version_content_endpoint(
    presentation_id: str,
    version: int,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get pages content of a specific version"""
    data = get_version_content(presentation_id, version, db, user_id=user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Version not found")
    pages = [
        PageContentResponse(
            page_number=p.page_number,
            html_content=p.html_content,
            page_title=p.page_title,
        )
        for p in data["pages"]
    ]
    return VersionContentResponse(pages=pages, total_pages=data["total_pages"])
