"""
UserFact Model - SQLAlchemy ORM
Maps to 'user_facts' table
"""
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database.session import Base


class UserFact(Base):
    __tablename__ = "user_facts"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign Keys
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Data
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    user = relationship("User", back_populates="user_facts")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'key', name='uq_user_fact_key'),
    )
    
    def __repr__(self):
        return f"<UserFact(id={self.id}, user_id={self.user_id}, key={self.key})>"
