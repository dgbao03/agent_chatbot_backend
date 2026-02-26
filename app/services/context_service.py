"""
Context Service - Assembles LLM system-prompt strings for each workflow step.

Centralises all context-building logic so that workflow steps contain only
LLM calls and event routing, not string-assembly details.
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from llama_index.core.llms import ChatMessage

from app.config.prompts import (
    ROUTER_ANSWER_PROMPT,
    TOOL_BEST_PRACTICES,
    SLIDE_GENERATION_PROMPT,
)
from app.config.pydantic_outputs import PageContent
from app.repositories.summary_repository import load_summary
from app.repositories.user_facts_repository import load_user_facts
from app.tools import registry
from app.logging import get_logger

logger = get_logger(__name__)


def _get_user_facts_text(user_id: str, db: Session) -> str:
    """Build user facts string for injection into system prompt."""
    try:
        facts = load_user_facts(user_id, db)
        if not facts:
            return ""
        lines = ["USER FACTS (Information about the user):"]
        for fact in facts:
            key = fact.get("key", "")
            value = fact.get("value", "")
            if key and value:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception:
        logger.exception("get_user_facts_text_failed")
        return ""


def build_chat_context(
    user_id: str,
    conversation_id: str,
    history: List[ChatMessage],
    db: Session,
) -> str:
    """
    Assemble the system_content string for the route_and_answer workflow step.

    Layers included (in order):
      1. Base ROUTER_ANSWER_PROMPT
      2. Tool instructions (per-tool plain-text usage guide)
      3. TOOL_BEST_PRACTICES
      4. User facts (personalisation, if any)
      5. Recent chat history (from ChatMemoryBuffer.get())
      6. Conversation summary (if one exists in DB)

    Args:
        user_id: UUID of the authenticated user
        conversation_id: UUID of the conversation
        history: Hydrated message list from ChatMemoryBuffer.get()
        db: Database session

    Returns:
        Complete system_content string ready to inject into LLM messages
    """
    system_content = ROUTER_ANSWER_PROMPT + "\n\n"

    tool_instructions = registry.get_tool_instructions()
    if tool_instructions:
        system_content += tool_instructions + "\n\n"
    system_content += TOOL_BEST_PRACTICES + "\n\n"

    user_facts_text = _get_user_facts_text(user_id, db)
    if user_facts_text:
        system_content += user_facts_text + "\n\n"

    if history:
        history_text = "\n===== RECENT CHAT HISTORY =====\n"
        for msg in history:
            history_text += f"{msg.role.value}: {msg.content}\n"
        system_content += "\n\n" + history_text

    summary_data = load_summary(conversation_id, user_id, db)
    if summary_data.get("summary_content"):
        system_content += (
            "\n===== CONVERSATION SUMMARY =====\n"
            f"{summary_data['summary_content']}"
        )

    return system_content


def build_slide_context(
    conversation_id: str,
    user_id: str,
    history: List[ChatMessage],
    action: str,
    previous_pages: Optional[List[PageContent]],
    total_pages: Optional[int],
    target_page_number: Optional[int],
    db: Session,
) -> Tuple[str, Optional[int]]:
    """
    Assemble the system_content string for the generate_slide workflow step.

    Layers included (in order):
      1. Base SLIDE_GENERATION_PROMPT
      2. Recent chat history
      3. Conversation summary (if any)
      4. Previous slide pages — either a single target page or all pages,
         with matching INSTRUCTIONS block appended
      5. Final action instruction (CREATE_NEW / EDIT page / EDIT entire)

    Note: target_page_number may be reset to None if the requested page is not
    found in previous_pages. The effective value is returned as the second
    element of the tuple so the caller can use it for page-merging logic.

    Args:
        conversation_id: UUID of the conversation
        user_id: UUID of the user (for ownership check)
        history: Hydrated message list from ChatMemoryBuffer.get()
        action: "CREATE_NEW", "EDIT_SPECIFIC", or "EDIT_ACTIVE"
        previous_pages: Existing slide pages, or None for new presentations
        total_pages: Total page count of the existing presentation, or None
        target_page_number: Page number to edit, or None
        db: Database session

    Returns:
        Tuple of (system_content: str, effective_target_page_number: Optional[int])
    """
    system_content = SLIDE_GENERATION_PROMPT

    if history:
        history_text = "\n===== RECENT CHAT HISTORY =====\n"
        for msg in history:
            history_text += f"{msg.role.value}: {msg.content}\n"
        system_content += "\n\n" + history_text

    summary_data = load_summary(conversation_id, user_id, db)
    if summary_data.get("summary_content"):
        system_content += (
            "\n===== CONVERSATION SUMMARY =====\n"
            f"{summary_data['summary_content']}"
        )

    if previous_pages:
        if target_page_number is not None:
            target_page = next(
                (p for p in previous_pages if p.page_number == target_page_number),
                None,
            )
            if target_page:
                system_content += (
                    f"\n\n===== PREVIOUS SLIDE - Page {target_page_number}"
                    f" (TARGET PAGE TO EDIT) =====\n"
                )
                system_content += f"Page Title: {target_page.page_title or 'No title'}\n"
                system_content += f"HTML Content:\n{target_page.html_content}\n\n"
                system_content += (
                    "INSTRUCTIONS FOR EDITING SPECIFIC PAGE:\n"
                    f"- Edit ONLY Page {target_page_number}\n"
                    "- Keep the same page_number\n"
                    "- Modify html_content according to user request\n"
                    "- Output should contain ONLY this page (not other pages)\n"
                    "- Backend will merge this with other unchanged pages\n\n"
                )
            else:
                # Requested page not found — fall back to full-presentation edit
                target_page_number = None

        if target_page_number is None:
            system_content += (
                f"\n\n===== PREVIOUS SLIDE - All {total_pages} Pages (for reference) =====\n"
            )
            for page in previous_pages:
                system_content += (
                    f"\n--- Page {page.page_number}: {page.page_title or 'No title'} ---\n"
                )
                system_content += f"{page.html_content}\n"
            system_content += "\n"
            system_content += (
                "INSTRUCTIONS FOR EDITING ENTIRE PRESENTATION:\n"
                "- You can add, remove, or modify any pages\n"
                "- Return complete new presentation (all pages)\n"
                "- Maintain consistent design across all pages\n"
                "- Preserve good elements unless explicitly asked to change\n\n"
            )

    if action == "CREATE_NEW":
        system_content += "\n\nCreate a NEW HTML slide presentation based on the user's request below."
    elif target_page_number is not None:
        system_content += f"\n\nEDIT Page {target_page_number} based on the user's request below."
    else:
        system_content += "\n\nEDIT the entire presentation based on the user's request below."

    return system_content, target_page_number
