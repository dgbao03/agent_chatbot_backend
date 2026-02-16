"""
Conversation Model - SQLAlchemy ORM
Maps to 'conversations' table
"""
from sqlalchemy import Column, String, Integer, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database.session import Base


class Conversation(Base):
    __tablename__ = "conversations"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign Keys
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    active_presentation_id = Column(UUID, ForeignKey("presentations.id", ondelete="SET NULL"), nullable=True)
    
    # Data
    title = Column(String, nullable=True)
    next_presentation_id_counter = Column(Integer, nullable=False, server_default="1")
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    summaries = relationship("ConversationSummary", back_populates="conversation", cascade="all, delete-orphan")
    presentations = relationship("Presentation", back_populates="conversation", foreign_keys="Presentation.conversation_id", cascade="all, delete-orphan")
    active_presentation = relationship("Presentation", foreign_keys=[active_presentation_id], post_update=True)
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title={self.title})>"
