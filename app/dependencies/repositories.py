"""
Repository dependencies - Factory functions for all repository instances.

Each function is a FastAPI dependency that receives a db session (via get_db)
and returns the corresponding repository instance. Routers and service
factories should never import db or repository classes directly.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.user_repository import UserRepository
from app.repositories.user_facts_repository import UserFactsRepository
from app.repositories.token_blacklist_repository import TokenBlacklistRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.presentation_repository import PresentationRepository
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository


def get_conversation_repository(
    db: Session = Depends(get_db),
) -> ConversationRepository:
    return ConversationRepository(db)


def get_chat_repository(
    db: Session = Depends(get_db),
) -> ChatRepository:
    return ChatRepository(db)


def get_user_repository(
    db: Session = Depends(get_db),
) -> UserRepository:
    return UserRepository(db)


def get_user_facts_repository(
    db: Session = Depends(get_db),
) -> UserFactsRepository:
    return UserFactsRepository(db)


def get_token_blacklist_repository(
    db: Session = Depends(get_db),
) -> TokenBlacklistRepository:
    return TokenBlacklistRepository(db)


def get_summary_repository(
    db: Session = Depends(get_db),
) -> SummaryRepository:
    return SummaryRepository(db)


def get_presentation_repository(
    db: Session = Depends(get_db),
) -> PresentationRepository:
    return PresentationRepository(db)


def get_password_reset_token_repository(
    db: Session = Depends(get_db),
) -> PasswordResetTokenRepository:
    return PasswordResetTokenRepository(db)
