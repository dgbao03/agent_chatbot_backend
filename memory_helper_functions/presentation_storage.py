"""
Presentation storage management using Supabase.
Replaces JSON file storage with database operations.
"""
from typing import Optional, Tuple, List
from config.supabase_client import get_supabase_client
from config.models import SlideOutput, SlideIntentOutput, PageContent
from llama_index.core.prompts import ChatPromptTemplate


def _create_presentation(
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
            'conversation_id': conversation_id,
            'topic': topic,
            'total_pages': total_pages,
            'version': 1,
            'metadata': {
                'user_request': user_request
            }
        }
        
        response = supabase.from_('presentations').insert(presentation_data).execute()
        
        if not response.data or len(response.data) == 0:
            print("❌ Failed to create presentation")
            return None
        
        presentation_id = response.data[0]['id']
        
        # Insert pages
        pages_data = []
        for page in pages:
            pages_data.append({
                'presentation_id': presentation_id,
                'page_number': page.page_number,
                'html_content': page.html_content,
                'page_title': page.page_title
            })
        
        if pages_data:
            supabase.from_('presentation_pages').insert(pages_data).execute()
        
        # Set as active presentation using RPC
        supabase.rpc('set_active_presentation', {
            'conv_id': conversation_id,
            'p_id': presentation_id
        }).execute()
        
        print(f"✅ Created presentation: {presentation_id} ({topic})")
        return presentation_id
        
    except Exception as e:
        print(f"❌ Error creating presentation: {e}")
        return None


def _load_presentation(presentation_id: str) -> Optional[dict]:
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
        response = supabase.from_('presentations').select('*').eq('id', presentation_id).execute()
        
        if not response.data or len(response.data) == 0:
            print(f"❌ Presentation {presentation_id} not found")
            return None
        
        presentation = response.data[0]
        
        # Get pages using RPC
        pages_response = supabase.rpc('get_presentation_pages', {'p_id': presentation_id}).execute()
        
        pages = []
        if pages_response.data:
            for page_data in pages_response.data:
                pages.append(PageContent(
                    page_number=page_data['page_number'],
                    html_content=page_data['html_content'],
                    page_title=page_data.get('page_title')
                ))
        
        return {
            'id': presentation['id'],
            'topic': presentation['topic'],
            'pages': pages,
            'total_pages': presentation['total_pages'],
            'version': presentation['version'],
            'metadata': presentation.get('metadata', {})
        }
        
    except Exception as e:
        print(f"❌ Error loading presentation: {e}")
        return None


def _update_presentation(
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
        presentation = supabase.from_('presentations').select('version').eq('id', presentation_id).execute()
        
        if not presentation.data or len(presentation.data) == 0:
            print(f"❌ Presentation {presentation_id} not found")
            return None
        
        current_version = presentation.data[0]['version']
        new_version = current_version + 1
        
        # Archive current version using RPC (returns version_id UUID)
        archive_response = supabase.rpc('archive_presentation_version', {'p_id': presentation_id}).execute()
        
        if not archive_response.data:
            print(f"⚠️ Warning: Archive returned no version_id")
        
        # Delete old pages (will be replaced)
        supabase.from_('presentation_pages').delete().eq('presentation_id', presentation_id).execute()
        
        # Update presentation metadata
        supabase.from_('presentations').update({
            'topic': topic,
            'total_pages': total_pages,
            'version': new_version,
            'metadata': {
                'user_request': user_request
            }
        }).eq('id', presentation_id).execute()
        
        # Insert new pages
        pages_data = []
        for page in pages:
            pages_data.append({
                'presentation_id': presentation_id,
                'page_number': page.page_number,
                'html_content': page.html_content,
                'page_title': page.page_title
            })
        
        if pages_data:
            supabase.from_('presentation_pages').insert(pages_data).execute()
        
        print(f"✅ Updated presentation: {presentation_id} (v{current_version} → v{new_version})")
        return new_version
        
    except Exception as e:
        print(f"❌ Error updating presentation: {e}")
        return None


def _get_presentation_versions(presentation_id: str) -> Optional[list]:
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
        response = supabase.rpc('get_presentation_versions', {'p_id': presentation_id}).execute()
        
        if not response.data:
            return []
        
        # Convert to expected format
        versions = []
        for v in response.data:
            versions.append({
                'version': v['version'],
                'is_current': v['is_current'],
                'timestamp': v['created_at'],
                'user_request': v.get('user_request', '')
            })
        
        return versions
        
    except Exception as e:
        print(f"❌ Error getting versions: {e}")
        return None


def _get_version_content(presentation_id: str, version: int) -> Optional[dict]:
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
        presentation = supabase.from_('presentations').select('version, total_pages').eq('id', presentation_id).execute()
        
        if not presentation.data or len(presentation.data) == 0:
            print(f"❌ Presentation {presentation_id} not found")
            return None
        
        current_version = presentation.data[0]['version']
        
        # If requesting current version, load from presentation_pages
        if version == current_version:
            print(f"📄 Loading CURRENT version {version} from presentation_pages")
            pages_response = supabase.rpc('get_presentation_pages', {'p_id': presentation_id}).execute()
        else:
            # Otherwise load from archived versions
            print(f"📦 Loading ARCHIVED version {version} from presentation_versions")
            pages_response = supabase.rpc('get_version_pages', {
                'p_id': presentation_id,
                'v_num': version
            }).execute()
        
        if not pages_response.data:
            print(f"❌ No pages found for version {version}")
            return None
        
        pages = []
        for page_data in pages_response.data:
            pages.append(PageContent(
                page_number=page_data['page_number'],
                html_content=page_data['html_content'],
                page_title=page_data.get('page_title')
            ))
        
        return {
            'pages': pages,
            'total_pages': len(pages)
        }
        
    except Exception as e:
        print(f"❌ Error getting version content: {e}")
        return None


def _get_active_presentation(conversation_id: str) -> Optional[str]:
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
        response = supabase.rpc('get_active_presentation', {'conv_id': conversation_id}).execute()
        
        # RPC returns UUID directly
        return response.data if response.data else None
        
    except Exception as e:
        print(f"❌ Error getting active presentation: {e}")
        return None


def _set_active_presentation(conversation_id: str, presentation_id: str) -> bool:
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
        supabase.rpc('set_active_presentation', {
            'conv_id': conversation_id,
            'p_id': presentation_id
        }).execute()
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting active presentation: {e}")
        return False


def _list_presentations(conversation_id: str) -> List[dict]:
    """
    List all presentations for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        
    Returns:
        List of presentation metadata dicts
    """
    try:
        supabase = get_supabase_client()
        
        response = supabase.from_('presentations').select('id, topic, total_pages, version, created_at').eq(
            'conversation_id', conversation_id
        ).order('created_at', desc=True).execute()
        
        if not response.data:
            return []
        
        return response.data
        
    except Exception as e:
        print(f"❌ Error listing presentations: {e}")
        return []


async def _detect_intent(
    user_input: str,
    conversation_id: str,
    llm
) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Detect user intent for presentation actions.
    Uses LLM to classify: CREATE_NEW, EDIT_SPECIFIC, or EDIT_ACTIVE.
    
    Args:
        user_input: User's request
        conversation_id: UUID of conversation
        llm: LLM instance
        
    Returns:
        Tuple of (action, target_presentation_id, target_page_number)
    """
    try:
        # Get presentations list for this conversation
        presentations = _list_presentations(conversation_id)
        active_id = _get_active_presentation(conversation_id)
        
        # Build context
        if not presentations:
            context = "Chưa có presentation nào trong conversation."
        else:
            context = "===== AVAILABLE PRESENTATIONS =====\n\n"
            for i, pres in enumerate(presentations, 1):
                is_active = " (ACTIVE)" if pres['id'] == active_id else ""
                context += f"Presentation {i}{is_active}:\n"
                context += f"  - ID: {pres['id']}\n"
                context += f"  - Topic: {pres['topic']}\n"
                context += f"  - Pages: {pres['total_pages']}\n\n"
            
            if active_id:
                context += f"Currently active: {active_id}\n"
        
        # System prompt
        system_prompt = """You are a presentation intent classifier.

Your task is to analyze user input and determine:
1. What action: CREATE_NEW, EDIT_SPECIFIC, or EDIT_ACTIVE
2. Which presentation to target (if editing)
3. Which page to target (if editing specific page)

RULES (in priority order):

1. CREATE_NEW - When user wants a NEW presentation:
   - Keywords: "tạo", "create", "make", "new slide/presentation"
   - target_presentation_id: null
   - target_page_number: null

2. EDIT_SPECIFIC - When user references a SPECIFIC presentation (HIGHEST PRIORITY for edits):
   - **IMPORTANT**: If user request contains ANY part of a presentation topic name, this is EDIT_SPECIFIC!
   - By number: "presentation 1", "slide 2", "slide thứ 1"
   - By topic name (full or partial): 
     * "sửa slide sự biến mất" → match "Sự Biến Mất"
     * "edit presentation về AI" → match "Artificial Intelligence"
     * "slide chinh phục" → match "Chinh Phục Khó Khăn"
   - **Rule**: Compare user request with ALL presentation topics, case-insensitive
   - If ANY topic matches (even partially) → EDIT_SPECIFIC
   - target_presentation_id: the matched presentation's ID
   - target_page_number: page number if mentioned, else null

3. EDIT_ACTIVE - When user wants to edit WITHOUT any specific reference:
   - **ONLY use this if NO presentation topic/name/number is mentioned**
   - Has edit keywords: "sửa", "edit", "change", "add", "thêm", "đổi"
   - BUT no presentation identifier in request
   - target_presentation_id: active presentation's ID
   - target_page_number: page number if mentioned, else null

PAGE-SPECIFIC EDIT:
- If user mentions page number (e.g., "sửa trang 2", "edit page 3"):
  → Set target_page_number to that number
  → Edit ONLY that page
- Otherwise: target_page_number = null (edit entire presentation)

Always provide clear reasoning."""

        user_message = f"""
===== AVAILABLE PRESENTATIONS =====
{context}

===== USER REQUEST =====
{user_input}

===== YOUR TASK =====
Analyze the user request and:
1. Check if user mentions ANY presentation topic name (even partially) → EDIT_SPECIFIC
2. Check if user mentions presentation number (e.g., "slide 1", "presentation 2") → EDIT_SPECIFIC
3. If NO specific reference but has edit keywords → EDIT_ACTIVE
4. If user wants new presentation → CREATE_NEW

Output:
1. Action? (CREATE_NEW, EDIT_SPECIFIC, EDIT_ACTIVE)
2. Which presentation ID? (provide exact UUID if editing)
3. Which page? (provide number if editing specific page, else null)

IMPORTANT: Carefully match user request with presentation topics!
"""
        
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_message)
        ])
        
        # Call LLM with structured output
        result = await llm.astructured_predict(
            SlideIntentOutput,
            prompt
        )
        
        # Validate and fix result
        if result.action in ["EDIT_SPECIFIC", "EDIT_ACTIVE"]:
            if not result.target_slide_id:
                print("⚠️ LLM didn't provide target, using active presentation")
                result.target_slide_id = active_id
        
        if result.action == "CREATE_NEW":
            result.target_slide_id = None
            result.target_page_number = None

        print(context)
        
        return (result.action, result.target_slide_id, result.target_page_number)
        
    except Exception as e:
        print(f"❌ Intent detection failed: {e}")
        raise ValueError(f"Intent detection failed: {e}") from e
