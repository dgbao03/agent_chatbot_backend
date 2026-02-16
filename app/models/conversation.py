"""
Conversation Model - SQLAlchemy ORM
TODO: Implement Conversation table mapping
"""
# from sqlalchemy import Column, String, DateTime, ForeignKey
# from sqlalchemy.orm import relationship
# from app.database.session import Base
# from datetime import datetime

# class Conversation(Base):
#     __tablename__ = "conversations"
#     
#     id = Column(String, primary_key=True)
#     user_id = Column(String, ForeignKey("users.id"), nullable=False)
#     title = Column(String, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     
#     # Relationships
#     # user = relationship("User", back_populates="conversations")
#     # messages = relationship("Message", back_populates="conversation")
