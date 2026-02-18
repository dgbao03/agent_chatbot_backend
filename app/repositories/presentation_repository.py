"""
Presentation repository - Data access layer for presentations.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import (
    Presentation,
    PresentationPage,
    PresentationVersion,
    PresentationVersionPage,
    Conversation
)
from app.config.pydantic_outputs import PageContent
from app.config.types import (
    Presentation as PresentationDict,
    PresentationWithPages,
    PresentationVersion as PresentationVersionDict,
    VersionContent,
)
from app.auth.context import get_current_user_id


def create_presentation(
    presentation: PresentationDict,
    pages: List[PageContent],
    user_request: str,
    db: Session
) -> Optional[PresentationDict]:
    """
    Create new presentation in database.
    
    Args:
        presentation: Presentation dict with conversation_id, topic, total_pages
        pages: List of PageContent objects
        user_request: User's request text
        db: Database session
        
    Returns:
        Presentation dict with id and created_at set if successful, None otherwise
    """
    try:
        # Get current user for authorization check
        user_id = get_current_user_id()
        
        # Verify conversation belongs to user
        conversation = db.query(Conversation).filter(
            Conversation.id == presentation["conversation_id"],
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not conversation:
            return None
        
        # Create presentation
        new_presentation = Presentation(
            conversation_id=presentation["conversation_id"],
            topic=presentation["topic"],
            total_pages=presentation["total_pages"],
            version=presentation.get("version", 1),
            pres_metadata={"user_request": user_request}
        )
        
        db.add(new_presentation)
        db.flush()  # Get ID without committing
        
        # Insert pages
        for page in pages:
            new_page = PresentationPage(
                presentation_id=new_presentation.id,
                page_number=page.page_number,
                html_content=page.html_content,
                page_title=page.page_title
            )
            db.add(new_page)
        
        # Set as active presentation
        conversation.active_presentation_id = new_presentation.id
        
        db.commit()
        db.refresh(new_presentation)
        
        return {
            "id": str(new_presentation.id),
            "conversation_id": str(new_presentation.conversation_id),
            "topic": new_presentation.topic,
            "total_pages": new_presentation.total_pages,
            "version": new_presentation.version,
            "metadata": new_presentation.pres_metadata,
            "created_at": new_presentation.created_at.isoformat() if new_presentation.created_at else None,
            "updated_at": new_presentation.updated_at.isoformat() if new_presentation.updated_at else None,
        }
        
    except Exception:
        db.rollback()
        return None


def load_presentation(presentation_id: str, db: Session) -> Optional[PresentationWithPages]:
    """
    Load presentation with current version pages.
    
    Args:
        presentation_id: UUID of presentation
        db: Database session
        
    Returns:
        PresentationWithPages dict with pages included, or None
    """
    try:
        # Get current user for authorization check
        user_id = get_current_user_id()
        
        # Get presentation with user authorization check
        presentation = db.query(Presentation).join(Conversation, Presentation.conversation_id == Conversation.id).filter(
            Presentation.id == presentation_id,
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not presentation:
            return None
        
        # Get pages
        pages_data = db.query(PresentationPage).filter(
            PresentationPage.presentation_id == presentation_id
        ).order_by(PresentationPage.page_number.asc()).all()
        
        pages = []
        for page_data in pages_data:
            pages.append(
                PageContent(
                    page_number=page_data.page_number,
                    html_content=page_data.html_content,
                    page_title=page_data.page_title,
                )
            )
        
        return {
            "id": str(presentation.id),
            "conversation_id": str(presentation.conversation_id),
            "topic": presentation.topic,
            "pages": pages,
            "total_pages": presentation.total_pages,
            "version": presentation.version,
            "metadata": presentation.pres_metadata or {},
            "created_at": presentation.created_at.isoformat() if presentation.created_at else None,
            "updated_at": presentation.updated_at.isoformat() if presentation.updated_at else None,
        }
        
    except Exception:
        return None


def update_presentation(
    presentation: PresentationDict,
    pages: List[PageContent],
    user_request: str,
    db: Session
) -> Optional[PresentationDict]:
    """
    Update presentation (archives current version, then updates).
    
    Args:
        presentation: Presentation dict with id, topic, total_pages
        pages: New list of PageContent objects
        user_request: User's request text
        db: Database session
        
    Returns:
        Presentation dict with updated version if successful, None otherwise
    """
    try:
        presentation_id = presentation["id"]
        
        if not presentation_id:
            return None
        
        # Get current user for authorization check
        user_id = get_current_user_id()
        
        # Get current presentation with user authorization
        current_presentation = db.query(Presentation).join(Conversation, Presentation.conversation_id == Conversation.id).filter(
            Presentation.id == presentation_id,
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not current_presentation:
            return None
        
        current_version = current_presentation.version
        new_version = current_version + 1
        
        # Archive current version
        # Get current pages
        current_pages = db.query(PresentationPage).filter(
            PresentationPage.presentation_id == presentation_id
        ).all()
        
        if current_pages:
            # Extract user_request from metadata
            old_user_request = None
            if current_presentation.pres_metadata:
                old_user_request = current_presentation.pres_metadata.get("user_request")
            
            # Create archived version record (PresentationVersion has no topic column)
            archived_version = PresentationVersion(
                presentation_id=presentation_id,
                version=current_version,
                total_pages=current_presentation.total_pages,
                user_request=old_user_request
            )
            db.add(archived_version)
            db.flush()
            
            # Archive pages
            for page in current_pages:
                archived_page = PresentationVersionPage(
                    version_id=archived_version.id,
                    page_number=page.page_number,
                    html_content=page.html_content,
                    page_title=page.page_title
                )
                db.add(archived_page)
        
        # Delete old pages (will be replaced)
        db.query(PresentationPage).filter(
            PresentationPage.presentation_id == presentation_id
        ).delete()
        
        # Update presentation metadata
        current_presentation.topic = presentation["topic"]
        current_presentation.total_pages = presentation["total_pages"]
        current_presentation.version = new_version
        current_presentation.pres_metadata = {"user_request": user_request}
        
        # Insert new pages
        for page in pages:
            new_page = PresentationPage(
                presentation_id=presentation_id,
                page_number=page.page_number,
                html_content=page.html_content,
                page_title=page.page_title
            )
            db.add(new_page)
        
        db.commit()
        db.refresh(current_presentation)
        
        return {
            "id": str(current_presentation.id),
            "conversation_id": str(current_presentation.conversation_id),
            "topic": current_presentation.topic,
            "total_pages": current_presentation.total_pages,
            "version": current_presentation.version,
            "metadata": current_presentation.pres_metadata,
            "created_at": current_presentation.created_at.isoformat() if current_presentation.created_at else None,
            "updated_at": current_presentation.updated_at.isoformat() if current_presentation.updated_at else None,
        }
        
    except Exception:
        db.rollback()
        return None


def get_presentation_versions(
    presentation_id: str, db: Session, user_id: Optional[str] = None
) -> List[PresentationVersionDict]:
    """
    Get all versions metadata for a presentation.
    
    Args:
        presentation_id: UUID of presentation
        db: Database session
        user_id: Optional - if provided use it, else use get_current_user_id() from context
        
    Returns:
        List of PresentationVersion dicts
    """
    try:
        # Get user_id: explicit param or from context (for workflow)
        uid = user_id or get_current_user_id()
        
        # Verify presentation belongs to user
        presentation = db.query(Presentation).join(Conversation, Presentation.conversation_id == Conversation.id).filter(
            Presentation.id == presentation_id,
            Conversation.user_id == uid  # Security: filter by user_id
        ).first()
        
        if not presentation:
            return []
        
        # Get archived versions
        archived_versions = db.query(PresentationVersion).filter(
            PresentationVersion.presentation_id == presentation_id
        ).order_by(PresentationVersion.version.desc()).all()
        
        # Convert to expected format
        versions: List[PresentationVersionDict] = []
        
        # Add current version
        versions.append(
            {
                "version": presentation.version,
                "total_pages": presentation.total_pages,
                "is_current": True,
                "created_at": presentation.updated_at.isoformat() if presentation.updated_at else None,
                "user_request": presentation.pres_metadata.get("user_request") if presentation.pres_metadata else None,
            }
        )
        
        # Add archived versions
        for v in archived_versions:
            versions.append(
                {
                    "version": v.version,
                    "total_pages": v.total_pages,
                    "is_current": False,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                    "user_request": v.user_request,
                }
            )
        
        return versions
        
    except Exception as e:
        return []


def get_version_content(
    presentation_id: str, version: int, db: Session, user_id: Optional[str] = None
) -> Optional[VersionContent]:
    """
    Get pages content of a specific version.
    
    Args:
        presentation_id: UUID of presentation
        version: Version number
        db: Database session
        user_id: Optional - if provided use it, else use get_current_user_id() from context
        
    Returns:
        VersionContent dict with pages and total_pages, or None
    """
    try:
        # Get user_id: explicit param or from context (for workflow)
        uid = user_id or get_current_user_id()
        
        # Get presentation with user authorization
        presentation = db.query(Presentation).join(Conversation, Presentation.conversation_id == Conversation.id).filter(
            Presentation.id == presentation_id,
            Conversation.user_id == uid  # Security: filter by user_id
        ).first()
        
        if not presentation:
            return None
        
        current_version = presentation.version
        
        # If requesting current version, load from presentation_pages
        if version == current_version:
            pages_data = db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation_id
            ).order_by(PresentationPage.page_number.asc()).all()
        else:
            # Otherwise load from archived versions
            archived_version = db.query(PresentationVersion).filter(
                PresentationVersion.presentation_id == presentation_id,
                PresentationVersion.version == version
            ).first()
            
            if not archived_version:
                return None
            
            pages_data = db.query(PresentationVersionPage).filter(
                PresentationVersionPage.version_id == archived_version.id
            ).order_by(PresentationVersionPage.page_number.asc()).all()
        
        if not pages_data:
            return None
        
        pages = []
        for page_data in pages_data:
            pages.append(
                PageContent(
                    page_number=page_data.page_number,
                    html_content=page_data.html_content,
                    page_title=page_data.page_title,
                )
            )
        
        return {"pages": pages, "total_pages": len(pages)}
        
    except Exception:
        return None


def get_active_presentation(
    conversation_id: str, db: Session, user_id: Optional[str] = None
) -> Optional[str]:
    """
    Get active presentation ID for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        db: Database session
        user_id: Optional - if provided use it, else use get_current_user_id() from context
        
    Returns:
        presentation_id or None
    """
    try:
        # Get user_id: explicit param or from context (for workflow)
        uid = user_id or get_current_user_id()
        
        # Get conversation with user authorization
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == uid  # Security: filter by user_id
        ).first()
        
        if not conversation or not conversation.active_presentation_id:
            return None
        
        return str(conversation.active_presentation_id)
        
    except Exception:
        return None


def set_active_presentation(conversation_id: str, presentation_id: str, db: Session) -> bool:
    """
    Set active presentation for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        presentation_id: UUID of presentation
        db: Database session
        
    Returns:
        True if successful
    """
    try:
        # Get current user for authorization check
        user_id = get_current_user_id()
        
        # Get conversation with user authorization
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not conversation:
            return False
        
        # Set active presentation
        conversation.active_presentation_id = presentation_id
        db.commit()
        
        return True
        
    except Exception:
        db.rollback()
        return False


def list_presentations(conversation_id: str, db: Session) -> List[PresentationDict]:
    """
    List all presentations for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        db: Database session
        
    Returns:
        List of Presentation dicts (without pages)
    """
    try:
        # Get current user for authorization check
        user_id = get_current_user_id()
        
        # Verify conversation belongs to user
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id  # Security: filter by user_id
        ).first()
        
        if not conversation:
            return []
        
        # Get presentations
        presentations_data = db.query(Presentation).filter(
            Presentation.conversation_id == conversation_id
        ).order_by(Presentation.created_at.desc()).all()
        
        if not presentations_data:
            return []
        
        presentations: List[PresentationDict] = []
        for p in presentations_data:
            presentations.append(
                {
                    "id": str(p.id),
                    "conversation_id": str(p.conversation_id),
                    "topic": p.topic,
                    "total_pages": p.total_pages,
                    "version": p.version,
                    "metadata": p.pres_metadata,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
            )
        
        return presentations
        
    except Exception:
        return []

