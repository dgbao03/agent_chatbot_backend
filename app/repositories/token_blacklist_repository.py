"""
Token Blacklist Repository - Data access for blacklisted tokens
"""
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.models.token_blacklist import TokenBlacklist
from uuid import UUID


def add_token_to_blacklist(
    token_jti: str,
    user_id: str,
    token_type: str,
    expires_at: datetime,
    db: Session
) -> bool:
    """
    Add token to blacklist.
    
    Args:
        token_jti: JWT ID (jti claim)
        user_id: User ID
        token_type: Type of token ('refresh')
        expires_at: When token expires
        db: Database session
        
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
        
        db.add(blacklist_entry)
        db.commit()
        return True
        
    except Exception as e:
        db.rollback()
        print(f"Error adding token to blacklist: {e}")
        return False


def is_token_blacklisted(token_jti: str, db: Session) -> bool:
    """
    Check if token is blacklisted.
    
    Args:
        token_jti: JWT ID to check
        db: Database session
        
    Returns:
        True if blacklisted, False otherwise
    """
    try:
        exists = db.query(TokenBlacklist).filter(
            TokenBlacklist.token_jti == token_jti
        ).first()
        
        return exists is not None
        
    except Exception:
        return False


def cleanup_expired_tokens(db: Session) -> int:
    """
    Delete expired tokens from blacklist (for periodic cleanup).
    
    Args:
        db: Database session
        
    Returns:
        Number of deleted entries
    """
    try:
        now = datetime.now(timezone.utc)
        
        deleted = db.query(TokenBlacklist).filter(
            TokenBlacklist.expires_at < now
        ).delete()
        
        db.commit()
        return deleted
        
    except Exception:
        db.rollback()
        return 0
