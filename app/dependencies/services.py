"""
Service dependencies - Factory functions for all service instances.

Each function is a FastAPI dependency that receives the required repository
instances (via repository factories) and returns the corresponding service
instance. Routers should only import from this module, never from repositories
or db directly.
"""
from fastapi import Depends

from app.dependencies.repositories import (
    get_conversation_repository,
    get_chat_repository,
    get_user_repository,
    get_user_facts_repository,
    get_token_blacklist_repository,
    get_summary_repository,
    get_presentation_repository,
    get_password_reset_token_repository,
)
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.user_repository import UserRepository
from app.repositories.user_facts_repository import UserFactsRepository
from app.repositories.token_blacklist_repository import TokenBlacklistRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.presentation_repository import PresentationRepository
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository

from app.services.email_service import EmailService
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.memory_service import MemoryService
from app.services.context_service import ContextService
from app.services.presentation_service import PresentationService


def get_email_service() -> EmailService:
    return EmailService()


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    token_blacklist_repo: TokenBlacklistRepository = Depends(get_token_blacklist_repository),
    password_reset_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    email_service: EmailService = Depends(get_email_service),
) -> AuthService:
    return AuthService(user_repo, token_blacklist_repo, password_reset_repo, email_service)


def get_conversation_service(
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    presentation_repo: PresentationRepository = Depends(get_presentation_repository),
) -> ConversationService:
    return ConversationService(conversation_repo, chat_repo, presentation_repo)


def get_message_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> MessageService:
    return MessageService(chat_repo)


def get_memory_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    summary_repo: SummaryRepository = Depends(get_summary_repository),
) -> MemoryService:
    return MemoryService(chat_repo, summary_repo)


def get_context_service(
    summary_repo: SummaryRepository = Depends(get_summary_repository),
    user_facts_repo: UserFactsRepository = Depends(get_user_facts_repository),
) -> ContextService:
    return ContextService(summary_repo, user_facts_repo)


def get_presentation_service(
    presentation_repo: PresentationRepository = Depends(get_presentation_repository),
) -> PresentationService:
    return PresentationService(presentation_repo)
