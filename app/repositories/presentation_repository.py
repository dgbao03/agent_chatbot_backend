"""
Presentation repository - Data access layer for presentations.
"""
from typing import Optional, List
from app.database.client import get_supabase_client
from app.config.pydantic_outputs import PageContent
from app.config.types import PresentationDict, PresentationVersionDict


def create_presentation(
    conversation_id: str,
    topic: str,
    pages: list,
    total_pages: int,
    user_request: str
) -> Optional[str]:
    """
    Create new presentation in Supabase.
    
    Args:
        conversation_id: UUID of conversation
        topic: Presentation topic
        pages: List of PageContent objects
        total_pages: Total number of pages
        user_request: User's request text
        
    Returns:
        presentation_id if successful, None otherwise
    """
    try:
        supabase = get_supabase_client()
        
        # Insert presentation metadata
        presentation_data = {
            "conversation_id": conversation_id,
            "topic": topic,
            "total_pages": total_pages,
            "version": 1,
            "metadata": {
                "user_request": user_request,
            },
        }
        
        response = supabase.from_("presentations").insert(presentation_data).execute()
        
        if not response.data or len(response.data) == 0:
            return None
        
        presentation_id = response.data[0]["id"]
        
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
                "conv_id": conversation_id,
                "p_id": presentation_id,
            },
        ).execute()
        
        return presentation_id
        
    except Exception:
        return None


def load_presentation(presentation_id: str) -> Optional[dict]:
    """
    Load presentation with current version pages.
    
    Args:
        presentation_id: UUID of presentation
        
    Returns:
        Dict with {id, topic, pages, total_pages, version} or None
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
            "topic": presentation["topic"],
            "pages": pages,
            "total_pages": presentation["total_pages"],
            "version": presentation["version"],
            "metadata": presentation.get("metadata", {}),
        }
        
    except Exception:
        return None


def update_presentation(
    presentation_id: str,
    topic: str,
    pages: list,
    total_pages: int,
    user_request: str
) -> Optional[int]:
    """
    Update presentation (archives current version, then updates).
    
    Args:
        presentation_id: UUID of presentation
        topic: New topic
        pages: New list of PageContent objects
        total_pages: New total pages count
        user_request: User's request text
        
    Returns:
        New version number if successful, None otherwise
    """
    try:
        supabase = get_supabase_client()
        
        # Get current version
        presentation = (
            supabase.from_("presentations")
            .select("version")
            .eq("id", presentation_id)
            .execute()
        )
        
        if not presentation.data or len(presentation.data) == 0:
            return None
        
        current_version = presentation.data[0]["version"]
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
        supabase.from_("presentations").update(
            {
                "topic": topic,
                "total_pages": total_pages,
                "version": new_version,
                "metadata": {
                    "user_request": user_request,
                },
            }
        ).eq("id", presentation_id).execute()
        
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
        
        return new_version
        
    except Exception:
        return None


def get_presentation_versions(presentation_id: str) -> Optional[list]:
    """
    Get all versions metadata for a presentation.
    
    Args:
        presentation_id: UUID of presentation
        
    Returns:
        List of version metadata dicts or None
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
        versions: List[PresentationVersionDict] = []
        for v in response.data:
            versions.append(
                {
                    "version": v["version"],
                    "is_current": v["is_current"],
                    "created_at": v["created_at"],
                    "user_request": v.get("user_request", ""),
                }
            )
        
        return versions
        
    except Exception:
        return None


def get_version_content(presentation_id: str, version: int) -> Optional[dict]:
    """
    Get pages content of a specific version.
    
    Args:
        presentation_id: UUID of presentation
        version: Version number
        
    Returns:
        Dict with {pages, total_pages} or None
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


def list_presentations(conversation_id: str) -> List[dict]:
    """
    List all presentations for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        
    Returns:
        List of presentation metadata dicts
    """
    try:
        supabase = get_supabase_client()
        
        response = (
            supabase.from_("presentations")
            .select("id, topic, total_pages, version, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        if not response.data:
            return []
        
        return response.data
        
    except Exception:
        return []

