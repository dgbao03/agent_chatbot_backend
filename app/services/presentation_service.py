"""
Presentation service - Business logic for presentation management.
"""
from typing import Optional, Tuple
from llama_index.core.prompts import ChatPromptTemplate
from app.config.models import SlideIntentOutput
from app.repositories.presentation_repository import (
    list_presentations,
    get_active_presentation
)


async def detect_presentation_intent(
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
        presentations = list_presentations(conversation_id)
        active_id = get_active_presentation(conversation_id)
        
        # Build context
        if not presentations:
            context = "Chưa có presentation nào trong conversation."
        else:
            context = "===== AVAILABLE PRESENTATIONS =====\n\n"
            for i, pres in enumerate(presentations, 1):
                is_active = " (ACTIVE)" if pres["id"] == active_id else ""
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
                # If LLM doesn't provide target, fallback to active presentation
                result.target_slide_id = active_id
        
        if result.action == "CREATE_NEW":
            result.target_slide_id = None
            result.target_page_number = None
        
        return (result.action, result.target_slide_id, result.target_page_number)
        
    except Exception as e:
        raise ValueError(f"Intent detection failed: {e}") from e

