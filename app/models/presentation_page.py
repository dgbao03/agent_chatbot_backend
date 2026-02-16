"""
PresentationPage Model - SQLAlchemy ORM
Maps to 'presentation_pages' table (current presentation pages)
"""
from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database.session import Base


class PresentationPage(Base):
    __tablename__ = "presentation_pages"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign Keys
    presentation_id = Column(UUID, ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False)
    
    # Data
    page_number = Column(Integer, nullable=False)
    html_content = Column(String, nullable=False)
    page_title = Column(String, nullable=True)
    
    # Timestamp
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    presentation = relationship("Presentation", back_populates="pages")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('presentation_id', 'page_number', name='uq_presentation_page_number'),
    )
    
    def __repr__(self):
        return f"<PresentationPage(id={self.id}, presentation_id={self.presentation_id}, page_number={self.page_number})>"
