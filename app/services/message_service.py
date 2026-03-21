"""
Message Service - Business logic for saving chat messages.

Provides thin wrappers around the chat repository so that workflow steps
call a named, intentional operation rather than constructing raw dicts.
"""
from typing import Optional

from app.types.internal.conversation import Message
from app.repositories.chat_repository import ChatRepository


class MessageService:

    def __init__(self, chat_repo: ChatRepository):
        self.chat_repo = chat_repo

    def save_user_message(self, conversation_id: str, content: str) -> Optional[str]:
        """
        Persist a user message and return its database ID.

        Args:
            conversation_id: UUID of the conversation
            content: User's message text

        Returns:
            Message UUID string if saved successfully, None otherwise
        """
        message: Message = {
            "conversation_id": conversation_id,
            "role": "user",
            "content": content,
            "intent": None,
            "metadata": {},
        }
        saved = self.chat_repo.save_message(message)
        return saved["id"] if saved else None

    def save_assistant_message(
        self,
        conversation_id: str,
        content: str,
        intent: str,
        metadata: dict,
    ) -> Optional[str]:
        """
        Persist an assistant message and return its database ID.

        Args:
            conversation_id: UUID of the conversation
            content: Assistant's response text
            intent: Detected intent label (e.g. "GENERAL", "PPTX")
            metadata: Arbitrary metadata dict (pages, slide_id, security flags, etc.)

        Returns:
            Message UUID string if saved successfully, None otherwise
        """
        message: Message = {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": content,
            "intent": intent,
            "metadata": metadata,
        }
        saved = self.chat_repo.save_message(message)
        return saved["id"] if saved else None

    async def save_error_response(
        self,
        conversation_id: str,
        content: str,
        result_dict: dict,
        memory: Optional[object] = None,
        ctx: Optional[object] = None,
    ) -> dict:
        """
        Save assistant error message to DB. Optionally add to memory and update ctx.store.
        Returns result_dict for workflow to wrap in StopEvent.
        """
        assistant_message: Message = {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": content,
            "intent": "GENERAL",
            "metadata": {"error_fallback": True},
        }
        saved = self.chat_repo.save_message(assistant_message)
        msg_id = saved["id"] if saved else None

        if memory is not None and ctx is not None:
            from llama_index.core.llms import ChatMessage, MessageRole

            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=content,
                    additional_kwargs={"message_id": msg_id},
                )
            )
            await ctx.store.set("chat_history", memory)

        return result_dict
