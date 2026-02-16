"""
PresentationVersionPage Model - SQLAlchemy ORM
Maps to 'presentation_version_pages' table (archived presentation version pages)
"""
from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.session import Base


class PresentationVersionPage(Base):
    __tablename__ = "presentation_version_pages"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign Keys
    version_id = Column(UUID, ForeignKey("presentation_versions.id", ondelete="CASCADE"), nullable=False)
    
    # Data
    page_number = Column(Integer, nullable=False)
    html_content = Column(String, nullable=False)
    page_title = Column(String, nullable=True)
    
    # Relationships
    version = relationship("PresentationVersion", back_populates="pages")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('version_id', 'page_number', name='uq_version_page_number'),
    )
    
    def __repr__(self):
        return f"<PresentationVersionPage(id={self.id}, version_id={self.version_id}, page_number={self.page_number})>"
