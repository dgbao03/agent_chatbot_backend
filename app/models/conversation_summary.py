"""
ConversationSummary Model - SQLAlchemy ORM
Maps to 'conversation_summaries' table
"""
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database.session import Base


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign Keys
    conversation_id = Column(UUID, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    
    # Data
    summary_content = Column(String, nullable=False)
    
    # Timestamp
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    conversation = relationship("Conversation", back_populates="summaries")
    
    # Constraints - 1 summary per conversation (upsert overwrites)
    __table_args__ = (
        UniqueConstraint('conversation_id', name='uq_conversation_summary_conversation_id'),
    )
    
    def __repr__(self):
        return f"<ConversationSummary(id={self.id}, conversation_id={self.conversation_id})>"
