"""
User facts repository - Data access layer for user facts.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import UserFact
from app.types.internal.user_facts import UserFact as UserFactDict
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


class UserFactsRepository:

    def __init__(self, db: Session):
        self.db = db

    def load_user_facts(self, user_id: str) -> List[UserFactDict]:
        """
        Load user facts from database.

        Args:
            user_id: UUID of the user

        Returns:
            List of UserFact dicts with all fields populated (id, user_id, key, value, created_at, updated_at)
        """
        try:
            facts = self.db.query(UserFact).filter(
                UserFact.user_id == user_id
            ).order_by(UserFact.key.asc()).all()

            if not facts:
                return []

            result: List[UserFactDict] = []
            for fact in facts:
                result.append(
                    {
                        "id": str(fact.id),
                        "user_id": str(fact.user_id),
                        "key": fact.key,
                        "value": fact.value,
                        "created_at": fact.created_at.isoformat() if fact.created_at else None,
                        "updated_at": fact.updated_at.isoformat() if fact.updated_at else None,
                    }
                )

            return result

        except Exception as e:
            logger.exception("load_user_facts_failed")
            raise DatabaseError(f"Failed to load user facts: {e}") from e

    def upsert_user_fact(self, fact: UserFactDict) -> Optional[UserFactDict]:
        """
        Insert or update a user fact in database.

        Args:
            fact: UserFact dict with user_id, key, value

        Returns:
            UserFact dict with id, created_at, updated_at set if successful, None otherwise
        """
        try:
            existing_fact = self.db.query(UserFact).filter(
                UserFact.user_id == fact["user_id"],
                UserFact.key == fact["key"]
            ).first()

            if existing_fact:
                existing_fact.value = fact["value"]
                existing_fact.updated_at = func.now()
                self.db.commit()
                self.db.refresh(existing_fact)

                return {
                    "id": str(existing_fact.id),
                    "user_id": str(existing_fact.user_id),
                    "key": existing_fact.key,
                    "value": existing_fact.value,
                    "created_at": existing_fact.created_at.isoformat() if existing_fact.created_at else None,
                    "updated_at": existing_fact.updated_at.isoformat() if existing_fact.updated_at else None,
                }
            else:
                new_fact = UserFact(
                    user_id=fact["user_id"],
                    key=fact["key"],
                    value=fact["value"]
                )
                self.db.add(new_fact)
                self.db.commit()
                self.db.refresh(new_fact)

                return {
                    "id": str(new_fact.id),
                    "user_id": str(new_fact.user_id),
                    "key": new_fact.key,
                    "value": new_fact.value,
                    "created_at": new_fact.created_at.isoformat() if new_fact.created_at else None,
                    "updated_at": new_fact.updated_at.isoformat() if new_fact.updated_at else None,
                }

        except Exception as e:
            logger.exception("upsert_user_fact_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to upsert user fact: {e}") from e

    def delete_user_fact(self, user_id: str, key: str) -> bool:
        """
        Delete a user fact from database.

        Args:
            user_id: UUID of the user
            key: Fact key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.db.query(UserFact).filter(
                UserFact.user_id == user_id,
                UserFact.key == key
            ).delete()

            self.db.commit()
            return True

        except Exception as e:
            logger.exception("delete_user_fact_failed")
            self.db.rollback()
            raise DatabaseError(f"Failed to delete user fact: {e}") from e
