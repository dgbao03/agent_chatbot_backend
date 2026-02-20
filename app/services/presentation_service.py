"""
Presentation service - Business logic for presentation management.
"""
from typing import Optional, Tuple
from llama_index.core.llms import ChatMessage, MessageRole
from app.config.pydantic_outputs import SlideIntentOutput
from app.config.prompts import PRESENTATION_INTENT_PROMPT
from app.logging import get_logger
from app.repositories.presentation_repository import (
    list_presentations,
    get_active_presentation
)

logger = get_logger(__name__)


async def detect_presentation_intent(
    user_input: str,
    conversation_id: str,
    llm,
    db
) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Detect user intent for presentation actions.
    Uses LLM to classify: CREATE_NEW, EDIT_SPECIFIC, or EDIT_ACTIVE.
    
    Args:
        user_input: User's request
        conversation_id: UUID of conversation
        llm: LLM instance
        db: Database session
        
    Returns:
        Tuple of (action, target_presentation_id, target_page_number)
    """
    try:
        # Get presentations list for this conversation
        presentations = list_presentations(conversation_id, db)
        active_id = get_active_presentation(conversation_id, db)
        
        # Build context
        if not presentations:
            context = "Chưa có presentation nào trong conversation."
        else:
            context = "===== AVAILABLE PRESENTATIONS =====\n\n"
            for i, pres in enumerate(presentations, 1):
                # Direct access is safe - list_presentations() always returns objects with these fields
                is_active = " (ACTIVE)" if pres["id"] == active_id else ""
                context += f"Presentation {i}{is_active}:\n"
                context += f"  - ID: {pres['id']}\n"
                context += f"  - Topic: {pres['topic']}\n"
                context += f"  - Pages: {pres['total_pages']}\n\n"
            
            if active_id:
                context += f"Currently active: {active_id}\n"
        
        # System prompt
        system_prompt = PRESENTATION_INTENT_PROMPT

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
        
        # Call LLM with structured output
        intent_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_message),
        ]
        resp = await llm.achat(intent_messages, response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "SlideIntentOutput",
                "schema": SlideIntentOutput.model_json_schema(),
            },
        })
        result = SlideIntentOutput.model_validate_json(resp.message.content)

        token_info = {}
        raw_resp = getattr(resp, "raw", None)
        if raw_resp and hasattr(raw_resp, "usage") and raw_resp.usage:
            token_info = {
                "prompt_tokens": raw_resp.usage.prompt_tokens,
                "completion_tokens": raw_resp.usage.completion_tokens,
                "total_tokens": raw_resp.usage.total_tokens,
            }
        logger.info("intent_detection_llm_call", model="gpt-4o-mini", **token_info)
        
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

