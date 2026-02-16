"""
PresentationVersion Model - SQLAlchemy ORM
Maps to 'presentation_versions' table (archived presentation versions)
"""
from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database.session import Base


class PresentationVersion(Base):
    __tablename__ = "presentation_versions"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign Keys
    presentation_id = Column(UUID, ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False)
    
    # Data
    version = Column(Integer, nullable=False)
    total_pages = Column(Integer, nullable=False)
    user_request = Column(String, nullable=True)
    
    # Timestamp
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    presentation = relationship("Presentation", back_populates="versions")
    pages = relationship("PresentationVersionPage", back_populates="version", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('presentation_id', 'version', name='uq_presentation_version'),
    )
    
    def __repr__(self):
        return f"<PresentationVersion(id={self.id}, presentation_id={self.presentation_id}, version={self.version})>"
