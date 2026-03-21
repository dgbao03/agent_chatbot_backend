"""
Presentation service - Business logic for presentation management.
"""
from typing import Optional, Tuple, List, Any

from llama_index.core.llms import ChatMessage, MessageRole

from app.types.llm.outputs import SlideIntentOutput, PageContent
from app.config.prompts import PRESENTATION_INTENT_PROMPT
from app.types.internal.presentation import Presentation as PresentationDict
from app.exceptions import LLMError, NotFoundError, DatabaseError
from app.config.settings import LLM_MODEL
from app.logging import get_logger
from app.repositories.presentation_repository import PresentationRepository

logger = get_logger(__name__)


class PresentationService:

    def __init__(self, presentation_repo: PresentationRepository):
        self.presentation_repo = presentation_repo

    async def detect_presentation_intent(
        self,
        user_input: str,
        conversation_id: str,
        user_id: str,
        llm: Any,
    ) -> Tuple[str, Optional[str], Optional[int]]:
        """
        Detect user intent for presentation actions.
        Uses LLM to classify: CREATE_NEW, EDIT_SPECIFIC, or EDIT_ACTIVE.

        Args:
            user_input: User's request
            conversation_id: UUID of conversation
            user_id: UUID of the user
            llm: LLM instance (passed from workflow)

        Returns:
            Tuple of (action, target_presentation_id, target_page_number)
        """
        try:
            presentations = self.presentation_repo.list_presentations(conversation_id, user_id)
            active_id = self.presentation_repo.get_active_presentation(conversation_id, user_id)

            if not presentations:
                context = "No presentations exist in this conversation yet."
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

            system_prompt = PRESENTATION_INTENT_PROMPT

            user_message = f"""
===== PRESENTATION INFORMATION =====
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

            if result.action in ["EDIT_SPECIFIC", "EDIT_ACTIVE"]:
                if not result.target_slide_id:
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

    def get_presentation_versions(self, presentation_id: str, user_id: str) -> list:
        """
        Get all versions metadata for a presentation.

        Raises:
            NotFoundError: If presentation not found or not owned by user
            DatabaseError: On DB failure (propagated from repository)
        """
        versions = self.presentation_repo.get_presentation_versions(presentation_id, user_id)
        if not versions:
            raise NotFoundError("Presentation", presentation_id)
        return versions

    def get_version_content(self, presentation_id: str, version: int, user_id: str) -> dict:
        """
        Get pages content of a specific presentation version.

        Raises:
            NotFoundError: If version not found or presentation not owned by user
            DatabaseError: On DB failure (propagated from repository)
        """
        data = self.presentation_repo.get_version_content(presentation_id, version, user_id)
        if data is None:
            raise NotFoundError("Presentation version", str(version))
        return data

    # ---------------------------------------------------------------------------
    # Write operations — used by workflow
    # ---------------------------------------------------------------------------

    def get_presentation(self, presentation_id: str, user_id: str) -> Optional[dict]:
        """
        Load a presentation with its pages by ID.

        Returns:
            PresentationWithPages dict, or None if not found
        """
        return self.presentation_repo.load_presentation(presentation_id, user_id)

    def save_new_presentation(
        self,
        presentation: PresentationDict,
        pages: List[PageContent],
        user_request: str,
        user_id: str,
    ) -> dict:
        """
        Create a new presentation and return the saved record.

        Raises:
            DatabaseError: If creation fails
        """
        saved = self.presentation_repo.create_presentation(
            presentation=presentation,
            pages=pages,
            user_request=user_request,
            user_id=user_id,
        )
        if not saved:
            raise DatabaseError("Failed to create presentation")
        return saved

    def save_updated_presentation(
        self,
        presentation: PresentationDict,
        pages: List[PageContent],
        user_request: str,
        user_id: str,
    ) -> dict:
        """
        Update an existing presentation and return the updated record.

        Raises:
            DatabaseError: If update fails
        """
        updated = self.presentation_repo.update_presentation(
            presentation=presentation,
            pages=pages,
            user_request=user_request,
            user_id=user_id,
        )
        if not updated:
            raise DatabaseError("Failed to update presentation")
        return updated

    def activate_presentation(
        self, conversation_id: str, presentation_id: str, user_id: str
    ) -> None:
        """
        Set a presentation as the active one for a conversation.

        Raises:
            DatabaseError: On DB failure (propagated from repository)
        """
        self.presentation_repo.set_active_presentation(conversation_id, presentation_id, user_id)
