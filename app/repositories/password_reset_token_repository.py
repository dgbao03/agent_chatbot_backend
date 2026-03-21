"""
Password Reset Token Repository - Data access for password reset tokens
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.password_reset_token import PasswordResetToken
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


class PasswordResetTokenRepository:

    def __init__(self, db: Session):
        self.db = db

    def create_token(self, user_id: Union[str, UUID], expires_minutes: int) -> Optional[str]:
        """
        Create a password reset token for user.

        Args:
            user_id: User UUID
            expires_minutes: Token validity in minutes

        Returns:
            Token string if successful, None otherwise
        """
        try:
            token_str = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
            uid = UUID(user_id) if isinstance(user_id, str) else user_id

            record = PasswordResetToken(
                token=token_str,
                user_id=uid,
                expires_at=expires_at,
            )
            self.db.add(record)
            self.db.commit()
            return token_str
        except Exception as e:
            logger.exception("create_reset_token_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to create password reset token: {e}") from e

    def get_valid_token(self, token: str) -> Optional[PasswordResetToken]:
        """
        Get token if valid (exists, not expired, not used).

        Args:
            token: Token string

        Returns:
            PasswordResetToken if valid, None otherwise
        """
        try:
            now = datetime.now(timezone.utc)
            record = self.db.query(PasswordResetToken).filter(
                PasswordResetToken.token == token,
                PasswordResetToken.expires_at > now,
                PasswordResetToken.used_at.is_(None),
            ).first()
            return record
        except Exception as e:
            logger.exception("get_valid_reset_token_failed")
            raise DatabaseError(f"Failed to get password reset token: {e}") from e

    def cleanup_expired_reset_tokens(self) -> int:
        """
        Delete expired or used password reset tokens (for periodic cleanup).

        Returns:
            Number of deleted entries
        """
        try:
            now = datetime.now(timezone.utc)
            deleted = self.db.query(PasswordResetToken).filter(
                or_(
                    PasswordResetToken.expires_at < now,
                    PasswordResetToken.used_at.isnot(None),
                )
            ).delete()
            self.db.commit()
            return deleted
        except Exception as e:
            logger.exception("cleanup_expired_reset_tokens_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to cleanup expired reset tokens: {e}") from e

    def mark_token_used(self, token: str) -> bool:
        """
        Mark token as used.

        Args:
            token: Token string

        Returns:
            True if successful, False otherwise
        """
        try:
            record = self.db.query(PasswordResetToken).filter(
                PasswordResetToken.token == token
            ).first()
            if not record:
                return False
            record.used_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        except Exception as e:
            logger.exception("mark_reset_token_used_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to mark reset token as used: {e}") from e
