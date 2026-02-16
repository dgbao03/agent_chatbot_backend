"""
UserFact Model - SQLAlchemy ORM
TODO: Implement UserFact table mapping
"""
# from sqlalchemy import Column, String, Text, DateTime, ForeignKey
# from app.database.session import Base
# from datetime import datetime

# class UserFact(Base):
#     __tablename__ = "user_facts"
#     
#     id = Column(String, primary_key=True)
#     user_id = Column(String, ForeignKey("users.id"), nullable=False)
#     key = Column(String, nullable=False)
#     value = Column(Text, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
