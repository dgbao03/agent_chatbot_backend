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


def create_token(user_id: Union[str, UUID], expires_minutes: int, db: Session) -> Optional[str]:
    """
    Create a password reset token for user.

    Args:
        user_id: User UUID
        expires_minutes: Token validity in minutes (default 15)
        db: Database session

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
        db.add(record)
        db.commit()
        return token_str
    except Exception as e:
        logger.exception("create_reset_token_failed")
        db.rollback()
        raise DatabaseError(f"Failed to create password reset token: {e}") from e


def get_valid_token(token: str, db: Session) -> Optional[PasswordResetToken]:
    """
    Get token if valid (exists, not expired, not used).

    Args:
        token: Token string
        db: Database session

    Returns:
        PasswordResetToken if valid, None otherwise
    """
    try:
        now = datetime.now(timezone.utc)
        record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.expires_at > now,
            PasswordResetToken.used_at.is_(None),
        ).first()
        return record
    except Exception as e:
        logger.exception("get_valid_reset_token_failed")
        raise DatabaseError(f"Failed to get password reset token: {e}") from e


def cleanup_expired_reset_tokens(db: Session) -> int:
    """
    Delete expired or used password reset tokens (for periodic cleanup).

    Args:
        db: Database session

    Returns:
        Number of deleted entries
    """
    try:
        now = datetime.now(timezone.utc)
        deleted = db.query(PasswordResetToken).filter(
            or_(
                PasswordResetToken.expires_at < now,
                PasswordResetToken.used_at.isnot(None),
            )
        ).delete()
        db.commit()
        return deleted
    except Exception as e:
        logger.exception("cleanup_expired_reset_tokens_failed")
        db.rollback()
        raise DatabaseError(f"Failed to cleanup expired reset tokens: {e}") from e


def mark_token_used(token: str, db: Session) -> bool:
    """
    Mark token as used.

    Args:
        token: Token string
        db: Database session

    Returns:
        True if successful, False otherwise
    """
    try:
        record = db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
        if not record:
            return False
        record.used_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:
        logger.exception("mark_reset_token_used_failed")
        db.rollback()
        raise DatabaseError(f"Failed to mark reset token as used: {e}") from e
