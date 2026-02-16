"""
Presentation Model - SQLAlchemy ORM
Maps to 'presentations' table (current/active presentations)
"""
from sqlalchemy import Column, String, Integer, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB
from sqlalchemy.orm import relationship
from app.database.session import Base


class Presentation(Base):
    __tablename__ = "presentations"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign Keys
    conversation_id = Column(UUID, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    
    # Data
    topic = Column(String, nullable=False)
    total_pages = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False, server_default="1")
    metadata = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    conversation = relationship("Conversation", back_populates="presentations", foreign_keys=[conversation_id])
    pages = relationship("PresentationPage", back_populates="presentation", cascade="all, delete-orphan")
    versions = relationship("PresentationVersion", back_populates="presentation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Presentation(id={self.id}, conversation_id={self.conversation_id}, topic={self.topic}, version={self.version})>"
