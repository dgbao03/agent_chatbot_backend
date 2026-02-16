"""
Message Model - SQLAlchemy ORM
TODO: Implement Message table mapping
"""
# from sqlalchemy import Column, String, Text, DateTime, ForeignKey
# from app.database.session import Base
# from datetime import datetime

# class Message(Base):
#     __tablename__ = "messages"
#     
#     id = Column(String, primary_key=True)
#     conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
#     role = Column(String, nullable=False)  # 'user' or 'assistant'
#     content = Column(Text, nullable=False)
#     intent = Column(String, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
