"""
Token Blacklist Repository - Data access for blacklisted tokens
"""
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.models.token_blacklist import TokenBlacklist
from uuid import UUID
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


class TokenBlacklistRepository:

    def __init__(self, db: Session):
        self.db = db

    def add_token_to_blacklist(
        self,
        token_jti: str,
        user_id: str,
        token_type: str,
        expires_at: datetime,
    ) -> bool:
        """
        Add token to blacklist.

        Args:
            token_jti: JWT ID (jti claim)
            user_id: User ID
            token_type: Type of token ('refresh')
            expires_at: When token expires

        Returns:
            True if successful, False otherwise
        """
        try:
            blacklist_entry = TokenBlacklist(
                token_jti=token_jti,
                user_id=UUID(user_id),
                token_type=token_type,
                expires_at=expires_at
            )
            self.db.add(blacklist_entry)
            self.db.commit()
            return True
        except Exception as e:
            logger.exception("add_token_to_blacklist_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to add token to blacklist: {e}") from e

    def is_token_blacklisted(self, token_jti: str) -> bool:
        """
        Check if token is blacklisted.

        Args:
            token_jti: JWT ID to check

        Returns:
            True if blacklisted, False otherwise
        """
        try:
            exists = self.db.query(TokenBlacklist).filter(
                TokenBlacklist.token_jti == token_jti
            ).first()
            return exists is not None
        except Exception as e:
            logger.exception("is_token_blacklisted_failed")
            raise DatabaseError(f"Failed to check token blacklist: {e}") from e

    def cleanup_expired_tokens(self) -> int:
        """
        Delete expired tokens from blacklist (for periodic cleanup).

        Returns:
            Number of deleted entries
        """
        try:
            now = datetime.now(timezone.utc)
            deleted = self.db.query(TokenBlacklist).filter(
                TokenBlacklist.expires_at < now
            ).delete()
            self.db.commit()
            return deleted
        except Exception as e:
            logger.exception("cleanup_expired_tokens_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to cleanup expired tokens: {e}") from e
