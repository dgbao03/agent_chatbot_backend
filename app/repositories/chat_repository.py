"""
Chat history repository - Data access layer for messages.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import Message, Conversation
from app.types.internal.conversation import Message as MessageDict
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


class ChatRepository:

    def __init__(self, db: Session):
        self.db = db

    def load_chat_history(self, conversation_id: str, user_id: str) -> List[MessageDict]:
        """
        Load working memory messages from database for a conversation.
        Returns list of messages in working memory, ordered by created_at.

        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user (for ownership check)

        Returns:
            List of Message dicts with all fields populated (id, conversation_id, role, content, etc.)
        """
        try:
            # Verify conversation belongs to user (security check)
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            ).first()

            if not conversation:
                return []

            # Query messages in working memory for this conversation
            messages = self.db.query(Message).filter(
                Message.conversation_id == conversation_id,
                Message.is_in_working_memory == True
            ).order_by(Message.created_at.asc()).all()

            if not messages:
                return []

            result: List[MessageDict] = []
            for msg in messages:
                result.append(
                    {
                        "id": str(msg.id),
                        "conversation_id": str(msg.conversation_id),
                        "role": msg.role,
                        "content": msg.content,
                        "intent": msg.intent,
                        "is_in_working_memory": msg.is_in_working_memory,
                        "summarized_at": msg.summarized_at.isoformat() if msg.summarized_at else None,
                        "metadata": msg.msg_metadata,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    }
                )

            return result

        except Exception as e:
            logger.exception("load_chat_history_failed")
            raise DatabaseError(f"Failed to load chat history: {e}") from e

    def load_all_messages_for_conversation(
        self, conversation_id: str, user_id: str
    ) -> List[MessageDict]:
        """
        Load ALL messages for a conversation (including summarized).
        Used by FE to display full chat history.
        Ownership checked via Conversation.user_id.

        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user (for ownership check)

        Returns:
            List of Message dicts ordered by created_at asc
        """
        try:
            # Verify conversation belongs to user
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            ).first()
            if not conversation:
                return []

            messages = (
                self.db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .all()
            )
            if not messages:
                return []

            result: List[MessageDict] = []
            for msg in messages:
                result.append({
                    "id": str(msg.id),
                    "conversation_id": str(msg.conversation_id),
                    "role": msg.role,
                    "content": msg.content,
                    "intent": msg.intent,
                    "is_in_working_memory": msg.is_in_working_memory,
                    "summarized_at": msg.summarized_at.isoformat() if msg.summarized_at else None,
                    "metadata": msg.msg_metadata,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                })
            return result
        except Exception as e:
            logger.exception("load_all_messages_failed")
            raise DatabaseError(f"Failed to load messages: {e}") from e

    def save_message(self, message: MessageDict) -> Optional[MessageDict]:
        """
        Save a new message to database.

        Args:
            message: Message dict with conversation_id, role, content, intent (optional), metadata (optional)

        Returns:
            Message dict with id and created_at set if successful, None if failed
        """
        try:
            new_message = Message(
                conversation_id=message["conversation_id"],
                role=message["role"],
                content=message["content"],
                intent=message.get("intent"),
                msg_metadata=message.get("metadata"),
                is_in_working_memory=message.get("is_in_working_memory", True)
            )

            self.db.add(new_message)
            self.db.commit()
            self.db.refresh(new_message)

            return {
                "id": str(new_message.id),
                "conversation_id": str(new_message.conversation_id),
                "role": new_message.role,
                "content": new_message.content,
                "intent": new_message.intent,
                "is_in_working_memory": new_message.is_in_working_memory,
                "summarized_at": new_message.summarized_at.isoformat() if new_message.summarized_at else None,
                "metadata": new_message.msg_metadata,
                "created_at": new_message.created_at.isoformat() if new_message.created_at else None,
            }

        except Exception as e:
            logger.exception("save_message_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to save message: {e}") from e
