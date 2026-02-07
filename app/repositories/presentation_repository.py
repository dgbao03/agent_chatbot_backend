"""
Presentation repository - Data access layer for presentations.
"""
from typing import Optional, List
from app.database.client import get_supabase_client
from app.config.pydantic_outputs import PageContent
from app.config.types import (
    Presentation,
    PresentationWithPages,
    PresentationVersion,
    VersionContent,
)


def create_presentation(
    presentation: Presentation,
    pages: List[PageContent],
    user_request: str
) -> Optional[Presentation]:
    """
    Create new presentation in Supabase.
    
    Args:
        presentation: Presentation object with conversation_id, topic, total_pages
        pages: List of PageContent objects
        user_request: User's request text
        
    Returns:
        Presentation object with id and created_at set if successful, None otherwise
    """
    try:
        supabase = get_supabase_client()
        
        # Insert presentation metadata
        presentation_data = {
            "conversation_id": presentation["conversation_id"],
            "topic": presentation["topic"],
            "total_pages": presentation["total_pages"],
            "version": presentation.get("version", 1),
            "metadata": {
                "user_request": user_request,
            },
        }
        
        response = supabase.from_("presentations").insert(presentation_data).execute()
        
        if not response.data or len(response.data) == 0:
            return None
        
        saved_presentation = response.data[0]
        presentation_id = saved_presentation["id"]
        
        # Insert pages
        pages_data = []
        for page in pages:
            pages_data.append(
                {
                    "presentation_id": presentation_id,
                    "page_number": page.page_number,
                    "html_content": page.html_content,
                    "page_title": page.page_title,
                }
            )
        
        if pages_data:
            supabase.from_("presentation_pages").insert(pages_data).execute()
        
        # Set as active presentation using RPC
        supabase.rpc(
            "set_active_presentation",
            {
                "conv_id": presentation["conversation_id"],
                "p_id": presentation_id,
            },
        ).execute()
        
        return {
            "id": saved_presentation["id"],
            "conversation_id": saved_presentation["conversation_id"],
            "topic": saved_presentation["topic"],
            "total_pages": saved_presentation["total_pages"],
            "version": saved_presentation.get("version", 1),
            "metadata": saved_presentation.get("metadata", {}),
            "created_at": saved_presentation.get("created_at"),
            "updated_at": saved_presentation.get("updated_at"),
        }
        
    except Exception:
        return None


def load_presentation(presentation_id: str) -> Optional[PresentationWithPages]:
    """
    Load presentation with current version pages.
    
    Args:
        presentation_id: UUID of presentation
        
    Returns:
        PresentationWithPages object with pages included, or None
    """
    try:
        supabase = get_supabase_client()
        
        # Get presentation metadata
        response = (
            supabase.from_("presentations")
            .select("*")
            .eq("id", presentation_id)
            .execute()
        )
        
        if not response.data or len(response.data) == 0:
            return None
        
        presentation = response.data[0]
        
        # Get pages using RPC
        pages_response = supabase.rpc(
            "get_presentation_pages", {"p_id": presentation_id}
        ).execute()
        
        pages = []
        if pages_response.data:
            for page_data in pages_response.data:
                pages.append(
                    PageContent(
                        page_number=page_data["page_number"],
                        html_content=page_data["html_content"],
                        page_title=page_data.get("page_title"),
                    )
                )
        
        return {
            "id": presentation["id"],
            "conversation_id": presentation["conversation_id"],
            "topic": presentation["topic"],
            "pages": pages,
            "total_pages": presentation["total_pages"],
            "version": presentation["version"],
            "metadata": presentation.get("metadata", {}),
            "created_at": presentation.get("created_at"),
            "updated_at": presentation.get("updated_at"),
        }
        
    except Exception:
        return None


def update_presentation(
    presentation: Presentation,
    pages: List[PageContent],
    user_request: str
) -> Optional[Presentation]:
    """
    Update presentation (archives current version, then updates).
    
    Args:
        presentation: Presentation object with id, topic, total_pages
        pages: New list of PageContent objects
        user_request: User's request text
        
    Returns:
        Presentation object with updated version if successful, None otherwise
    """
    try:
        supabase = get_supabase_client()
        presentation_id = presentation["id"]
        
        if not presentation_id:
            return None
        
        # Get current version
        current_presentation = (
            supabase.from_("presentations")
            .select("version")
            .eq("id", presentation_id)
            .execute()
        )
        
        if not current_presentation.data or len(current_presentation.data) == 0:
            return None
        
        current_version = current_presentation.data[0]["version"]
        new_version = current_version + 1
        
        # Archive current version using RPC (returns version_id UUID)
        archive_response = supabase.rpc(
            "archive_presentation_version", {"p_id": presentation_id}
        ).execute()
        
        if not archive_response.data:
            # Archive returned no version_id; continue with update
            pass
        
        # Delete old pages (will be replaced)
        supabase.from_("presentation_pages").delete().eq(
            "presentation_id", presentation_id
        ).execute()
        
        # Update presentation metadata
        update_response = supabase.from_("presentations").update(
            {
                "topic": presentation["topic"],
                "total_pages": presentation["total_pages"],
                "version": new_version,
                "metadata": {
                    "user_request": user_request,
                },
            }
        ).eq("id", presentation_id).execute()
        
        if not update_response.data or len(update_response.data) == 0:
            return None
        
        # Insert new pages
        pages_data = []
        for page in pages:
            pages_data.append(
                {
                    "presentation_id": presentation_id,
                    "page_number": page.page_number,
                    "html_content": page.html_content,
                    "page_title": page.page_title,
                }
            )
        
        if pages_data:
            supabase.from_("presentation_pages").insert(pages_data).execute()
        
        updated_presentation = update_response.data[0]
        return {
            "id": updated_presentation["id"],
            "conversation_id": updated_presentation["conversation_id"],
            "topic": updated_presentation["topic"],
            "total_pages": updated_presentation["total_pages"],
            "version": updated_presentation["version"],
            "metadata": updated_presentation.get("metadata", {}),
            "created_at": updated_presentation.get("created_at"),
            "updated_at": updated_presentation.get("updated_at"),
        }
        
    except Exception:
        return None


def get_presentation_versions(presentation_id: str) -> List[PresentationVersion]:
    """
    Get all versions metadata for a presentation.
    
    Args:
        presentation_id: UUID of presentation
        
    Returns:
        List of PresentationVersion objects
    """
    try:
        supabase = get_supabase_client()
        
        # Use RPC to get versions
        response = supabase.rpc(
            "get_presentation_versions", {"p_id": presentation_id}
        ).execute()
        
        if not response.data:
            return []
        
        # Convert to expected format
        versions: List[PresentationVersion] = []
        for v in response.data:
            versions.append(
                {
                    "version": v["version"],
                    "total_pages": v.get("total_pages", 0),
                    "is_current": v["is_current"],
                    "created_at": v["created_at"],
                    "user_request": v.get("user_request"),
                }
            )
        
        return versions
        
    except Exception:
        return []


def get_version_content(presentation_id: str, version: int) -> Optional[VersionContent]:
    """
    Get pages content of a specific version.
    
    Args:
        presentation_id: UUID of presentation
        version: Version number
        
    Returns:
        VersionContent object with pages and total_pages, or None
    """
    try:
        supabase = get_supabase_client()
        
        # Check if requested version is current version
        presentation = (
            supabase.from_("presentations")
            .select("version, total_pages")
            .eq("id", presentation_id)
            .execute()
        )
        
        if not presentation.data or len(presentation.data) == 0:
            return None
        
        current_version = presentation.data[0]["version"]
        
        # If requesting current version, load from presentation_pages
        if version == current_version:
            pages_response = supabase.rpc(
                "get_presentation_pages", {"p_id": presentation_id}
            ).execute()
        else:
            # Otherwise load from archived versions
            pages_response = supabase.rpc(
                "get_version_pages",
                {"p_id": presentation_id, "v_num": version},
            ).execute()
        
        if not pages_response.data:
            return None
        
        pages = []
        for page_data in pages_response.data:
            pages.append(
                PageContent(
                    page_number=page_data["page_number"],
                    html_content=page_data["html_content"],
                    page_title=page_data.get("page_title"),
                )
            )
        
        return {"pages": pages, "total_pages": len(pages)}
        
    except Exception:
        return None


def get_active_presentation(conversation_id: str) -> Optional[str]:
    """
    Get active presentation ID for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        
    Returns:
        presentation_id or None
    """
    try:
        supabase = get_supabase_client()
        
        # Use RPC to get active presentation
        response = supabase.rpc(
            "get_active_presentation", {"conv_id": conversation_id}
        ).execute()
        
        # RPC returns UUID directly
        return response.data if response.data else None
        
    except Exception:
        return None


def set_active_presentation(conversation_id: str, presentation_id: str) -> bool:
    """
    Set active presentation for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        presentation_id: UUID of presentation
        
    Returns:
        True if successful
    """
    try:
        supabase = get_supabase_client()
        
        # Use RPC to set active presentation
        supabase.rpc(
            "set_active_presentation",
            {
                "conv_id": conversation_id,
                "p_id": presentation_id,
            },
        ).execute()
        
        return True
        
    except Exception:
        return False


def list_presentations(conversation_id: str) -> List[Presentation]:
    """
    List all presentations for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        
    Returns:
        List of Presentation objects (without pages)
    """
    try:
        supabase = get_supabase_client()
        
        response = (
            supabase.from_("presentations")
            .select("id, conversation_id, topic, total_pages, version, metadata, created_at, updated_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        if not response.data:
            return []
        
        presentations: List[Presentation] = []
        for p in response.data:
            presentations.append(
                {
                    "id": p["id"],
                    "conversation_id": p["conversation_id"],
                    "topic": p["topic"],
                    "total_pages": p["total_pages"],
                    "version": p["version"],
                    "metadata": p.get("metadata"),
                    "created_at": p.get("created_at"),
                    "updated_at": p.get("updated_at"),
                }
            )
        
        return presentations
        
    except Exception:
        return []

