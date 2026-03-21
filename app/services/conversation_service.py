"""
Conversation service - Business logic for conversation management.

Centralizes all conversation-related business logic:
- CRUD operations (wrapping repository calls)
- Ownership validation
- Conversation creation with title generation
"""
from typing import Optional, Tuple, List, Dict, Any

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.presentation_repository import PresentationRepository
from app.utils.title_generator import generate_conversation_title
from app.exceptions import NotFoundError
from app.logging import get_logger

logger = get_logger(__name__)


class ConversationService:

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        chat_repo: ChatRepository,
        presentation_repo: PresentationRepository,
    ):
        self.conversation_repo = conversation_repo
        self.chat_repo = chat_repo
        self.presentation_repo = presentation_repo

    # ---------------------------------------------------------------------------
    # Ownership / access helpers
    # ---------------------------------------------------------------------------

    def validate_conversation_access(self, user_id: str, conversation_id: str) -> None:
        """
        Validate that user has access to the conversation.

        Args:
            user_id: UUID of the user
            conversation_id: UUID of the conversation

        Raises:
            NotFoundError: If conversation not found or user doesn't own it
            DatabaseError: If DB query fails (propagated from repository)
        """
        conv = self.conversation_repo.get_conversation_by_id(conversation_id, user_id)
        if conv is None:
            raise NotFoundError("Conversation", conversation_id)

    def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        user_input: str,
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Get an existing conversation (validating ownership) or create a new one.

        If conversation_id is absent/null/"null", a new conversation is created and
        its title is generated from the user's input. Otherwise, ownership is
        verified via validate_conversation_access.

        Args:
            user_id: UUID of the authenticated user
            conversation_id: Existing conversation UUID, or None / "" / "null"
            user_input: User's message text (used for title generation on new convs)

        Returns:
            Tuple of (conversation_id, new_conv_id_if_created, title_if_created)
            - new_conv_id_if_created is None when the conversation already existed
            - title_if_created is None when the conversation already existed

        Raises:
            DatabaseError: If creating a new conversation fails
            NotFoundError: If existing conversation is not found or not owned
        """
        is_new = not conversation_id or conversation_id == "null" or conversation_id == ""

        if is_new:
            conversation_id = self.conversation_repo.create_new_conversation(user_id)

            try:
                title = generate_conversation_title(user_input)
                self.conversation_repo.update_conversation_title(conversation_id, title, user_id)
            except Exception:
                title = user_input[:60].strip()
                if len(user_input) > 60:
                    title += "..."
                self.conversation_repo.update_conversation_title(conversation_id, title, user_id)

            logger.info("conversation_created", conversation_id=conversation_id, title=title)
            return conversation_id, conversation_id, title

        else:
            self.validate_conversation_access(user_id, conversation_id)
            return conversation_id, None, None

    # ---------------------------------------------------------------------------
    # CRUD — used by routers/conversations.py
    # ---------------------------------------------------------------------------

    def list_conversations(self, user_id: str) -> list:
        """
        List all conversations for a user, ordered by updated_at desc.

        Raises:
            DatabaseError: On DB failure (propagated from repository)
        """
        return self.conversation_repo.list_conversations(user_id)

    def check_conversation_exists(self, conversation_id: str, user_id: str) -> bool:
        """Return True if the conversation exists and belongs to the user."""
        conv = self.conversation_repo.get_conversation_by_id(conversation_id, user_id)
        return conv is not None

    def get_conversation(self, conversation_id: str, user_id: str) -> dict:
        """
        Get conversation by ID.

        Raises:
            NotFoundError: If conversation not found or not owned by user
            DatabaseError: On DB failure (propagated from repository)
        """
        conv = self.conversation_repo.get_conversation_by_id(conversation_id, user_id)
        if conv is None:
            raise NotFoundError("Conversation", conversation_id)
        return conv

    def update_conversation(
        self, conversation_id: str, user_id: str, data: Dict[str, Any]
    ) -> dict:
        """
        Update conversation fields (e.g. title).

        Raises:
            NotFoundError: If conversation not found or not owned by user
            DatabaseError: On DB failure (propagated from repository)
        """
        conv = self.conversation_repo.update_conversation(conversation_id, user_id, data)
        if conv is None:
            raise NotFoundError("Conversation", conversation_id)
        return conv

    def delete_conversation(self, conversation_id: str, user_id: str) -> None:
        """
        Delete conversation if it belongs to the user.

        Raises:
            NotFoundError: If conversation not found or not owned by user
            DatabaseError: On DB failure (propagated from repository)
        """
        deleted = self.conversation_repo.delete_conversation(conversation_id, user_id)
        if not deleted:
            raise NotFoundError("Conversation", conversation_id)

    def get_messages(self, conversation_id: str, user_id: str) -> list:
        """
        Get all messages in a conversation (including summarized).

        Raises:
            DatabaseError: On DB failure (propagated from repository)
        """
        return self.chat_repo.load_all_messages_for_conversation(conversation_id, user_id)

    def get_active_presentation(self, conversation_id: str, user_id: str) -> Optional[str]:
        """
        Get active presentation ID for a conversation.

        Returns None if no active presentation exists.
        """
        return self.presentation_repo.get_active_presentation(conversation_id, user_id)
