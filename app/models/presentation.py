"""
Presentation Model - SQLAlchemy ORM
TODO: Implement Presentation table mapping
"""
# from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean
# from sqlalchemy.orm import relationship
# from app.database.session import Base
# from datetime import datetime

# class Presentation(Base):
#     __tablename__ = "presentations"
#     
#     id = Column(String, primary_key=True)
#     conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
#     version = Column(Integer, nullable=False)
#     is_archived = Column(Boolean, default=False)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     
#     # Relationships
#     # pages = relationship("PresentationPage", back_populates="presentation")
