"""
User repository - Data access layer for users.
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import User
from app.logging import get_logger

logger = get_logger(__name__)


def get_user_by_email(email: str, db: Session) -> Optional[User]:
    """
    Get user by email address.
    
    Args:
        email: User's email address
        db: Database session
        
    Returns:
        User object if found, None otherwise
    """
    try:
        user = db.query(User).filter(User.email == email).first()
        return user
    except Exception:
        logger.exception("get_user_by_email_failed")
        return None


def get_user_by_id(user_id: str, db: Session) -> Optional[User]:
    """
    Get user by ID.
    
    Args:
        user_id: UUID of the user
        db: Database session
        
    Returns:
        User object if found, None otherwise
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except Exception:
        logger.exception("get_user_by_id_failed")
        return None


def create_user(user_data: Dict[str, Any], db: Session) -> Optional[User]:
    """
    Create a new user.
    
    Args:
        user_data: Dictionary with user fields (email, hashed_password, name, etc.)
        db: Database session
        
    Returns:
        Created User object if successful, None otherwise
    """
    try:
        new_user = User(**user_data)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception:
        logger.exception("create_user_failed")
        db.rollback()
        return None


def update_user(user_id: str, update_data: Dict[str, Any], db: Session) -> Optional[User]:
    """
    Update user information.
    
    Args:
        user_id: UUID of the user
        update_data: Dictionary with fields to update
        db: Database session
        
    Returns:
        Updated User object if successful, None otherwise
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return None
        
        # Update fields
        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        # Update timestamp
        user.updated_at = func.now()
        
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        logger.exception("update_user_failed")
        db.rollback()
        return None
