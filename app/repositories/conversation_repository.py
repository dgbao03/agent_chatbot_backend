"""
Conversation repository - Data access layer for conversations.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import Conversation
from app.types.internal.conversation import Conversation as ConversationDict
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


class ConversationRepository:

    def __init__(self, db: Session):
        self.db = db

    def list_conversations(self, user_id: str) -> List[ConversationDict]:
        """
        List all conversations for a user, ordered by updated_at desc.

        Args:
            user_id: UUID of the user

        Returns:
            List of conversation dicts

        Raises:
            DatabaseError: On DB failure
        """
        try:
            conversations = (
                self.db.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .order_by(desc(Conversation.updated_at))
                .all()
            )
            return [
                {
                    "id": str(c.id),
                    "user_id": str(c.user_id),
                    "title": c.title,
                    "active_presentation_id": str(c.active_presentation_id) if c.active_presentation_id else None,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in conversations
            ]
        except Exception as e:
            logger.exception("list_conversations_failed")
            raise DatabaseError(f"Failed to list conversations: {e}") from e

    def get_conversation_by_id(self, conversation_id: str, user_id: str) -> Optional[ConversationDict]:
        """
        Get conversation by ID if it belongs to the user.

        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user

        Returns:
            Conversation dict or None if not found / not owned
        """
        try:
            conv = (
                self.db.query(Conversation)
                .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
                .first()
            )
            if not conv:
                return None
            return {
                "id": str(conv.id),
                "user_id": str(conv.user_id),
                "title": conv.title,
                "active_presentation_id": str(conv.active_presentation_id) if conv.active_presentation_id else None,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
        except Exception as e:
            logger.exception("get_conversation_by_id_failed")
            raise DatabaseError(f"Failed to get conversation: {e}") from e

    def update_conversation(
        self, conversation_id: str, user_id: str, data: Dict[str, Any]
    ) -> Optional[ConversationDict]:
        """
        Update conversation (e.g. title) if it belongs to the user.

        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user
            data: Dict with fields to update (title, etc.)

        Returns:
            Updated conversation dict or None
        """
        try:
            conv = (
                self.db.query(Conversation)
                .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
                .first()
            )
            if not conv:
                return None
            if "title" in data and data["title"] is not None:
                conv.title = data["title"]
            self.db.commit()
            self.db.refresh(conv)
            return {
                "id": str(conv.id),
                "user_id": str(conv.user_id),
                "title": conv.title,
                "active_presentation_id": str(conv.active_presentation_id) if conv.active_presentation_id else None,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
        except Exception as e:
            logger.exception("update_conversation_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to update conversation: {e}") from e

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """
        Delete conversation if it belongs to the user. Cascade deletes messages, summaries, presentations.

        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user

        Returns:
            True if deleted, False if not found / not owned
        """
        try:
            conv = (
                self.db.query(Conversation)
                .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
                .first()
            )
            if not conv:
                return False
            self.db.delete(conv)
            self.db.commit()
            return True
        except Exception as e:
            logger.exception("delete_conversation_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to delete conversation: {e}") from e

    def create_new_conversation(self, user_id: str) -> str:
        """
        Create a new conversation with title = null initially.
        Title will be updated after generation.

        Args:
            user_id: UUID of the user

        Returns:
            Conversation ID (UUID string)

        Raises:
            DatabaseError: If conversation creation fails
        """
        try:
            conversation = Conversation(
                user_id=user_id,
                title=None
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
            return str(conversation.id)
        except Exception as e:
            self.db.rollback()
            raise DatabaseError(f"Failed to create conversation: {e}") from e

    def update_conversation_title(self, conversation_id: str, title: str, user_id: str) -> bool:
        """
        Update conversation title.

        Args:
            conversation_id: UUID of the conversation
            title: Title string to set
            user_id: UUID of the user (for ownership check)

        Returns:
            True if successful, False otherwise
        """
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            ).first()

            if not conversation:
                return False

            conversation.title = title
            self.db.commit()
            return True
        except Exception as e:
            logger.exception("update_conversation_title_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to update conversation title: {e}") from e
