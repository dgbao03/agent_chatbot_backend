"""
User repository - Data access layer for users.
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import User
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


class UserRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User's email address

        Returns:
            User object if found, None otherwise
        """
        try:
            user = self.db.query(User).filter(User.email == email).first()
            return user
        except Exception as e:
            logger.exception("get_user_by_email_failed")
            raise DatabaseError(f"Failed to get user by email: {e}") from e

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: UUID of the user

        Returns:
            User object if found, None otherwise
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            return user
        except Exception as e:
            logger.exception("get_user_by_id_failed")
            raise DatabaseError(f"Failed to get user by id: {e}") from e

    def create_user(self, user_data: Dict[str, Any]) -> Optional[User]:
        """
        Create a new user.

        Args:
            user_data: Dictionary with user fields (email, hashed_password, name, etc.)

        Returns:
            Created User object if successful, None otherwise
        """
        try:
            new_user = User(**user_data)
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            return new_user
        except Exception as e:
            logger.exception("create_user_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to create user: {e}") from e

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """
        Update user information.

        Args:
            user_id: UUID of the user
            update_data: Dictionary with fields to update

        Returns:
            Updated User object if successful, None otherwise
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()

            if not user:
                return None

            for key, value in update_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            user.updated_at = func.now()

            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception as e:
            logger.exception("update_user_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to update user: {e}") from e
