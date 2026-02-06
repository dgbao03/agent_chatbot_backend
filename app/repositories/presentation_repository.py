"""
Presentation repository - Data access layer for presentations.
"""
from typing import Optional, List
from app.database.client import get_supabase_client
from app.config.models import PageContent
from app.config.constants import (
    TABLE_PRESENTATIONS,
    TABLE_PRESENTATION_PAGES,
    FIELD_CONVERSATION_ID,
    FIELD_TOPIC,
    FIELD_TOTAL_PAGES,
    FIELD_VERSION,
    FIELD_METADATA,
    FIELD_PRESENTATION_ID,
    FIELD_PAGE_NUMBER,
    FIELD_HTML_CONTENT,
    FIELD_PAGE_TITLE,
    FIELD_ID,
    FIELD_CREATED_AT,
    METADATA_KEY_USER_REQUEST,
    RPC_SET_ACTIVE_PRESENTATION,
    RPC_GET_PRESENTATION_PAGES,
    RPC_GET_VERSION_PAGES,
    RPC_GET_PRESENTATION_VERSIONS,
    RPC_ARCHIVE_PRESENTATION_VERSION,
    RPC_GET_ACTIVE_PRESENTATION,
    RPC_PARAM_CONV_ID,
    RPC_PARAM_P_ID,
    RPC_PARAM_V_NUM,
    DEFAULT_PRESENTATION_VERSION
)
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
            FIELD_CONVERSATION_ID: conversation_id,
            FIELD_TOPIC: topic,
            FIELD_TOTAL_PAGES: total_pages,
            FIELD_VERSION: DEFAULT_PRESENTATION_VERSION,
            FIELD_METADATA: {
                METADATA_KEY_USER_REQUEST: user_request
            }
        }
        
        response = supabase.from_(TABLE_PRESENTATIONS).insert(presentation_data).execute()
        
        if not response.data or len(response.data) == 0:
            return None
        
        presentation_id = response.data[0][FIELD_ID]
        
        # Insert pages
        pages_data = []
        for page in pages:
            pages_data.append({
                FIELD_PRESENTATION_ID: presentation_id,
                FIELD_PAGE_NUMBER: page.page_number,
                FIELD_HTML_CONTENT: page.html_content,
                FIELD_PAGE_TITLE: page.page_title
            })
        
        if pages_data:
            supabase.from_(TABLE_PRESENTATION_PAGES).insert(pages_data).execute()
        
        # Set as active presentation using RPC
        supabase.rpc(
            RPC_SET_ACTIVE_PRESENTATION,
            {
                RPC_PARAM_CONV_ID: conversation_id,
                RPC_PARAM_P_ID: presentation_id,
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
        response = supabase.from_(TABLE_PRESENTATIONS).select('*').eq(FIELD_ID, presentation_id).execute()
        
        if not response.data or len(response.data) == 0:
            return None
        
        presentation = response.data[0]
        
        # Get pages using RPC
        pages_response = supabase.rpc(RPC_GET_PRESENTATION_PAGES, {RPC_PARAM_P_ID: presentation_id}).execute()
        
        pages = []
        if pages_response.data:
            for page_data in pages_response.data:
                pages.append(PageContent(
                    page_number=page_data[FIELD_PAGE_NUMBER],
                    html_content=page_data[FIELD_HTML_CONTENT],
                    page_title=page_data.get(FIELD_PAGE_TITLE)
                ))
        
        return {
            FIELD_ID: presentation[FIELD_ID],
            FIELD_TOPIC: presentation[FIELD_TOPIC],
            'pages': pages,
            FIELD_TOTAL_PAGES: presentation[FIELD_TOTAL_PAGES],
            FIELD_VERSION: presentation[FIELD_VERSION],
            FIELD_METADATA: presentation.get(FIELD_METADATA, {})
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
        presentation = supabase.from_(TABLE_PRESENTATIONS).select(FIELD_VERSION).eq(FIELD_ID, presentation_id).execute()
        
        if not presentation.data or len(presentation.data) == 0:
            return None
        
        current_version = presentation.data[0][FIELD_VERSION]
        new_version = current_version + 1
        
        # Archive current version using RPC (returns version_id UUID)
        archive_response = supabase.rpc(
            RPC_ARCHIVE_PRESENTATION_VERSION, {RPC_PARAM_P_ID: presentation_id}
        ).execute()
        
        if not archive_response.data:
            # Archive returned no version_id; continue with update
            pass
        
        # Delete old pages (will be replaced)
        supabase.from_(TABLE_PRESENTATION_PAGES).delete().eq(FIELD_PRESENTATION_ID, presentation_id).execute()
        
        # Update presentation metadata
        supabase.from_(TABLE_PRESENTATIONS).update({
            FIELD_TOPIC: topic,
            FIELD_TOTAL_PAGES: total_pages,
            FIELD_VERSION: new_version,
            FIELD_METADATA: {
                METADATA_KEY_USER_REQUEST: user_request
            }
        }).eq(FIELD_ID, presentation_id).execute()
        
        # Insert new pages
        pages_data = []
        for page in pages:
            pages_data.append({
                FIELD_PRESENTATION_ID: presentation_id,
                FIELD_PAGE_NUMBER: page.page_number,
                FIELD_HTML_CONTENT: page.html_content,
                FIELD_PAGE_TITLE: page.page_title
            })
        
        if pages_data:
            supabase.from_(TABLE_PRESENTATION_PAGES).insert(pages_data).execute()
        
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
        response = supabase.rpc(RPC_GET_PRESENTATION_VERSIONS, {RPC_PARAM_P_ID: presentation_id}).execute()
        
        if not response.data:
            return []
        
        # Convert to expected format
        versions: List[PresentationVersionDict] = []
        for v in response.data:
            versions.append({
                FIELD_VERSION: v[FIELD_VERSION],
                'is_current': v['is_current'],
                FIELD_CREATED_AT: v[FIELD_CREATED_AT],
                METADATA_KEY_USER_REQUEST: v.get(METADATA_KEY_USER_REQUEST, '')
            })
        
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
        presentation = supabase.from_(TABLE_PRESENTATIONS).select(
            f'{FIELD_VERSION}, {FIELD_TOTAL_PAGES}'
        ).eq(FIELD_ID, presentation_id).execute()
        
        if not presentation.data or len(presentation.data) == 0:
            return None
        
        current_version = presentation.data[0][FIELD_VERSION]
        
        # If requesting current version, load from presentation_pages
        if version == current_version:
            pages_response = supabase.rpc(
                RPC_GET_PRESENTATION_PAGES, {RPC_PARAM_P_ID: presentation_id}
            ).execute()
        else:
            # Otherwise load from archived versions
            pages_response = supabase.rpc(
                RPC_GET_VERSION_PAGES,
                {
                    RPC_PARAM_P_ID: presentation_id,
                    RPC_PARAM_V_NUM: version,
                },
            ).execute()
        
        if not pages_response.data:
            return None
        
        pages = []
        for page_data in pages_response.data:
            pages.append(PageContent(
                page_number=page_data[FIELD_PAGE_NUMBER],
                html_content=page_data[FIELD_HTML_CONTENT],
                page_title=page_data.get(FIELD_PAGE_TITLE)
            ))
        
        return {'pages': pages, FIELD_TOTAL_PAGES: len(pages)}
        
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
            RPC_GET_ACTIVE_PRESENTATION, {RPC_PARAM_CONV_ID: conversation_id}
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
            RPC_SET_ACTIVE_PRESENTATION,
            {
                RPC_PARAM_CONV_ID: conversation_id,
                RPC_PARAM_P_ID: presentation_id,
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
        
        response = supabase.from_(TABLE_PRESENTATIONS).select(f'{FIELD_ID}, {FIELD_TOPIC}, {FIELD_TOTAL_PAGES}, {FIELD_VERSION}, {FIELD_CREATED_AT}').eq(
            FIELD_CONVERSATION_ID, conversation_id
        ).order(FIELD_CREATED_AT, desc=True).execute()
        
        if not response.data:
            return []
        
        return response.data
        
    except Exception:
        return []

