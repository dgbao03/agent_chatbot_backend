"""
Presentation service - Business logic for presentation management.
"""
from typing import Optional, Tuple, List, Any
from sqlalchemy.orm import Session
from llama_index.core.llms import ChatMessage, MessageRole
from app.config.pydantic_outputs import SlideIntentOutput, PageContent
from app.config.prompts import PRESENTATION_INTENT_PROMPT
from app.config.types import Presentation as PresentationDict
from app.exceptions import LLMError, NotFoundError, DatabaseError
from app.config.settings import LLM_MODEL
from app.logging import get_logger
from app.repositories.presentation_repository import (
    list_presentations,
    get_active_presentation,
    load_presentation as repo_load_presentation,
    create_presentation as repo_create_presentation,
    update_presentation as repo_update_presentation,
    set_active_presentation as repo_set_active_presentation,
    get_presentation_versions as repo_get_presentation_versions,
    get_version_content as repo_get_version_content,
)

logger = get_logger(__name__)


async def detect_presentation_intent(
    user_input: str,
    conversation_id: str,
    user_id: str,
    llm: Any,
    db: Session,
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
        active_id = get_active_presentation(conversation_id, db, user_id=user_id)
        
        # Build context
        if not presentations:
            context = "No presentations exist in this conversation yet."
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
        logger.info("intent_detection_llm_call", model=LLM_MODEL, **token_info)
        
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
        raise LLMError(f"Intent detection failed: {e}") from e


# ---------------------------------------------------------------------------
# CRUD — used by routers/presentations.py
# ---------------------------------------------------------------------------

def get_presentation_versions(presentation_id: str, user_id: str, db) -> list:
    """
    Get all versions metadata for a presentation.

    Raises:
        NotFoundError: If presentation not found or not owned by user
        DatabaseError: On DB failure (propagated from repository)
    """
    versions = repo_get_presentation_versions(presentation_id, db, user_id=user_id)
    if not versions:
        raise NotFoundError("Presentation", presentation_id)
    return versions


def get_version_content(presentation_id: str, version: int, user_id: str, db: Session) -> dict:
    """
    Get pages content of a specific presentation version.

    Raises:
        NotFoundError: If version not found or presentation not owned by user
        DatabaseError: On DB failure (propagated from repository)
    """
    data = repo_get_version_content(presentation_id, version, db, user_id=user_id)
    if data is None:
        raise NotFoundError("Presentation version", str(version))
    return data


# ---------------------------------------------------------------------------
# Write operations — used by workflow
# ---------------------------------------------------------------------------

def get_presentation(presentation_id: str, db: Session) -> Optional[dict]:
    """
    Load a presentation with its pages by ID.

    Returns:
        PresentationWithPages dict, or None if not found
        DatabaseError: On DB failure (propagated from repository)
    """
    return repo_load_presentation(presentation_id, db)


def save_new_presentation(
    presentation: PresentationDict,
    pages: List[PageContent],
    user_request: str,
    db: Session,
) -> dict:
    """
    Create a new presentation and return the saved record.

    Raises:
        DatabaseError: If creation fails
    """
    saved = repo_create_presentation(
        presentation=presentation,
        pages=pages,
        user_request=user_request,
        db=db,
    )
    if not saved:
        raise DatabaseError("Failed to create presentation")
    return saved


def save_updated_presentation(
    presentation: PresentationDict,
    pages: List[PageContent],
    user_request: str,
    db: Session,
) -> dict:
    """
    Update an existing presentation and return the updated record.

    Raises:
        DatabaseError: If update fails
    """
    updated = repo_update_presentation(
        presentation=presentation,
        pages=pages,
        user_request=user_request,
        db=db,
    )
    if not updated:
        raise DatabaseError("Failed to update presentation")
    return updated


def activate_presentation(conversation_id: str, presentation_id: str, db: Session) -> None:
    """
    Set a presentation as the active one for a conversation.

    Raises:
        DatabaseError: On DB failure (propagated from repository)
    """
    repo_set_active_presentation(conversation_id, presentation_id, db)

