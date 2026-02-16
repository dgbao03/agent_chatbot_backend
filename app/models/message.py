"""
Message Model - SQLAlchemy ORM
Maps to 'messages' table
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB
from sqlalchemy.orm import relationship
from app.database.session import Base


class Message(Base):
    __tablename__ = "messages"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign Keys
    conversation_id = Column(UUID, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    
    # Data
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    intent = Column(String, nullable=True)
    
    # Memory Management
    is_in_working_memory = Column(Boolean, nullable=False, server_default="true")
    summarized_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Metadata
    metadata = Column(JSONB, nullable=True)
    
    # Timestamp
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="check_message_role"),
        CheckConstraint("intent IN ('PPTX', 'GENERAL') OR intent IS NULL", name="check_message_intent"),
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, role={self.role})>"
