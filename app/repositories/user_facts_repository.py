"""
User facts repository - Data access layer for user facts.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import UserFact
from app.config.types import UserFact as UserFactDict


def load_user_facts(user_id: str, db: Session) -> List[UserFactDict]:
    """
    Load user facts from database.
    
    Args:
        user_id: UUID of the user
        db: Database session
        
    Returns:
        List of UserFact dicts with all fields populated (id, user_id, key, value, created_at, updated_at)
    """
    try:
        # Query user facts (automatically filtered by user_id)
        facts = db.query(UserFact).filter(
            UserFact.user_id == user_id
        ).order_by(UserFact.key.asc()).all()
        
        if not facts:
            return []
        
        # Convert to dict format
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
        
    except Exception:
        return []


def upsert_user_fact(fact: UserFactDict, db: Session) -> Optional[UserFactDict]:
    """
    Insert or update a user fact in database.
    
    Args:
        fact: UserFact dict with user_id, key, value
        db: Database session
        
    Returns:
        UserFact dict with id, created_at, updated_at set if successful, None otherwise
    """
    try:
        # Check if fact exists
        existing_fact = db.query(UserFact).filter(
            UserFact.user_id == fact["user_id"],
            UserFact.key == fact["key"]
        ).first()
        
        if existing_fact:
            # Update existing fact
            existing_fact.value = fact["value"]
            existing_fact.updated_at = func.now()
            db.commit()
            db.refresh(existing_fact)
            
            return {
                "id": str(existing_fact.id),
                "user_id": str(existing_fact.user_id),
                "key": existing_fact.key,
                "value": existing_fact.value,
                "created_at": existing_fact.created_at.isoformat() if existing_fact.created_at else None,
                "updated_at": existing_fact.updated_at.isoformat() if existing_fact.updated_at else None,
            }
        else:
            # Insert new fact
            new_fact = UserFact(
                user_id=fact["user_id"],
                key=fact["key"],
                value=fact["value"]
            )
            
            db.add(new_fact)
            db.commit()
            db.refresh(new_fact)
            
            return {
                "id": str(new_fact.id),
                "user_id": str(new_fact.user_id),
                "key": new_fact.key,
                "value": new_fact.value,
                "created_at": new_fact.created_at.isoformat() if new_fact.created_at else None,
                "updated_at": new_fact.updated_at.isoformat() if new_fact.updated_at else None,
            }
        
    except Exception:
        db.rollback()
        return None


def delete_user_fact(user_id: str, key: str, db: Session) -> bool:
    """
    Delete a user fact from database.
    
    Args:
        user_id: UUID of the user
        key: Fact key to delete
        db: Database session
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Delete fact with user_id filter (security)
        db.query(UserFact).filter(
            UserFact.user_id == user_id,
            UserFact.key == key
        ).delete()
        
        db.commit()
        return True
        
    except Exception:
        db.rollback()
        return False

